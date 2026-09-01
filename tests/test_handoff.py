"""Structured human handoff (P5, FR5.1–FR5.6, C-T6).

`user-flow.md` calls this "the most consequential flow in the product", and
`market-trends.md` found patient acceptance depends on a human being reachable
rather than on the technology. So the tests here are about whether a person
picking up the call actually knows anything — and about the two payloads, since
one crosses a vendor boundary and the other does not.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from ait_voice.core.handoff import (
    CLINICAL_REASONS,
    HandoffContext,
    HandoffDecision,
    HandoffMethod,
    HandoffQueue,
    Urgency,
    decide_handoff,
    spoken_promise,
    urgency_for,
)
from ait_voice.core.tenancy import OutOfHoursPolicy, StaffedHours, TenantConfig
from ait_voice.core.types import PHI, Region

ALWAYS = StaffedHours(days=frozenset(range(1, 8)), opens=time(0, 0), closes=time(23, 59))
WEDNESDAY = datetime(2026, 9, 2, 14, 0, tzinfo=UTC)


def _config(
    *,
    hours: StaffedHours | None = None,
    number: str | None = "+15551230000",
    policy: OutOfHoursPolicy = OutOfHoursPolicy.TAKE_MESSAGE,
    tenant_id: str = "northside",
) -> TenantConfig:
    return TenantConfig(
        tenant_id=tenant_id,
        region=Region.US,
        clinic_name="Northside",
        staffed_hours=hours if hours is not None else ALWAYS,
        escalation_number=number,
        out_of_hours=policy,
    )


def _context(**kw) -> HandoffContext:  # noqa: ANN003
    base = {
        "call_id": "c-1",
        "tenant_id": "northside",
        "reason": "caller_requested_human",
    }
    return HandoffContext(**{**base, **kw})


class TestAvailabilityDecision:
    """ "Is a human available now?" — the question the flow calls unobvious."""

    def test_a_staffed_clinic_with_a_number_transfers(self) -> None:
        decision = decide_handoff(_config(), now=WEDNESDAY)

        assert decision.method is HandoffMethod.TRANSFERRED
        assert decision.transfer_to == "+15551230000"

    def test_an_unstaffed_clinic_takes_a_message(self) -> None:
        decision = decide_handoff(_config(hours=StaffedHours.never()), now=WEDNESDAY)

        assert decision.method is HandoffMethod.MESSAGE_TAKEN
        assert decision.transfer_to is None

    def test_a_policy_is_not_mistaken_for_a_phone_number(self) -> None:
        """OutOfHoursPolicy is a StrEnum, so `isinstance(route, str)` is True
        for it as well as for a number. Testing the policy first is what makes
        this a real discrimination rather than one branch that always wins."""
        decision = decide_handoff(_config(hours=StaffedHours.never()), now=WEDNESDAY)

        assert decision.method is not HandoffMethod.TRANSFERRED
        assert decision.transfer_to != "take_message"

    def test_an_after_hours_service_is_its_own_method(self) -> None:
        decision = decide_handoff(
            _config(
                hours=StaffedHours.never(),
                policy=OutOfHoursPolicy.EXISTING_AFTER_HOURS,
            ),
            now=WEDNESDAY,
        )

        assert decision.method is HandoffMethod.EXISTING_SERVICE

    def test_staffed_with_no_number_takes_a_message(self) -> None:
        """Dialling nothing rings in an empty room, and the caller hears it."""
        decision = decide_handoff(_config(number=None), now=WEDNESDAY)

        assert decision.method is HandoffMethod.MESSAGE_TAKEN


class TestSpokenPromise:
    def test_a_transfer_says_it_is_putting_them_through(self) -> None:
        promise = spoken_promise(HandoffDecision(HandoffMethod.TRANSFERRED, transfer_to="+1555"))
        assert "put you through" in promise.lower()

    def test_the_callback_is_worded_as_the_clinic_calling(self) -> None:
        """The obligation is the clinic's; nothing here can discharge it."""
        promise = spoken_promise(HandoffDecision(HandoffMethod.MESSAGE_TAKEN))

        assert "clinic will call you back" in promise.lower()
        assert "i will call" not in promise.lower()

    def test_the_after_hours_service_is_named_as_the_clinics(self) -> None:
        promise = spoken_promise(HandoffDecision(HandoffMethod.EXISTING_SERVICE))
        assert "out-of-hours" in promise.lower()


class TestUrgency:
    def test_clinical_content_goes_to_the_top(self) -> None:
        """Not triage — the agent cannot triage. Precisely why it goes first."""
        assert urgency_for("clinical_content") is Urgency.CLINICAL

    def test_a_dependency_failure_is_urgent(self) -> None:
        """That caller got an apology and nothing else."""
        assert urgency_for("dependency_failure") is Urgency.URGENT

    def test_an_ordinary_request_is_routine(self) -> None:
        assert urgency_for("caller_requested_human") is Urgency.ROUTINE

    def test_clinical_reasons_are_data_not_scattered_conditionals(self) -> None:
        assert "clinical_content" in CLINICAL_REASONS


class TestTwoPayloads:
    """The distinction that makes the vendor boundary safe."""

    def test_the_human_briefing_reveals_what_the_caller_said(self) -> None:
        context = _context(
            said=(PHI("I need to move my appointment"), PHI("Thursday if possible")),
            caller_number=PHI("+15551234541"),
        )

        briefing = context.for_human()

        assert briefing["said"] == [
            "I need to move my appointment",
            "Thursday if possible",
        ]
        assert briefing["caller_number"] == "+15551234541"

    def test_the_vendor_payload_carries_no_phi(self) -> None:
        """handoffData crosses a vendor boundary whose BAA is unconfirmed."""
        context = _context(
            said=(PHI("I've had chest pain since this morning"),),
            caller_number=PHI("+15551234541"),
            caller_ref="caller-abc",
        )

        payload = context.for_vendor()
        rendered = str(payload)

        assert "chest pain" not in rendered
        assert "+15551234541" not in rendered
        assert "said" not in payload
        assert payload["caller_ref"] == "caller-abc"

    def test_the_vendor_payload_still_says_enough_to_route(self) -> None:
        payload = _context(reason="clinical_content").for_vendor()

        assert payload["reason"] == "clinical_content"
        assert payload["urgency"] in {u.value for u in Urgency}

    def test_they_are_separate_methods_not_a_flag(self) -> None:
        """A flag is something you can forget to pass at the one call site
        where it matters."""
        assert callable(HandoffContext.for_human)
        assert callable(HandoffContext.for_vendor)


class TestQueue:
    def test_a_handoff_is_recorded(self) -> None:
        queue = HandoffQueue()
        tenant = _config().context()

        record = queue.add(tenant, _context(), HandoffDecision(HandoffMethod.MESSAGE_TAKEN))

        assert record.is_open
        assert queue.pending(tenant) == [record]

    def test_urgent_calls_come_before_older_routine_ones(self) -> None:
        """A clinic working down the list should reach the clinical caller first."""
        queue = HandoffQueue()
        tenant = _config().context()
        decision = HandoffDecision(HandoffMethod.MESSAGE_TAKEN)

        queue.add(
            tenant,
            _context(call_id="old", urgency=Urgency.ROUTINE),
            decision,
            at=WEDNESDAY - timedelta(hours=2),
        )
        queue.add(
            tenant,
            _context(call_id="clinical", urgency=Urgency.CLINICAL),
            decision,
            at=WEDNESDAY,
        )

        assert [r.context.call_id for r in queue.pending(tenant)] == ["clinical", "old"]

    def test_equal_urgency_is_ordered_oldest_first(self) -> None:
        queue = HandoffQueue()
        tenant = _config().context()
        decision = HandoffDecision(HandoffMethod.MESSAGE_TAKEN)

        queue.add(tenant, _context(call_id="second"), decision, at=WEDNESDAY)
        queue.add(
            tenant,
            _context(call_id="first"),
            decision,
            at=WEDNESDAY - timedelta(hours=1),
        )

        assert [r.context.call_id for r in queue.pending(tenant)] == ["first", "second"]

    def test_acknowledging_closes_without_deleting(self) -> None:
        """The record is how a clinic learns a handoff went unanswered."""
        queue = HandoffQueue()
        tenant = _config().context()
        record = queue.add(tenant, _context(), HandoffDecision(HandoffMethod.MESSAGE_TAKEN))

        acknowledged = queue.acknowledge(tenant, record.handoff_id, by="reception")

        assert not acknowledged.is_open
        assert acknowledged.acknowledged_by == "reception"
        assert queue.pending(tenant) == []
        assert len(queue.all(tenant)) == 1

    def test_acknowledging_an_unknown_handoff_returns_none(self) -> None:
        assert HandoffQueue().acknowledge(_config().context(), "ghost", by="reception") is None

    def test_the_queue_summary_carries_no_phi(self) -> None:
        queue = HandoffQueue()
        tenant = _config().context()
        record = queue.add(
            tenant,
            _context(said=(PHI("I've had chest pain"),), caller_number=PHI("+15551234541")),
            HandoffDecision(HandoffMethod.MESSAGE_TAKEN),
        )

        assert "chest pain" not in str(record.summary())
        assert "+15551234541" not in str(record.summary())

    def test_one_clinic_cannot_see_anothers_handoffs(self) -> None:
        queue = HandoffQueue()
        north, park = _config().context(), _config(tenant_id="parkclinic").context()
        queue.add(north, _context(), HandoffDecision(HandoffMethod.MESSAGE_TAKEN))

        assert len(queue.pending(north)) == 1
        assert queue.pending(park) == []

    def test_one_clinic_cannot_acknowledge_anothers_handoff(self) -> None:
        queue = HandoffQueue()
        north, park = _config().context(), _config(tenant_id="parkclinic").context()
        record = queue.add(north, _context(), HandoffDecision(HandoffMethod.MESSAGE_TAKEN))

        assert queue.acknowledge(park, record.handoff_id, by="them") is None
        assert queue.get(north, record.handoff_id).is_open
