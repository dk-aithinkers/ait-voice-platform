"""Storage protocols: one async interface, two implementations behind it.

The same move `providers/base.py` makes for vendors, made for persistence. The
in-memory stores in `core/` are what several hundred tests pin; the Postgres
repositories are what actually runs. Production code should be unable to tell
them apart, and — more importantly — should be unable to accidentally depend on
the in-memory one.

These protocols are what makes that true. :class:`~ait_voice.api.app.Services`
is typed against them, so under `mypy --strict` handing it a synchronous
:class:`~ait_voice.core.records.CallStore` is a type error rather than a
deployment that quietly loses every call on restart.

**Why async is the shared shape rather than sync.** Postgres is async and
cannot be made otherwise; memory can be either. So the interface takes the
shape the constrained side requires, and the unconstrained side adapts — see
:mod:`ait_voice.db.memory`. The alternative, an adapter at each call site that
awaits only when it must, is precisely the "behaves *almost* the same" failure
`tests/test_repository_equivalence.py` exists to catch.

Structural, not nominal: nothing inherits from these. `PostgresCallStore`
already satisfies :class:`CallRepository` without knowing it exists, which is
what keeps the protocol honest — it describes the implementations rather than
constraining them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from ait_voice.core.audit import AuditEntry, AuditEvent
from ait_voice.core.consent import Consent, ConsentPurpose
from ait_voice.core.handoff import HandoffContext, HandoffDecision, HandoffRecord
from ait_voice.core.intake import IntakeRecord
from ait_voice.core.records import ActivitySummary, CallRecord, Message, Transcript
from ait_voice.core.scheduling import Appointment, BookingHours
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region, TenantContext


@runtime_checkable
class AuditSink(Protocol):
    """The immutable security record — C-R7, and the P3 audit requirement.

    Two implementations with genuinely different guarantees, which is why this
    protocol exists rather than one class with a flag.
    :class:`~ait_voice.core.audit.AuditLog` appends JSON lines to local disk and
    is single-writer by construction; :class:`~ait_voice.db.s3_audit.S3AuditLog`
    is what a deployment uses, where immutability is enforced by S3 Object Lock
    rather than by our own good intentions.

    `read` returns a list rather than yielding, because the S3 sink pages over
    objects and cannot stream lazily without holding a connection open for the
    life of the iteration.
    """

    async def record(
        self,
        tenant: TenantContext,
        event: AuditEvent,
        *,
        call_id: str | None = None,
        caller_ref: str | None = None,
        **detail: str | int | float | bool,
    ) -> AuditEntry: ...
    async def read(self, tenant: TenantContext) -> list[dict[str, Any]]: ...
    async def verify(self, tenant: TenantContext) -> bool: ...


@runtime_checkable
class ContentSink(Protocol):
    """Transcripts and recordings — the erasable half, and never the audit log.

    C-R8 requires personal data erased once its purpose is fulfilled, which is
    why this is a different store with a different lifetime from
    :class:`AuditSink`. The two obligations in `project.md` only both hold
    because they apply to disjoint data.

    :meth:`store` returns an opaque locator rather than a path. The filesystem
    implementation returns a path and the S3 one returns a URI; a caller that
    treats either as a filesystem path is reaching through the boundary, and
    typing it as `str` is what stops that being convenient.
    """

    async def store(
        self,
        tenant: TenantContext,
        call_id: str,
        transcript: list[PHI[str]],
        *,
        audit: AuditSink | None = None,
    ) -> str: ...
    async def erase(
        self,
        tenant: TenantContext,
        call_id: str,
        *,
        audit: AuditSink | None = None,
        reason: str = "purpose_fulfilled",
    ) -> bool: ...
    async def exists(self, tenant: TenantContext, call_id: str) -> bool: ...


@runtime_checkable
class TenantRepository(Protocol):
    """The clinic registry.

    The one store whose methods take no :class:`TenantContext`: it is the
    registry that knows about every clinic, which is what lets every other
    store know about exactly one. It holds no patient data.
    """

    async def add(self, config: TenantConfig) -> TenantConfig: ...
    async def get(self, tenant_id: str) -> TenantConfig: ...
    async def resolve(self, tenant_id: str) -> TenantContext: ...
    async def update(self, tenant_id: str, **changes: Any) -> TenantConfig: ...
    async def deactivate(self, tenant_id: str) -> TenantConfig: ...
    async def all(self) -> list[TenantConfig]: ...
    async def active_tenants(self) -> list[TenantConfig]: ...
    async def by_region(self, region: Region) -> list[TenantConfig]: ...
    async def count(self) -> int: ...

    # Inbound routing: the number a caller dialled, to the clinic that answers
    # it. Lives on the registry rather than on TenantConfig because it is a
    # routing table with a uniqueness constraint, not a per-clinic setting.
    async def claim_number(
        self, tenant_id: str, number: str, *, label: str | None = None
    ) -> str: ...
    async def release_number(self, number: str) -> bool: ...
    async def numbers(self, tenant_id: str) -> list[str]: ...
    async def resolve_number(self, number: str) -> TenantContext: ...


@runtime_checkable
class CallRepository(Protocol):
    """Call records, transcripts and callback messages.

    Three lifetimes behind one interface: a record is a business record, a
    transcript is erasable content, and neither is the audit log — see
    :mod:`ait_voice.core.audit` for why that separation is load bearing.
    """

    async def add(self, tenant: TenantContext, record: CallRecord) -> CallRecord: ...
    async def get(self, tenant: TenantContext, call_id: str) -> CallRecord | None: ...
    async def recent(
        self, tenant: TenantContext, *, limit: int = 50, since: datetime | None = None
    ) -> list[CallRecord]: ...
    async def count(self, tenant: TenantContext) -> int: ...
    async def attach_transcript(
        self, tenant: TenantContext, transcript: Transcript
    ) -> CallRecord | None: ...
    async def transcript(self, tenant: TenantContext, call_id: str) -> Transcript | None: ...
    async def erase_transcript(self, tenant: TenantContext, call_id: str) -> bool: ...
    async def add_message(self, tenant: TenantContext, message: Message) -> Message: ...
    async def messages(
        self, tenant: TenantContext, *, open_only: bool = False
    ) -> list[Message]: ...
    async def resolve_message(
        self, tenant: TenantContext, message_id: str, *, at: datetime | None = None
    ) -> Message | None: ...
    async def summarize(
        self, tenant: TenantContext, *, window_days: int = 7, now: datetime | None = None
    ) -> ActivitySummary: ...


@runtime_checkable
class CalendarRepository(Protocol):
    """The agent's own diary.

    `book` is the method where the two implementations differ most and agree
    anyway: memory holds an in-process lock, Postgres holds a partial unique
    index. Both raise :class:`~ait_voice.core.scheduling.SlotUnavailable`
    carrying alternatives, so a caller cannot tell which layer refused them.
    """

    async def get(self, tenant: TenantContext, appointment_id: str) -> Appointment | None: ...
    async def active(self, tenant: TenantContext) -> list[Appointment]: ...
    async def upcoming(
        self, tenant: TenantContext, *, now: datetime | None = None, limit: int = 50
    ) -> list[Appointment]: ...
    async def for_caller(self, tenant: TenantContext, caller_ref: str) -> list[Appointment]: ...
    async def is_free(self, tenant: TenantContext, when: datetime) -> bool: ...
    async def availability(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        *,
        on: datetime | None = None,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[datetime]: ...
    async def alternatives(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        around: datetime,
        *,
        now: datetime | None = None,
        count: int = 3,
    ) -> tuple[datetime, ...]: ...
    async def book(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        when: datetime,
        *,
        call_id: str | None = None,
        caller_ref: str = "",
        patient_name: str | None = None,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> Appointment: ...
    async def reschedule(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        appointment_id: str,
        when: datetime,
        *,
        now: datetime | None = None,
    ) -> Appointment: ...
    async def cancel(self, tenant: TenantContext, appointment_id: str) -> Appointment: ...


@runtime_checkable
class HandoffRepository(Protocol):
    """Calls waiting for a person, with what the caller already said."""

    async def add(
        self,
        tenant: TenantContext,
        context: HandoffContext,
        decision: HandoffDecision,
        *,
        at: datetime | None = None,
    ) -> HandoffRecord: ...
    async def get(self, tenant: TenantContext, handoff_id: str) -> HandoffRecord | None: ...
    async def pending(self, tenant: TenantContext) -> list[HandoffRecord]: ...
    async def all(self, tenant: TenantContext) -> list[HandoffRecord]: ...
    async def acknowledge(
        self, tenant: TenantContext, handoff_id: str, *, by: str, at: datetime | None = None
    ) -> HandoffRecord | None: ...


@runtime_checkable
class IntakeRepository(Protocol):
    """Structured intake captured over voice. Every value is PHI."""

    async def add(self, tenant: TenantContext, record: IntakeRecord) -> IntakeRecord: ...
    async def get(self, tenant: TenantContext, intake_id: str) -> IntakeRecord | None: ...
    async def for_call(self, tenant: TenantContext, call_id: str) -> list[IntakeRecord]: ...
    async def recent(self, tenant: TenantContext, *, limit: int = 50) -> list[IntakeRecord]: ...
    async def erase(self, tenant: TenantContext, intake_id: str) -> bool: ...


@runtime_checkable
class ConsentRepository(Protocol):
    """Consent, and the fact that it expires.

    Expiry is evaluated at read time from the grant date and region, never
    stamped into a column — a stored `expires_at` is a second copy of a rule
    that can disagree with itself. C-R9.
    """

    async def grant(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        at: datetime | None = None,
    ) -> Consent: ...
    async def revoke(
        self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> bool: ...
    async def lookup(
        self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> Consent | None: ...
    async def is_valid(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        now: datetime | None = None,
    ) -> bool: ...
