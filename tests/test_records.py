"""Call records, transcripts, messages and the activity summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ait_voice.core.audit import AuditLog
from ait_voice.core.pipeline import CallResult
from ait_voice.core.recording import outcome_for, record_call, take_message, transcript_from
from ait_voice.core.records import (
    ActivitySummary,
    CallOutcome,
    CallRecord,
    CallStore,
    Message,
    Speaker,
    Transcript,
    TranscriptTurn,
    mask_number,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region, TenantContext, Utterance


def _tenant(tenant_id: str = "northside", region: Region = Region.US) -> TenantContext:
    return TenantConfig(tenant_id=tenant_id, region=region, clinic_name="Northside").context()


def _record(call_id: str = "c-1", **kw) -> CallRecord:  # noqa: ANN003
    base = {
        "call_id": call_id,
        "tenant_id": "northside",
        "started_at": datetime.now(UTC),
        "duration_seconds": 90.0,
        "turns": 3,
    }
    return CallRecord(**{**base, **kw})


class TestMasking:
    def test_a_number_keeps_its_prefix_and_last_two_digits(self) -> None:
        assert mask_number("+15551234541") == "+1555…41"

    def test_whitespace_is_normalised_first(self) -> None:
        assert mask_number("+1 555 123 4541") == "+1555…41"

    def test_a_short_number_reveals_almost_nothing(self) -> None:
        assert mask_number("4541") == "…41"

    def test_an_empty_number_stays_empty(self) -> None:
        assert mask_number("") == ""

    def test_a_record_without_a_caller_says_unknown(self) -> None:
        assert _record().caller_masked == "unknown"

    def test_the_summary_never_carries_the_raw_number(self) -> None:
        """The list view is where a leak would be widest."""
        summary = _record(caller=PHI("+15551234541")).summary()
        assert "+15551234541" not in str(summary)
        assert summary["caller_masked"] == "+1555…41"


class TestCallRecord:
    def test_escalated_reflects_the_outcome(self) -> None:
        assert _record(outcome=CallOutcome.ESCALATED).escalated
        assert not _record(outcome=CallOutcome.NO_ACTION).escalated

    def test_an_unobservable_latency_is_carried_not_dropped(self) -> None:
        """A relayed call's p95 is a floor; the screen has to be able to say so."""
        assert _record(latency_observable=False).summary()["latency_observable"] is False

    def test_the_summary_is_json_safe(self) -> None:
        import json

        json.dumps(_record(caller=PHI("+15551234541"), p95_ms=812.44).summary())


class TestStoreIsolation:
    def test_one_clinic_cannot_read_anothers_calls(self) -> None:
        store = CallStore()
        a, b = _tenant("clinic-a"), _tenant("clinic-b")
        store.add(a, _record("shared-id", tenant_id="clinic-a"))

        assert store.get(a, "shared-id") is not None
        assert store.get(b, "shared-id") is None
        assert store.recent(b) == []

    def test_transcripts_are_partitioned_too(self) -> None:
        store = CallStore()
        a, b = _tenant("clinic-a"), _tenant("clinic-b")
        store.add(a, _record("c-1"))
        store.attach_transcript(
            a, Transcript("c-1", (TranscriptTurn(Speaker.CALLER, PHI("private")),))
        )

        assert store.transcript(a, "c-1") is not None
        assert store.transcript(b, "c-1") is None

    def test_attaching_to_another_tenants_call_does_nothing(self) -> None:
        store = CallStore()
        a, b = _tenant("clinic-a"), _tenant("clinic-b")
        store.add(a, _record("c-1"))

        assert store.attach_transcript(b, Transcript("c-1")) is None
        assert store.transcript(a, "c-1") is None

    def test_the_store_refuses_to_iterate_without_a_tenant(self) -> None:
        """An 'all records' accessor is how a filter gets forgotten."""
        with pytest.raises(TypeError, match="tenant context"):
            list(CallStore())


class TestRecentAndSummary:
    def test_recent_is_newest_first(self) -> None:
        store = CallStore()
        tenant = _tenant()
        now = datetime.now(UTC)
        for i in range(3):
            store.add(tenant, _record(f"c-{i}", started_at=now - timedelta(hours=i)))

        assert [r.call_id for r in store.recent(tenant)] == ["c-0", "c-1", "c-2"]

    def test_recent_respects_the_limit(self) -> None:
        store = CallStore()
        tenant = _tenant()
        for i in range(10):
            store.add(tenant, _record(f"c-{i}"))
        assert len(store.recent(tenant, limit=4)) == 4

    def test_the_summary_counts_only_the_window(self) -> None:
        store = CallStore()
        tenant = _tenant()
        now = datetime.now(UTC)
        store.add(tenant, _record("recent", started_at=now - timedelta(days=1)))
        store.add(tenant, _record("old", started_at=now - timedelta(days=30)))

        assert store.summarize(tenant, window_days=7).calls_answered == 1

    def test_outcomes_are_counted_by_kind(self) -> None:
        store = CallStore()
        tenant = _tenant()
        store.add(tenant, _record("a", outcome=CallOutcome.APPOINTMENT_BOOKED))
        store.add(tenant, _record("b", outcome=CallOutcome.APPOINTMENT_RESCHEDULED))
        store.add(tenant, _record("c", outcome=CallOutcome.APPOINTMENT_CANCELLED))
        store.add(tenant, _record("d", outcome=CallOutcome.ESCALATED))

        summary = store.summarize(tenant)

        assert summary.appointments_booked == 1
        assert summary.appointments_changed == 2
        assert summary.escalated == 1

    def test_escalation_rate_is_none_without_a_sample(self) -> None:
        """A rate over zero calls is not zero percent; it is unknown."""
        assert ActivitySummary(window_days=7).escalation_rate is None

    def test_escalation_rate_is_a_share_of_answered_calls(self) -> None:
        summary = ActivitySummary(window_days=7, calls_answered=4, escalated=1)
        assert summary.escalation_rate == 0.25

    def test_the_summary_carries_no_hours_saved_field(self) -> None:
        """I-02 — no baseline exists, so the figure would be manufactured."""
        assert not any("hours" in f for f in ActivitySummary(window_days=7).__slots__)


class TestErasure:
    def test_erasing_a_transcript_keeps_the_record(self) -> None:
        """DPDP erasure at the right granularity: the words go, the fact stays."""
        store = CallStore()
        tenant = _tenant()
        store.add(tenant, _record("c-1"))
        store.attach_transcript(
            tenant, Transcript("c-1", (TranscriptTurn(Speaker.CALLER, PHI("words")),))
        )

        assert store.erase_transcript(tenant, "c-1")

        assert store.transcript(tenant, "c-1") is None
        assert store.get(tenant, "c-1") is not None
        assert store.get(tenant, "c-1").has_transcript is False

    def test_attaching_marks_the_record_as_having_one(self) -> None:
        store = CallStore()
        tenant = _tenant()
        store.add(tenant, _record("c-1"))

        assert store.get(tenant, "c-1").has_transcript is False
        store.attach_transcript(tenant, Transcript("c-1"))
        assert store.get(tenant, "c-1").has_transcript is True


class TestMessages:
    def test_an_unresolved_message_is_open(self) -> None:
        message = Message("m1", "c-1", "northside", datetime.now(UTC))
        assert message.is_open

    def test_resolving_closes_it_without_deleting(self) -> None:
        store = CallStore()
        tenant = _tenant()
        store.add_message(tenant, Message("m1", "c-1", "northside", datetime.now(UTC)))

        resolved = store.resolve_message(tenant, "m1")

        assert not resolved.is_open
        assert len(store.messages(tenant)) == 1

    def test_open_only_filters(self) -> None:
        store = CallStore()
        tenant = _tenant()
        store.add_message(tenant, Message("m1", "c", "northside", datetime.now(UTC)))
        store.add_message(tenant, Message("m2", "c", "northside", datetime.now(UTC)))
        store.resolve_message(tenant, "m1")

        assert [m.message_id for m in store.messages(tenant, open_only=True)] == ["m2"]

    def test_the_note_stays_wrapped_unless_asked_for(self) -> None:
        message = Message("m1", "c", "northside", datetime.now(UTC), note=PHI("call back Thursday"))
        assert message.summary()["note"] is None
        assert message.summary(reveal_note=True)["note"] == "call back Thursday"

    def test_age_measures_from_when_it_was_taken(self) -> None:
        taken = datetime.now(UTC) - timedelta(hours=5)
        message = Message("m1", "c", "northside", taken)
        assert message.age(now=taken + timedelta(hours=5)) == timedelta(hours=5)

    def test_resolving_an_unknown_message_returns_none(self) -> None:
        assert CallStore().resolve_message(_tenant(), "ghost") is None


class TestRecordingFromACall:
    def _result(self, **kw) -> CallResult:  # noqa: ANN003
        base = {"call_id": "c-1", "tenant_id": "northside", "region": "us", "turns": 3}
        return CallResult(**{**base, **kw})

    def test_an_escalated_call_is_classified_as_escalated(self) -> None:
        assert (
            outcome_for(self._result(escalated=True, escalation_reason="caller_requested_human"))
            is CallOutcome.ESCALATED
        )

    def test_a_dependency_failure_is_classified_as_failed(self) -> None:
        assert (
            outcome_for(self._result(escalated=True, escalation_reason="dependency_failure"))
            is CallOutcome.FAILED
        )

    def test_an_ordinary_call_is_no_action_until_booking_exists(self) -> None:
        """Showing a booking count that nothing produces would be dishonest."""
        assert outcome_for(self._result()) is CallOutcome.NO_ACTION

    def test_recording_stores_the_record_and_the_transcript(self) -> None:
        store = CallStore()
        tenant = _tenant()
        history = [
            Utterance(text=PHI("I need an appointment")),
            Utterance(text=PHI("Of course, what day?")),
        ]

        record = record_call(
            tenant,
            self._result(),
            store,
            history=history,
            caller_number="+15551234541",
            duration_seconds=95.0,
        )

        assert record.has_transcript
        assert store.transcript(tenant, "c-1").rendered()[0]["speaker"] == "caller"
        assert record.caller_masked == "+1555…41"

    def test_the_audit_entry_carries_no_caller_number(self) -> None:
        """C-R2 — the number goes to the record, never to the security log."""
        import tempfile

        store = CallStore()
        tenant = _tenant()
        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(root=tmp)
            record_call(
                tenant,
                self._result(),
                store,
                caller_number="+15551234541",
                duration_seconds=12.0,
                audit=audit,
            )
            entries = list(audit.read(tenant))

        assert entries
        assert "+15551234541" not in str(entries)
        assert entries[0]["caller_ref"].startswith("caller-")

    def test_transcript_speakers_alternate_from_the_caller(self) -> None:
        transcript = transcript_from(
            "c-1", [Utterance(text=PHI("a")), Utterance(text=PHI("b")), Utterance(text=PHI("c"))]
        )
        assert [t.speaker for t in transcript.turns] == [
            Speaker.CALLER,
            Speaker.AGENT,
            Speaker.CALLER,
        ]

    def test_taking_a_message_records_it(self) -> None:
        store = CallStore()
        tenant = _tenant()

        message = take_message(
            tenant, "c-1", store, note="Wants Thursday", caller_number="+15551234541"
        )

        assert message.is_open
        assert store.messages(tenant, open_only=True)[0].message_id == message.message_id
        assert message.summary()["caller_masked"] == "+1555…41"


class TestBookingOutcomes:
    """P7 finally makes `appointment_booked` a real outcome rather than a stub."""

    def _result(self, **kw):  # noqa: ANN003, ANN202
        base = {"call_id": "c-1", "tenant_id": "northside", "region": "us", "turns": 3}
        return CallResult(**{**base, **kw})

    def _appointment(self, status=None):  # noqa: ANN001, ANN202
        from ait_voice.core.scheduling import Appointment, AppointmentStatus

        return Appointment(
            appointment_id="a-1",
            tenant_id="northside",
            starts_at=datetime(2026, 9, 2, 14, 30, tzinfo=UTC),
            status=status or AppointmentStatus.BOOKED,
        )

    def test_a_booking_produces_the_booked_outcome(self) -> None:
        assert outcome_for(self._result(), self._appointment()) is (CallOutcome.APPOINTMENT_BOOKED)

    def test_a_reschedule_produces_the_moved_outcome(self) -> None:
        from ait_voice.core.scheduling import AppointmentStatus

        assert (
            outcome_for(self._result(), self._appointment(AppointmentStatus.RESCHEDULED))
            is CallOutcome.APPOINTMENT_RESCHEDULED
        )

    def test_a_cancellation_produces_the_cancelled_outcome(self) -> None:
        from ait_voice.core.scheduling import AppointmentStatus

        assert (
            outcome_for(self._result(), self._appointment(AppointmentStatus.CANCELLED))
            is CallOutcome.APPOINTMENT_CANCELLED
        )

    def test_an_unmapped_status_does_not_claim_a_booking(self) -> None:
        from ait_voice.core.scheduling import AppointmentStatus

        assert (
            outcome_for(self._result(), self._appointment(AppointmentStatus.NO_SHOW))
            is CallOutcome.NO_ACTION
        )

    def test_escalation_wins_over_a_booking(self) -> None:
        """Somebody still has to pick up the phone; a green tick would hide that."""
        escalated = self._result(escalated=True, escalation_reason="caller_requested_human")

        assert outcome_for(escalated, self._appointment()) is CallOutcome.ESCALATED

    def test_the_record_links_to_the_appointment(self) -> None:
        store = CallStore()
        tenant = _tenant()

        record = record_call(tenant, self._result(), store, appointment=self._appointment())

        assert record.appointment_id == "a-1"
        assert record.outcome is CallOutcome.APPOINTMENT_BOOKED

    def test_the_booking_audit_entry_carries_no_reason(self) -> None:
        """An appointment's reason is why someone is unwell."""
        import tempfile

        from ait_voice.core.scheduling import Appointment

        store = CallStore()
        tenant = _tenant()
        appointment = Appointment(
            appointment_id="a-1",
            tenant_id="northside",
            starts_at=datetime(2026, 9, 2, 14, 30, tzinfo=UTC),
            patient_name=PHI("Priya Sharma"),
            reason=PHI("persistent cough"),
        )

        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(root=tmp)
            record_call(tenant, self._result(), store, appointment=appointment, audit=audit)
            entries = list(audit.read(tenant))

        events = [e["event"] for e in entries]
        assert "appointment_booked" in events
        assert "Priya" not in str(entries)
        assert "cough" not in str(entries)

    def test_a_cancellation_is_audited_as_a_cancellation(self) -> None:
        import tempfile

        from ait_voice.core.scheduling import AppointmentStatus

        store = CallStore()
        tenant = _tenant()

        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(root=tmp)
            record_call(
                tenant,
                self._result(),
                store,
                appointment=self._appointment(AppointmentStatus.CANCELLED),
                audit=audit,
            )
            events = [e["event"] for e in audit.read(tenant)]

        assert "appointment_cancelled" in events

    def test_a_message_is_audited(self) -> None:
        import tempfile

        store = CallStore()
        tenant = _tenant()

        with tempfile.TemporaryDirectory() as tmp:
            audit = AuditLog(root=tmp)
            take_message(tenant, "c-1", store, note="Call back", audit=audit)
            entries = list(audit.read(tenant))

        assert [e["event"] for e in entries] == ["message_taken"]
        assert "Call back" not in str(entries)
