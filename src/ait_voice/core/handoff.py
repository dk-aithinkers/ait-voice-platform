"""Handing a call to a person, with what the caller already said.

P5, and constraint C-T6 makes it Firm rather than nice: `market-trends.md`
found that patient acceptance of a voice agent depends on the presence of a
human, not on the technology. A transfer that makes the caller repeat
everything spends the one thing that earns acceptance.

`user-flow.md` calls this "the most consequential flow in the product" and
gives it a shape this module implements literally:

    Escalation triggered -> is a human available now?
        yes -> transfer with context
        no  -> take a structured message, and promise a callback

**Two payloads, deliberately.** The context a human reads carries PHI: what the
caller said, their number, why they are calling. The context handed to a
telephony vendor carries none — opaque references and enumerated codes only.
They are separate methods rather than one method with a flag, because the
difference is a compliance boundary and a flag is something you can forget to
pass. See :meth:`HandoffContext.for_human` and :meth:`HandoffContext.for_vendor`.

**The summary is not composed at handoff time.** AC5.5.1 gives three seconds
from failure to spoken apology, and a model round-trip inside that budget is a
risk taken for a convenience. The context is assembled from what the call
already has; a written summary can be attached afterwards, when nobody is
waiting on it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from ait_voice.core.tenancy import OutOfHoursPolicy, TenantConfig, TenantScoped
from ait_voice.core.types import PHI, TenantContext


class Urgency(StrEnum):
    """How fast a person needs to reach this caller.

    Ordered, and the ordering is load-bearing: the callback queue is sorted by
    it, so a clinic working down the list reaches the urgent caller first even
    if they rang last.
    """

    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"
    #: Clinical content the agent is forbidden to engage with. Not a triage
    #: judgement — the agent cannot make one — but a signal that a person must
    #: look at this before anything else in the queue.
    CLINICAL = "clinical"


#: Sort weight. Higher means sooner.
_URGENCY_ORDER = {
    Urgency.ROUTINE: 0,
    Urgency.SOON: 1,
    Urgency.URGENT: 2,
    Urgency.CLINICAL: 3,
}

#: Escalation reasons that are clinical by definition. Kept as data rather than
#: an `if` in three places, so adding a reason cannot miss one of them.
CLINICAL_REASONS = frozenset({"clinical_content"})


class HandoffMethod(StrEnum):
    """How the call actually left the agent."""

    #: A person was available and the call was transferred to them.
    TRANSFERRED = "transferred"
    #: Nobody was available; a structured message entered the clinic's queue.
    MESSAGE_TAKEN = "message_taken"
    #: The clinic's own after-hours arrangement took it.
    EXISTING_SERVICE = "existing_after_hours"


class UnresolvedCall(RuntimeError):
    """A call was about to end without a task, a transfer, or a message.

    FR5.6 says that must never happen. Raising here converts a silent product
    failure — a caller hung up on with nothing recorded — into a loud one.
    """


@dataclass(frozen=True, slots=True)
class HandoffContext:
    """Everything a person needs to pick this call up mid-conversation."""

    call_id: str
    tenant_id: str
    reason: str
    urgency: Urgency = Urgency.ROUTINE
    caller_ref: str = ""
    #: A listed identifier, so wrapped. The human sees it; the vendor does not.
    caller_number: PHI[str] | None = None
    #: What the caller actually said, in order. The point of the whole feature.
    said: tuple[PHI[str], ...] = ()
    turns: int = 0
    recovery_attempted: bool = False
    #: Appointments this call created or touched, so the person is not told
    #: about a booking the caller has already been given.
    appointment_ids: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_clinical(self) -> bool:
        return self.urgency is Urgency.CLINICAL

    def for_human(self) -> dict[str, object]:
        """The briefing a person reads. Contains PHI by design.

        Served only to an authenticated principal scoped to this tenant. This
        is the one place the caller's words are deliberately revealed, because
        withholding them is the failure the feature exists to prevent.
        """
        return {
            "call_id": self.call_id,
            "reason": self.reason,
            "urgency": str(self.urgency),
            "turns": self.turns,
            "recovery_attempted": self.recovery_attempted,
            "started_at": self.started_at.isoformat(),
            "caller_number": self.caller_number.reveal() if self.caller_number else None,
            "said": [utterance.reveal() for utterance in self.said],
            "appointment_ids": list(self.appointment_ids),
        }

    def for_vendor(self) -> dict[str, object]:
        """The payload handed to a telephony vendor. Carries no PHI.

        Twilio ConversationRelay's ``handoffData`` crosses a vendor boundary,
        and whether it is covered depends on an executed BAA and an edition
        this project has not yet confirmed. Sending opaque references and
        enumerated codes costs nothing here — the human reads the real briefing
        from our own surface, authenticated and tenant-scoped — and removes the
        question entirely.
        """
        return {
            "call_id": self.call_id,
            "tenant_id": self.tenant_id,
            "caller_ref": self.caller_ref,
            "reason": self.reason,
            "urgency": str(self.urgency),
            "turns": self.turns,
            "has_appointment": bool(self.appointment_ids),
        }


def urgency_for(reason: str, *, clinical_reasons: frozenset[str] = CLINICAL_REASONS) -> Urgency:
    """Classify how quickly a person is needed.

    Deliberately coarse. The agent is forbidden from assessing symptoms
    (FR5.2), so this is not triage: clinical content goes to the top of the
    queue precisely *because* nobody here is qualified to decide it can wait.
    """
    if reason in clinical_reasons:
        return Urgency.CLINICAL
    if reason == "dependency_failure":
        # The caller got an apology and nothing else. They are owed a person
        # sooner than someone whose booking simply needs confirming.
        return Urgency.URGENT
    return Urgency.ROUTINE


@dataclass(frozen=True, slots=True)
class HandoffDecision:
    """Where this call goes, and why.

    ``method`` answers "is a human available now?" — the question `user-flow.md`
    records as having no obvious answer. Here it is answered from the clinic's
    configured staffed hours and escalation number, which is the honest
    available answer: a live presence check needs a presence to check, and no
    clinic has one wired.
    """

    method: HandoffMethod
    transfer_to: str | None = None
    policy: OutOfHoursPolicy | None = None

    @property
    def is_transfer(self) -> bool:
        return self.method is HandoffMethod.TRANSFERRED


def decide_handoff(
    config: TenantConfig, *, now: datetime | None = None
) -> HandoffDecision:
    """Transfer if a person is there; otherwise take a message."""
    route = config.escalation_route(now)
    # Order matters, and not for style: OutOfHoursPolicy is a StrEnum, so
    # `isinstance(route, str)` is True for a policy as well as for a phone
    # number. Testing for the policy first is what makes this a real
    # discrimination rather than one branch that always wins.
    if isinstance(route, OutOfHoursPolicy):
        if route is OutOfHoursPolicy.EXISTING_AFTER_HOURS:
            return HandoffDecision(
                method=HandoffMethod.EXISTING_SERVICE, policy=route
            )
        # TRANSFER_ANYWAY with no number configured also lands here. A message
        # is the safe failure: dialling nothing rings in an empty room, and the
        # caller would hear it.
        return HandoffDecision(method=HandoffMethod.MESSAGE_TAKEN, policy=route)
    if route:
        return HandoffDecision(method=HandoffMethod.TRANSFERRED, transfer_to=route)
    return HandoffDecision(method=HandoffMethod.MESSAGE_TAKEN)


def spoken_promise(decision: HandoffDecision) -> str:
    """What the caller is told.

    The callback line is an obligation on the clinic that nothing in this
    system can discharge — `user-flow.md` is explicit that it should not be
    spoken until a clinic has agreed to answer it. It is worded as the clinic
    calling back, not as the agent arranging anything, because the agent
    cannot.
    """
    if decision.is_transfer:
        return "Let me put you through to someone now."
    if decision.method is HandoffMethod.EXISTING_SERVICE:
        return "Let me pass you to the clinic's out-of-hours service."
    return (
        "There's nobody available right now. I've taken a note and someone "
        "from the clinic will call you back."
    )


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """A handoff that happened, and whether anyone has picked it up.

    Kept separate from :class:`~ait_voice.core.records.Message` on purpose. A
    message is a callback obligation; a handoff record is the briefing plus the
    decision that produced it. A transferred call has a record and no message.
    """

    handoff_id: str
    context: HandoffContext
    decision: HandoffDecision
    at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None

    @property
    def is_open(self) -> bool:
        return self.acknowledged_at is None

    @property
    def sort_key(self) -> tuple[int, datetime]:
        """Most urgent first, then oldest first within an urgency."""
        return (-_URGENCY_ORDER[self.context.urgency], self.at)

    def summary(self) -> dict[str, object]:
        """Queue shape. No PHI — the briefing is fetched per record."""
        return {
            "handoff_id": self.handoff_id,
            "call_id": self.context.call_id,
            "reason": self.context.reason,
            "urgency": str(self.context.urgency),
            "method": str(self.decision.method),
            "at": self.at.isoformat(),
            "is_open": self.is_open,
            "acknowledged_at": self.acknowledged_at.isoformat()
            if self.acknowledged_at
            else None,
            "turns": self.context.turns,
        }


class HandoffQueue:
    """Tenant-partitioned handoff records."""

    def __init__(self) -> None:
        self._records: TenantScoped[HandoffRecord] = TenantScoped()

    def add(
        self,
        tenant: TenantContext,
        context: HandoffContext,
        decision: HandoffDecision,
        *,
        at: datetime | None = None,
    ) -> HandoffRecord:
        record = HandoffRecord(
            handoff_id=str(uuid.uuid4()),
            context=context,
            decision=decision,
            at=at or datetime.now(UTC),
        )
        return self._records.put(tenant, record.handoff_id, record)

    def get(self, tenant: TenantContext, handoff_id: str) -> HandoffRecord | None:
        return self._records.get(tenant, handoff_id)

    def pending(self, tenant: TenantContext) -> list[HandoffRecord]:
        """Open handoffs, most urgent first.

        Urgency before recency: a clinic working down this list should reach
        the clinical caller before the routine one who rang earlier.
        """
        return sorted(
            (r for r in self._records.values(tenant) if r.is_open),
            key=lambda r: r.sort_key,
        )

    def all(self, tenant: TenantContext) -> list[HandoffRecord]:
        return sorted(self._records.values(tenant), key=lambda r: r.at, reverse=True)

    def acknowledge(
        self,
        tenant: TenantContext,
        handoff_id: str,
        *,
        by: str,
        at: datetime | None = None,
    ) -> HandoffRecord | None:
        """Mark that a person has picked this up. Never deletes.

        The record is how the clinic learns a handoff went unanswered, so
        removing it on acknowledgement would delete the evidence of the thing
        worth measuring.
        """
        record = self._records.get(tenant, handoff_id)
        if record is None:
            return None
        acknowledged = replace(
            record,
            acknowledged_at=at or datetime.now(UTC),
            acknowledged_by=by,
        )
        return self._records.put(tenant, handoff_id, acknowledged)
