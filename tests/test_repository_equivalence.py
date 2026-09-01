"""One contract, two implementations.

The in-memory stores are what 500-odd tests pin, and the Postgres repositories
are what will actually run. The risk in a swap like this is not that the new
code fails loudly — it is that it behaves *almost* the same, and the difference
surfaces months later in a clinic's diary.

So these tests are written once against a thin uniform facade and run twice:
against the in-memory store and against Postgres. A divergence fails here
rather than in production.

Where the two genuinely differ, the test says so rather than being weakened to
paper over it — see :class:`TestDoubleBookingDiffers`.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest

from ait_voice.core.handoff import (
    HandoffContext,
    HandoffDecision,
    HandoffMethod,
    HandoffQueue,
    Urgency,
)
from ait_voice.core.intake import FieldName, IntakeSession, IntakeStore
from ait_voice.core.records import (
    CallOutcome,
    CallRecord,
    CallStore,
    Message,
    Speaker,
    Transcript,
    TranscriptTurn,
)
from ait_voice.core.scheduling import (
    AppointmentNotFound,
    BookingHours,
    Calendar,
    SlotUnavailable,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region
from ait_voice.db.calls import PostgresCallStore
from ait_voice.db.connection import Database
from ait_voice.db.handoffs import PostgresHandoffQueue
from ait_voice.db.intake import PostgresIntakeStore
from ait_voice.db.scheduling import PostgresCalendar
from tests.conftest import postgres_available

NORTH_CONFIG = TenantConfig(
    tenant_id="northside",
    region=Region.US,
    clinic_name="Northside Medical",
    timezone="America/New_York",
)
NORTH = NORTH_CONFIG.context()
PARK_CONFIG = TenantConfig(tenant_id="parkclinic", region=Region.INDIA, clinic_name="Park Clinic")
PARK = PARK_CONFIG.context()

NOW = datetime(2027, 6, 1, 12, 0, tzinfo=UTC)
#: Wednesday 2027-06-02, 10:30 New York.
SLOT = datetime(2027, 6, 2, 14, 30, tzinfo=UTC)

HOURS = BookingHours()


async def _call(store: Any, method: str, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
    """Invoke a store method whether it is sync (in memory) or async (Postgres).

    The adapter exists so one test body can drive both. It deliberately does no
    translation beyond awaiting — anything else would be the test hiding a
    difference it is supposed to find.
    """
    result = getattr(store, method)(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


# --------------------------------------------------------------------------
# Parameterisation: every test below runs once per implementation.
# --------------------------------------------------------------------------

IMPLEMENTATIONS = ["memory"]
if postgres_available():
    IMPLEMENTATIONS.append("postgres")


@pytest.fixture(params=IMPLEMENTATIONS)
def implementation(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
async def backend(implementation: str, database: Database | None) -> Database | None:
    """The database for this parameterisation, or None for the in-memory run.

    The `database` fixture yields None when Postgres is not configured, so the
    in-memory half runs on a machine with no database — and the Postgres half
    is not generated at all in that case, so nothing silently skips while
    reporting green.
    """
    if implementation != "postgres":
        return None
    assert database is not None, (
        "the postgres parameterisation was generated without a database — "
        "postgres_available() and the database fixture disagree"
    )
    return database


@pytest.fixture
async def seeded_tenants(implementation: str, owner: Database | None) -> None:
    if implementation != "postgres" or owner is None:
        return
    async with owner.unscoped() as c:
        await c.execute(
            """
            INSERT INTO tenants (tenant_id, region, clinic_name, timezone) VALUES
              ('northside','us','Northside Medical','America/New_York'),
              ('parkclinic','india','Park Clinic','Asia/Kolkata')
            ON CONFLICT (tenant_id) DO NOTHING
            """
        )


@pytest.fixture
async def calls(implementation: str, backend: Database | None, seeded_tenants: None) -> Any:  # noqa: ANN401
    if implementation == "memory":
        return CallStore()
    assert backend is not None
    return PostgresCallStore(backend)


@pytest.fixture
async def calendar(implementation: str, backend: Database | None, seeded_tenants: None) -> Any:  # noqa: ANN401
    if implementation == "memory":
        return Calendar()
    assert backend is not None
    return PostgresCalendar(backend)


@pytest.fixture
async def handoffs(implementation: str, backend: Database | None, seeded_tenants: None) -> Any:  # noqa: ANN401
    if implementation == "memory":
        return HandoffQueue()
    assert backend is not None
    return PostgresHandoffQueue(backend)


@pytest.fixture
async def intake(implementation: str, backend: Database | None, seeded_tenants: None) -> Any:  # noqa: ANN401
    if implementation == "memory":
        return IntakeStore()
    assert backend is not None
    return PostgresIntakeStore(backend)


def _record(call_id: str = "c-1", **kw: Any) -> CallRecord:  # noqa: ANN401
    base: dict[str, Any] = {
        "call_id": call_id,
        "tenant_id": "northside",
        "started_at": NOW,
        "duration_seconds": 90.0,
        "turns": 3,
    }
    return CallRecord(**{**base, **kw})


# --------------------------------------------------------------------------


class TestCallRecords:
    async def test_a_record_round_trips(self, calls: Any) -> None:  # noqa: ANN401
        await _call(calls, "add", NORTH, _record(caller=PHI("+15551110041")))

        stored = await _call(calls, "get", NORTH, "c-1")

        assert stored.call_id == "c-1"
        assert stored.caller.reveal() == "+15551110041"
        assert stored.caller_masked == "+1555…41"

    async def test_an_absent_record_is_none(self, calls: Any) -> None:  # noqa: ANN401
        assert await _call(calls, "get", NORTH, "nope") is None

    async def test_one_clinic_cannot_read_anothers(self, calls: Any) -> None:  # noqa: ANN401
        await _call(calls, "add", NORTH, _record("shared-id"))

        assert await _call(calls, "get", NORTH, "shared-id") is not None
        assert await _call(calls, "get", PARK, "shared-id") is None

    async def test_recent_is_newest_first(self, calls: Any) -> None:  # noqa: ANN401
        for i in range(3):
            await _call(
                calls,
                "add",
                NORTH,
                _record(f"c-{i}", started_at=NOW - timedelta(hours=i)),
            )

        found = await _call(calls, "recent", NORTH)

        assert [r.call_id for r in found] == ["c-0", "c-1", "c-2"]

    async def test_recent_respects_the_limit(self, calls: Any) -> None:  # noqa: ANN401
        for i in range(5):
            await _call(calls, "add", NORTH, _record(f"c-{i}"))

        assert len(await _call(calls, "recent", NORTH, limit=2)) == 2

    async def test_the_summary_counts_outcomes(self, calls: Any) -> None:  # noqa: ANN401
        await _call(calls, "add", NORTH, _record("a", outcome=CallOutcome.APPOINTMENT_BOOKED))
        await _call(calls, "add", NORTH, _record("b", outcome=CallOutcome.ESCALATED))
        await _call(calls, "add", NORTH, _record("c", outcome=CallOutcome.APPOINTMENT_CANCELLED))

        summary = await _call(calls, "summarize", NORTH, now=NOW + timedelta(hours=1))

        assert summary.calls_answered == 3
        assert summary.appointments_booked == 1
        assert summary.escalated == 1
        assert summary.appointments_changed == 1

    async def test_the_summary_excludes_calls_outside_the_window(
        self,
        calls: Any,  # noqa: ANN401
    ) -> None:
        await _call(calls, "add", NORTH, _record("recent"))
        await _call(calls, "add", NORTH, _record("old", started_at=NOW - timedelta(days=30)))

        summary = await _call(
            calls, "summarize", NORTH, window_days=7, now=NOW + timedelta(hours=1)
        )

        assert summary.calls_answered == 1

    async def test_an_empty_window_has_no_escalation_rate(self, calls: Any) -> None:  # noqa: ANN401
        """A rate over zero calls is unknown, not zero percent."""
        summary = await _call(calls, "summarize", NORTH, now=NOW)

        assert summary.calls_answered == 0
        assert summary.escalation_rate is None


class TestTranscripts:
    @staticmethod
    def _transcript(call_id: str = "c-1") -> Transcript:
        return Transcript(
            call_id=call_id,
            turns=(
                TranscriptTurn(Speaker.CALLER, PHI("I need to move my appointment")),
                TranscriptTurn(Speaker.AGENT, PHI("Of course, what day?")),
            ),
        )

    async def test_a_transcript_round_trips_in_order(self, calls: Any) -> None:  # noqa: ANN401
        await _call(calls, "add", NORTH, _record())
        await _call(calls, "attach_transcript", NORTH, self._transcript())

        stored = await _call(calls, "transcript", NORTH, "c-1")

        assert [t.speaker for t in stored.turns] == [Speaker.CALLER, Speaker.AGENT]
        assert stored.turns[0].text.reveal() == "I need to move my appointment"

    async def test_attaching_marks_the_record(self, calls: Any) -> None:  # noqa: ANN401
        await _call(calls, "add", NORTH, _record())
        assert (await _call(calls, "get", NORTH, "c-1")).has_transcript is False

        await _call(calls, "attach_transcript", NORTH, self._transcript())

        assert (await _call(calls, "get", NORTH, "c-1")).has_transcript is True

    async def test_attaching_to_another_tenants_call_does_nothing(
        self,
        calls: Any,  # noqa: ANN401
    ) -> None:
        await _call(calls, "add", NORTH, _record())

        assert await _call(calls, "attach_transcript", PARK, self._transcript()) is None
        assert await _call(calls, "transcript", PARK, "c-1") is None

    async def test_erasing_keeps_the_record(self, calls: Any) -> None:  # noqa: ANN401
        """DPDP erasure at the granularity a clinic can live with."""
        await _call(calls, "add", NORTH, _record())
        await _call(calls, "attach_transcript", NORTH, self._transcript())

        assert await _call(calls, "erase_transcript", NORTH, "c-1") is True

        assert await _call(calls, "transcript", NORTH, "c-1") is None
        assert await _call(calls, "get", NORTH, "c-1") is not None
        assert (await _call(calls, "get", NORTH, "c-1")).has_transcript is False

    async def test_a_transcript_is_not_visible_across_tenants(
        self,
        calls: Any,  # noqa: ANN401
    ) -> None:
        await _call(calls, "add", NORTH, _record())
        await _call(calls, "attach_transcript", NORTH, self._transcript())

        assert await _call(calls, "transcript", PARK, "c-1") is None


class TestMessages:
    @staticmethod
    def _message(message_id: str) -> Message:
        import uuid

        return Message(
            message_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, message_id)),
            call_id="c-1",
            tenant_id="northside",
            taken_at=NOW,
            caller=PHI("+15551110055"),
            note=PHI("Wants a call before 5pm"),
        )

    async def test_a_message_round_trips(self, calls: Any) -> None:  # noqa: ANN401
        message = self._message("m1")
        await _call(calls, "add_message", NORTH, message)

        [stored] = await _call(calls, "messages", NORTH)

        assert stored.note.reveal() == "Wants a call before 5pm"
        assert stored.is_open

    async def test_resolving_closes_without_deleting(self, calls: Any) -> None:  # noqa: ANN401
        message = self._message("m1")
        await _call(calls, "add_message", NORTH, message)

        resolved = await _call(calls, "resolve_message", NORTH, message.message_id)

        assert resolved.is_open is False
        assert len(await _call(calls, "messages", NORTH)) == 1

    async def test_open_only_filters(self, calls: Any) -> None:  # noqa: ANN401
        first, second = self._message("m1"), self._message("m2")
        await _call(calls, "add_message", NORTH, first)
        await _call(calls, "add_message", NORTH, second)
        await _call(calls, "resolve_message", NORTH, first.message_id)

        open_messages = await _call(calls, "messages", NORTH, open_only=True)

        assert [m.message_id for m in open_messages] == [second.message_id]

    async def test_resolving_an_unknown_message_is_none(self, calls: Any) -> None:  # noqa: ANN401
        import uuid

        assert await _call(calls, "resolve_message", NORTH, str(uuid.uuid4())) is None

    async def test_one_clinic_cannot_resolve_anothers(self, calls: Any) -> None:  # noqa: ANN401
        message = self._message("m1")
        await _call(calls, "add_message", NORTH, message)

        assert await _call(calls, "resolve_message", PARK, message.message_id) is None
        assert (await _call(calls, "messages", NORTH))[0].is_open


class TestScheduling:
    async def test_a_slot_can_be_booked(self, calendar: Any) -> None:  # noqa: ANN401
        appointment = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        assert appointment.starts_at == SLOT
        assert appointment.spoken(NORTH_CONFIG) == "Wednesday 2 June at 10:30 am"

    async def test_the_same_slot_twice_is_refused_with_alternatives(
        self,
        calendar: Any,  # noqa: ANN401
    ) -> None:
        await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        with pytest.raises(SlotUnavailable) as refusal:
            await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        assert refusal.value.alternatives
        assert SLOT not in refusal.value.alternatives

    async def test_a_closed_day_is_refused(self, calendar: Any) -> None:  # noqa: ANN401
        saturday = datetime(2027, 6, 5, 14, 30, tzinfo=UTC)

        with pytest.raises(SlotUnavailable, match="not open"):
            await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, saturday, now=NOW)

    async def test_a_past_slot_is_refused(self, calendar: Any) -> None:  # noqa: ANN401
        with pytest.raises(SlotUnavailable, match="in the past"):
            await _call(
                calendar,
                "book",
                NORTH,
                NORTH_CONFIG,
                HOURS,
                NOW - timedelta(days=1),
                now=NOW,
            )

    async def test_a_naive_datetime_is_refused(self, calendar: Any) -> None:  # noqa: ANN401
        with pytest.raises(ValueError, match="timezone-aware"):
            await _call(
                calendar,
                "book",
                NORTH,
                NORTH_CONFIG,
                HOURS,
                datetime(2027, 6, 2, 14, 30),
                now=NOW,
            )

    async def test_rescheduling_frees_the_old_slot(self, calendar: Any) -> None:  # noqa: ANN401
        original = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        moved = await _call(
            calendar,
            "reschedule",
            NORTH,
            NORTH_CONFIG,
            HOURS,
            original.appointment_id,
            SLOT + timedelta(hours=2),
            now=NOW,
        )

        assert moved.previous_starts_at == SLOT
        assert await _call(calendar, "is_free", NORTH, SLOT) is True

    async def test_cancelling_frees_the_slot_and_keeps_the_row(
        self,
        calendar: Any,  # noqa: ANN401
    ) -> None:
        original = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        cancelled = await _call(calendar, "cancel", NORTH, original.appointment_id)

        assert cancelled.status.value == "cancelled"
        assert await _call(calendar, "get", NORTH, original.appointment_id) is not None
        assert await _call(calendar, "is_free", NORTH, SLOT) is True

    async def test_a_cancelled_slot_can_be_rebooked(self, calendar: Any) -> None:  # noqa: ANN401
        first = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)
        await _call(calendar, "cancel", NORTH, first.appointment_id)

        second = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        assert second.appointment_id != first.appointment_id

    async def test_cancelling_twice_raises(self, calendar: Any) -> None:  # noqa: ANN401
        original = await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)
        await _call(calendar, "cancel", NORTH, original.appointment_id)

        with pytest.raises(AppointmentNotFound):
            await _call(calendar, "cancel", NORTH, original.appointment_id)

    async def test_a_caller_finds_only_their_own(self, calendar: Any) -> None:  # noqa: ANN401
        mine = await _call(
            calendar,
            "book",
            NORTH,
            NORTH_CONFIG,
            HOURS,
            SLOT,
            caller_ref="caller-abc",
            now=NOW,
        )
        await _call(
            calendar,
            "book",
            NORTH,
            NORTH_CONFIG,
            HOURS,
            SLOT + timedelta(hours=1),
            caller_ref="caller-xyz",
            now=NOW,
        )

        found = await _call(calendar, "for_caller", NORTH, "caller-abc")

        assert [a.appointment_id for a in found] == [mine.appointment_id]

    async def test_an_empty_caller_ref_matches_nothing(self, calendar: Any) -> None:  # noqa: ANN401
        """Matching everything is how the wrong appointment gets cancelled."""
        await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, caller_ref="", now=NOW)

        assert await _call(calendar, "for_caller", NORTH, "") == []

    async def test_two_clinics_may_hold_the_same_slot(self, calendar: Any) -> None:  # noqa: ANN401
        await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)
        await _call(calendar, "book", PARK, PARK_CONFIG, HOURS, SLOT, now=NOW)

        assert len(await _call(calendar, "active", NORTH)) == 1
        assert len(await _call(calendar, "active", PARK)) == 1

    async def test_availability_excludes_booked_slots(self, calendar: Any) -> None:  # noqa: ANN401
        free = await _call(calendar, "availability", NORTH, NORTH_CONFIG, HOURS, now=NOW, limit=1)
        await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, free[0], now=NOW)

        after = await _call(calendar, "availability", NORTH, NORTH_CONFIG, HOURS, now=NOW, limit=5)

        assert free[0] not in after

    async def test_alternatives_are_near_the_request(self, calendar: Any) -> None:  # noqa: ANN401
        await _call(calendar, "book", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        offered = await _call(calendar, "alternatives", NORTH, NORTH_CONFIG, HOURS, SLOT, now=NOW)

        assert all(abs(slot - SLOT) <= timedelta(hours=4) for slot in offered)


class TestHandoffs:
    @staticmethod
    def _context(call_id: str = "c-1", urgency: Urgency = Urgency.ROUTINE) -> HandoffContext:
        return HandoffContext(
            call_id=call_id,
            tenant_id="northside",
            reason="caller_requested_human",
            urgency=urgency,
            caller_number=PHI("+15551110072"),
            said=(PHI("I'd rather talk to a person"),),
            turns=1,
        )

    async def test_a_handoff_round_trips_with_what_was_said(
        self,
        handoffs: Any,  # noqa: ANN401
    ) -> None:
        """C-T6 — the whole point is that the words survive the transfer."""
        record = await _call(
            handoffs,
            "add",
            NORTH,
            self._context(),
            HandoffDecision(HandoffMethod.MESSAGE_TAKEN),
        )

        stored = await _call(handoffs, "get", NORTH, record.handoff_id)

        assert stored.context.for_human()["said"] == ["I'd rather talk to a person"]
        assert stored.is_open

    async def test_urgent_sorts_above_older_routine(self, handoffs: Any) -> None:  # noqa: ANN401
        decision = HandoffDecision(HandoffMethod.MESSAGE_TAKEN)
        await _call(
            handoffs,
            "add",
            NORTH,
            self._context("old", Urgency.ROUTINE),
            decision,
            at=NOW - timedelta(hours=2),
        )
        await _call(
            handoffs,
            "add",
            NORTH,
            self._context("clinical", Urgency.CLINICAL),
            decision,
            at=NOW,
        )

        pending = await _call(handoffs, "pending", NORTH)

        assert [r.context.call_id for r in pending] == ["clinical", "old"]

    async def test_equal_urgency_is_oldest_first(self, handoffs: Any) -> None:  # noqa: ANN401
        decision = HandoffDecision(HandoffMethod.MESSAGE_TAKEN)
        await _call(handoffs, "add", NORTH, self._context("second"), decision, at=NOW)
        await _call(
            handoffs,
            "add",
            NORTH,
            self._context("first"),
            decision,
            at=NOW - timedelta(hours=1),
        )

        pending = await _call(handoffs, "pending", NORTH)

        assert [r.context.call_id for r in pending] == ["first", "second"]

    async def test_acknowledging_closes_without_deleting(self, handoffs: Any) -> None:  # noqa: ANN401
        record = await _call(
            handoffs,
            "add",
            NORTH,
            self._context(),
            HandoffDecision(HandoffMethod.MESSAGE_TAKEN),
        )

        acknowledged = await _call(
            handoffs, "acknowledge", NORTH, record.handoff_id, by="reception"
        )

        assert acknowledged.is_open is False
        assert acknowledged.acknowledged_by == "reception"
        assert await _call(handoffs, "pending", NORTH) == []
        assert len(await _call(handoffs, "all", NORTH)) == 1

    async def test_one_clinic_cannot_acknowledge_anothers(
        self,
        handoffs: Any,  # noqa: ANN401
    ) -> None:
        record = await _call(
            handoffs,
            "add",
            NORTH,
            self._context(),
            HandoffDecision(HandoffMethod.MESSAGE_TAKEN),
        )

        assert await _call(handoffs, "acknowledge", PARK, record.handoff_id, by="them") is None
        assert (await _call(handoffs, "get", NORTH, record.handoff_id)).is_open

    async def test_one_clinic_cannot_see_anothers(self, handoffs: Any) -> None:  # noqa: ANN401
        await _call(
            handoffs,
            "add",
            NORTH,
            self._context(),
            HandoffDecision(HandoffMethod.MESSAGE_TAKEN),
        )

        assert await _call(handoffs, "pending", PARK) == []


class TestIntake:
    @staticmethod
    def _record() -> Any:  # noqa: ANN401
        session = IntakeSession()
        for name, answer in (
            (FieldName.FULL_NAME, "Priya Sharma"),
            (FieldName.DATE_OF_BIRTH, "1985-03-04"),
            (FieldName.CALLBACK_NUMBER, "+15551234541"),
            (FieldName.REASON_FOR_VISIT, "knee follow-up"),
        ):
            if session.capture(name, answer):
                session.confirm(name)
        return session.completed(call_id="c-1", tenant_id="northside")

    async def test_intake_round_trips(self, intake: Any) -> None:  # noqa: ANN401
        record = self._record()
        await _call(intake, "add", NORTH, record)

        stored = await _call(intake, "get", NORTH, record.intake_id)

        assert stored.get(FieldName.FULL_NAME) == "Priya Sharma"

    async def test_a_date_survives_as_a_date(self, intake: Any) -> None:  # noqa: ANN401
        """Returning a string here would quietly change what callers receive."""
        from datetime import date

        record = self._record()
        await _call(intake, "add", NORTH, record)

        stored = await _call(intake, "get", NORTH, record.intake_id)

        assert stored.get(FieldName.DATE_OF_BIRTH) == date(1985, 3, 4)

    async def test_it_can_be_found_by_call(self, intake: Any) -> None:  # noqa: ANN401
        record = self._record()
        await _call(intake, "add", NORTH, record)

        found = await _call(intake, "for_call", NORTH, "c-1")

        assert [r.intake_id for r in found] == [record.intake_id]
        assert await _call(intake, "for_call", NORTH, "other") == []

    async def test_erasure_removes_it(self, intake: Any) -> None:  # noqa: ANN401
        record = self._record()
        await _call(intake, "add", NORTH, record)

        assert await _call(intake, "erase", NORTH, record.intake_id) is True
        assert await _call(intake, "get", NORTH, record.intake_id) is None

    async def test_one_clinic_cannot_read_or_erase_anothers(
        self,
        intake: Any,  # noqa: ANN401
    ) -> None:
        record = self._record()
        await _call(intake, "add", NORTH, record)

        assert await _call(intake, "get", PARK, record.intake_id) is None
        assert await _call(intake, "erase", PARK, record.intake_id) is False
        assert await _call(intake, "get", NORTH, record.intake_id) is not None

    async def test_the_summary_carries_no_values(self, intake: Any) -> None:  # noqa: ANN401
        record = self._record()
        await _call(intake, "add", NORTH, record)

        stored = await _call(intake, "get", NORTH, record.intake_id)

        assert "Priya" not in str(stored.summary())
        assert "full_name" in str(stored.summary())


@pytest.fixture
async def tenants(implementation: str, backend: Database | None) -> Any:  # noqa: ANN401
    from ait_voice.core.tenancy import TenantStore
    from ait_voice.db.tenants import PostgresTenantStore

    if implementation == "memory":
        return TenantStore()
    assert backend is not None
    return PostgresTenantStore(backend)


@pytest.fixture
async def consent(implementation: str, backend: Database | None) -> Any:  # noqa: ANN401
    from ait_voice.core.consent import ConsentLedger
    from ait_voice.db.consent import PostgresConsentLedger

    if implementation == "memory":
        return ConsentLedger()
    assert backend is not None
    return PostgresConsentLedger(backend)


class TestTenants:
    """The registry. Deliberately the one table without row-level security."""

    async def test_a_tenant_round_trips(self, tenants: Any) -> None:  # noqa: ANN401
        await _call(tenants, "add", NORTH_CONFIG)

        stored = await _call(tenants, "get", "northside")

        assert stored.clinic_name == "Northside Medical"
        assert stored.region is Region.US
        assert stored.timezone == "America/New_York"

    async def test_staffed_hours_survive_the_round_trip(self, tenants: Any) -> None:  # noqa: ANN401
        """A clinic's opening hours are the thing a wrong column type eats."""
        from ait_voice.core.tenancy import StaffedHours

        config = NORTH_CONFIG.with_changes(
            staffed_hours=StaffedHours(
                days=frozenset({1, 3, 5}), opens=time(8, 30), closes=time(18, 0)
            )
        )
        await _call(tenants, "add", config)

        stored = await _call(tenants, "get", "northside")

        assert stored.staffed_hours.days == frozenset({1, 3, 5})
        assert stored.staffed_hours.opens == time(8, 30)
        assert stored.staffed_hours.closes == time(18, 0)

    async def test_languages_survive_as_a_tuple(self, tenants: Any) -> None:  # noqa: ANN401
        await _call(tenants, "add", PARK_CONFIG.with_changes(languages=("en", "hi", "hi-en")))

        stored = await _call(tenants, "get", "parkclinic")

        assert stored.languages == ("en", "hi", "hi-en")

    async def test_an_unknown_tenant_raises(self, tenants: Any) -> None:  # noqa: ANN401
        from ait_voice.core.tenancy import TenantNotFoundError

        with pytest.raises(TenantNotFoundError):
            await _call(tenants, "get", "nobody")

    async def test_resolve_refuses_an_inactive_tenant(self, tenants: Any) -> None:  # noqa: ANN401
        from ait_voice.core.tenancy import TenantNotFoundError

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(tenants, "deactivate", "northside")

        with pytest.raises(TenantNotFoundError, match="not active"):
            await _call(tenants, "resolve", "northside")

    async def test_deactivating_does_not_delete(self, tenants: Any) -> None:  # noqa: ANN401
        """Deleting would cascade to the clinic's call records."""
        await _call(tenants, "add", NORTH_CONFIG)
        await _call(tenants, "deactivate", "northside")

        assert (await _call(tenants, "get", "northside")).active is False

    async def test_update_changes_one_field(self, tenants: Any) -> None:  # noqa: ANN401
        await _call(tenants, "add", NORTH_CONFIG)

        updated = await _call(tenants, "update", "northside", greeting="Good morning.")

        assert updated.greeting == "Good morning."
        assert updated.clinic_name == "Northside Medical"

    async def test_tenants_can_be_listed_by_region(self, tenants: Any) -> None:  # noqa: ANN401
        await _call(tenants, "add", NORTH_CONFIG)
        await _call(tenants, "add", PARK_CONFIG)

        assert len(await _call(tenants, "by_region", Region.US)) == 1
        assert len(await _call(tenants, "by_region", Region.INDIA)) == 1

    async def test_active_tenants_excludes_deactivated(self, tenants: Any) -> None:  # noqa: ANN401
        await _call(tenants, "add", NORTH_CONFIG)
        await _call(tenants, "add", PARK_CONFIG)
        await _call(tenants, "deactivate", "parkclinic")

        active = await _call(tenants, "active_tenants")

        assert [c.tenant_id for c in active] == ["northside"]


class TestConsent:
    """C-R9. The property that must survive the move is *when* expiry is
    evaluated: at read time, from the grant date and region — never stamped
    into a column, which would be a second copy of a rule that can disagree
    with itself."""

    async def test_a_grant_round_trips(self, consent: Any, tenants: Any) -> None:  # noqa: ANN401
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(
            consent,
            "grant",
            NORTH,
            "caller-abc",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        stored = await _call(
            consent, "lookup", NORTH, "caller-abc", ConsentPurpose.APPOINTMENT_REMINDER
        )

        assert stored.granted_at == NOW
        assert stored.region is Region.US

    async def test_us_consent_has_no_fixed_lifetime(
        self,
        consent: Any,
        tenants: Any,  # noqa: ANN401
    ) -> None:
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(
            consent,
            "grant",
            NORTH,
            "caller-abc",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        stored = await _call(
            consent, "lookup", NORTH, "caller-abc", ConsentPurpose.APPOINTMENT_REMINDER
        )

        assert stored.expires_at is None

    async def test_india_consent_expires_after_seven_days(
        self,
        consent: Any,
        tenants: Any,  # noqa: ANN401
    ) -> None:
        """The rule C-R9 exists for, computed rather than stored."""
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", PARK_CONFIG)
        await _call(
            consent,
            "grant",
            PARK,
            "caller-xyz",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        stored = await _call(
            consent, "lookup", PARK, "caller-xyz", ConsentPurpose.APPOINTMENT_REMINDER
        )

        assert stored.expires_at == NOW + timedelta(days=7)
        assert stored.is_valid(now=NOW + timedelta(days=6)) is True
        assert stored.is_valid(now=NOW + timedelta(days=8)) is False

    async def test_validity_is_evaluated_at_read_time(
        self,
        consent: Any,
        tenants: Any,  # noqa: ANN401
    ) -> None:
        """The same stored row is valid on day six and expired on day eight,
        with nothing written in between."""
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", PARK_CONFIG)
        await _call(
            consent,
            "grant",
            PARK,
            "caller-xyz",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        assert await _call(
            consent,
            "is_valid",
            PARK,
            "caller-xyz",
            ConsentPurpose.APPOINTMENT_REMINDER,
            now=NOW + timedelta(days=6),
        )
        assert not await _call(
            consent,
            "is_valid",
            PARK,
            "caller-xyz",
            ConsentPurpose.APPOINTMENT_REMINDER,
            now=NOW + timedelta(days=8),
        )

    async def test_consent_is_per_purpose(self, consent: Any, tenants: Any) -> None:  # noqa: ANN401
        """Consent is never general."""
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(
            consent,
            "grant",
            NORTH,
            "caller-abc",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        assert (
            await _call(consent, "lookup", NORTH, "caller-abc", ConsentPurpose.CALL_RECORDING)
            is None
        )

    async def test_revoking_removes_it(self, consent: Any, tenants: Any) -> None:  # noqa: ANN401
        """Withdrawal is always available, in every jurisdiction."""
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(
            consent,
            "grant",
            NORTH,
            "caller-abc",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        assert (
            await _call(consent, "revoke", NORTH, "caller-abc", ConsentPurpose.APPOINTMENT_REMINDER)
            is True
        )
        assert (
            await _call(consent, "lookup", NORTH, "caller-abc", ConsentPurpose.APPOINTMENT_REMINDER)
            is None
        )

    async def test_one_clinic_cannot_see_anothers_consent(
        self,
        consent: Any,
        tenants: Any,  # noqa: ANN401
    ) -> None:
        from ait_voice.core.consent import ConsentPurpose

        await _call(tenants, "add", NORTH_CONFIG)
        await _call(tenants, "add", PARK_CONFIG)
        await _call(
            consent,
            "grant",
            NORTH,
            "caller-abc",
            ConsentPurpose.APPOINTMENT_REMINDER,
            at=NOW,
        )

        assert (
            await _call(consent, "lookup", PARK, "caller-abc", ConsentPurpose.APPOINTMENT_REMINDER)
            is None
        )
