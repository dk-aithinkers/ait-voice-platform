"""Call records, transcripts and messages — what the clinic actually sees.

P8 in the backlog, and the recorded prerequisite for P9: *"the clinic view has
nothing to show without call records."*

The split from :mod:`ait_voice.core.audit` is the same one that resolves the
C-R7 / C-R8 contradiction, applied one layer up. A :class:`CallRecord` is a
business record — what happened on a call, how long it took, what came of it.
The audit log is a security record and stays PHI-free. Transcripts are content
and live in the erasable store. Three things, three lifetimes:

- **Audit entries** — retained a year or more, never erased, no personal data.
- **Call records** — the clinic's operational history. Carries the caller's
  number, so it is PHI and erasable with the rest.
- **Transcripts** — content, erasable, never listed in bulk.

A record is deliberately *summary-shaped*. Listing a hundred calls should not
load a hundred transcripts into memory, and a screen that shows a list has no
business holding the words.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ait_voice.core.tenancy import TenantScoped
from ait_voice.core.types import PHI, TenantContext

#: How many leading characters of a phone number stay visible.
#: The country and area code are deliberately legible: a receptionist
#: recognising a local number is the point of showing it at all, and an area
#: code alone does not identify anyone. Everything between that and the last
#: two digits is masked.
MASK_PREFIX = 5
MASK_SUFFIX = 2


class CallOutcome(StrEnum):
    """What came of a call. Closed vocabulary, safe to log and aggregate."""

    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_RESCHEDULED = "appointment_rescheduled"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    MESSAGE_TAKEN = "message_taken"
    ESCALATED = "escalated"
    NO_ACTION = "no_action"
    FAILED = "failed"


class Speaker(StrEnum):
    AGENT = "agent"
    CALLER = "caller"


def mask_number(number: str) -> str:
    """Partially mask a phone number for display.

    The wireframes call for this on every list view. Masking here rather than
    in the UI means a client that forgets to mask cannot leak the number — it
    never receives it.
    """
    if not number:
        return ""
    compact = re.sub(r"\s+", "", number)
    if len(compact) <= MASK_PREFIX + MASK_SUFFIX:
        return "…" + compact[-MASK_SUFFIX:]
    return f"{compact[:MASK_PREFIX]}…{compact[-MASK_SUFFIX:]}"


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    """One line of a conversation. Content, therefore PHI."""

    speaker: Speaker
    text: PHI[str]
    at_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class CallRecord:
    """A call's business summary. No transcript — see :class:`Transcript`."""

    call_id: str
    tenant_id: str
    started_at: datetime
    duration_seconds: float = 0.0
    turns: int = 0
    outcome: CallOutcome = CallOutcome.NO_ACTION
    language: str = "en"
    #: The caller's number. PHI (a listed identifier), so wrapped; the UI is
    #: served :attr:`caller_masked` instead.
    caller: PHI[str] | None = None
    #: Tenant-salted hash, for correlating a caller across calls without
    #: storing who they are. Matches the audit log's reference for this caller.
    caller_ref: str = ""
    escalation_reason: str | None = None
    escalation_route: str | None = None
    p95_ms: float | None = None
    #: False when the transport could not observe time to first audio, so a
    #: latency figure shown against this call would be a floor rather than a
    #: measurement. Carried through to the UI rather than dropped.
    latency_observable: bool = True
    has_transcript: bool = False

    @property
    def caller_masked(self) -> str:
        return mask_number(self.caller.reveal()) if self.caller else "unknown"

    @property
    def escalated(self) -> bool:
        return self.outcome is CallOutcome.ESCALATED

    def summary(self) -> dict[str, object]:
        """The shape a list view needs. Contains no unmasked PHI."""
        return {
            "call_id": self.call_id,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 1),
            "turns": self.turns,
            "outcome": str(self.outcome),
            "language": self.language,
            "caller_masked": self.caller_masked,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "has_transcript": self.has_transcript,
            "p95_ms": round(self.p95_ms, 1) if self.p95_ms is not None else None,
            "latency_observable": self.latency_observable,
        }


@dataclass(frozen=True, slots=True)
class Transcript:
    """A call's words. Content, erasable, never returned in a list."""

    call_id: str
    turns: tuple[TranscriptTurn, ...] = ()

    def rendered(self) -> list[dict[str, str]]:
        """Reveal the text for a detail view.

        The only place PHI is deliberately unwrapped. Callers are the call
        detail endpoint and the content store, both of which have already
        established that this tenant may see this call.
        """
        return [
            {"speaker": str(turn.speaker), "text": turn.text.reveal()}
            for turn in self.turns
        ]


@dataclass(frozen=True, slots=True)
class Message:
    """A callback the agent promised on the clinic's behalf.

    The wireframes put this on both surfaces deliberately: the clinic carries
    the obligation, and the operator carries the responsibility for noticing it
    is unmet. An unresolved message is a promise a patient is waiting on.
    """

    message_id: str
    call_id: str
    tenant_id: str
    taken_at: datetime
    caller: PHI[str] | None = None
    note: PHI[str] | None = None
    resolved_at: datetime | None = None

    @property
    def is_open(self) -> bool:
        return self.resolved_at is None

    def age(self, *, now: datetime | None = None) -> timedelta:
        return (now or datetime.now(UTC)) - self.taken_at

    def summary(self, *, reveal_note: bool = False) -> dict[str, object]:
        """List shape. The note stays wrapped unless explicitly asked for."""
        return {
            "message_id": self.message_id,
            "call_id": self.call_id,
            "taken_at": self.taken_at.isoformat(),
            "caller_masked": mask_number(self.caller.reveal())
            if self.caller
            else "unknown",
            "note": self.note.reveal() if (reveal_note and self.note) else None,
            "is_open": self.is_open,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass(frozen=True, slots=True)
class ActivitySummary:
    """The clinic view's top tiles.

    Every field here is a **counted fact**. There is deliberately no
    hours-saved figure: RAID item I-02 records that the success metrics carry
    no baseline and no measurement window, and this project's practice forbids
    producing a figure the evidence cannot support. Calls answered is counted;
    hours saved would be derived from a baseline nobody has taken.
    """

    window_days: int
    calls_answered: int = 0
    appointments_booked: int = 0
    appointments_changed: int = 0
    escalated: int = 0
    messages_open: int = 0
    average_duration_seconds: float = 0.0

    @property
    def escalation_rate(self) -> float | None:
        """Share of calls handed to a person. None when there is no sample."""
        if not self.calls_answered:
            return None
        return self.escalated / self.calls_answered


class CallStore:
    """Tenant-partitioned storage for records, transcripts and messages.

    Built on :class:`~ait_voice.core.tenancy.TenantScoped`, so one clinic's
    calls are physically separate from another's rather than filtered apart.
    Every method takes tenant context first, per the affirmed convention.
    """

    def __init__(self) -> None:
        self._records: TenantScoped[CallRecord] = TenantScoped()
        self._transcripts: TenantScoped[Transcript] = TenantScoped()
        self._messages: TenantScoped[Message] = TenantScoped()

    # -- records ---------------------------------------------------------

    def add(self, tenant: TenantContext, record: CallRecord) -> CallRecord:
        return self._records.put(tenant, record.call_id, record)

    def get(self, tenant: TenantContext, call_id: str) -> CallRecord | None:
        return self._records.get(tenant, call_id)

    def recent(
        self, tenant: TenantContext, *, limit: int = 50, since: datetime | None = None
    ) -> list[CallRecord]:
        """Most recent calls first — the order every screen wants."""
        records = self._records.values(tenant)
        if since:
            records = [r for r in records if r.started_at >= since]
        return sorted(records, key=lambda r: r.started_at, reverse=True)[:limit]

    def count(self, tenant: TenantContext) -> int:
        return self._records.count(tenant)

    # -- transcripts -----------------------------------------------------

    def attach_transcript(
        self, tenant: TenantContext, transcript: Transcript
    ) -> CallRecord | None:
        """Store a transcript and mark its record as having one.

        Returns the updated record, or None when no such call exists for this
        tenant — which is also what a cross-tenant attempt gets.
        """
        record = self.get(tenant, transcript.call_id)
        if record is None:
            return None
        self._transcripts.put(tenant, transcript.call_id, transcript)
        updated = replace_record(record, has_transcript=True)
        return self._records.put(tenant, record.call_id, updated)

    def transcript(self, tenant: TenantContext, call_id: str) -> Transcript | None:
        return self._transcripts.get(tenant, call_id)

    def erase_transcript(self, tenant: TenantContext, call_id: str) -> bool:
        """Delete a call's words, keeping the record that the call happened.

        DPDP erasure applied at the right granularity: the clinic keeps its
        operational history and the patient's words are gone.
        """
        removed = self._transcripts.delete(tenant, call_id)
        if record := self.get(tenant, call_id):
            self._records.put(
                tenant, call_id, replace_record(record, has_transcript=False)
            )
        return removed

    # -- messages --------------------------------------------------------

    def add_message(self, tenant: TenantContext, message: Message) -> Message:
        return self._messages.put(tenant, message.message_id, message)

    def messages(
        self, tenant: TenantContext, *, open_only: bool = False
    ) -> list[Message]:
        found = self._messages.values(tenant)
        if open_only:
            found = [m for m in found if m.is_open]
        return sorted(found, key=lambda m: m.taken_at, reverse=True)

    def resolve_message(
        self, tenant: TenantContext, message_id: str, *, at: datetime | None = None
    ) -> Message | None:
        message = self._messages.get(tenant, message_id)
        if message is None:
            return None
        from dataclasses import replace

        resolved = replace(message, resolved_at=at or datetime.now(UTC))
        return self._messages.put(tenant, message_id, resolved)

    # -- aggregates ------------------------------------------------------

    def summarize(
        self,
        tenant: TenantContext,
        *,
        window_days: int = 7,
        now: datetime | None = None,
    ) -> ActivitySummary:
        """Counted facts over a window. Nothing derived, nothing modelled."""
        cutoff = (now or datetime.now(UTC)) - timedelta(days=window_days)
        records = [r for r in self._records.values(tenant) if r.started_at >= cutoff]
        durations = [r.duration_seconds for r in records]
        changed = {
            CallOutcome.APPOINTMENT_RESCHEDULED,
            CallOutcome.APPOINTMENT_CANCELLED,
        }
        return ActivitySummary(
            window_days=window_days,
            calls_answered=len(records),
            appointments_booked=sum(
                1 for r in records if r.outcome is CallOutcome.APPOINTMENT_BOOKED
            ),
            appointments_changed=sum(1 for r in records if r.outcome in changed),
            escalated=sum(1 for r in records if r.escalated),
            messages_open=len(self.messages(tenant, open_only=True)),
            average_duration_seconds=(sum(durations) / len(durations))
            if durations
            else 0.0,
        )

    def __iter__(self) -> Iterator[str]:
        raise TypeError(
            "CallStore is not iterable without tenant context. Use recent(tenant)."
        )


def replace_record(record: CallRecord, **changes: object) -> CallRecord:
    from dataclasses import replace

    return replace(record, **changes)
