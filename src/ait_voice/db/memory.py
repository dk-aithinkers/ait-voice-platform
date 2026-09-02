"""The in-memory stores, wearing the async interface.

Thin by design and boring on purpose: every method awaits nothing and
translates nothing, it just calls the synchronous store underneath and returns
what it returns. Anything cleverer here would be this layer having behaviour of
its own, which is exactly what must not happen — the point is that
`InMemoryCallStore` and `PostgresCallStore` are indistinguishable to a caller.

**Why this exists rather than making `core/` async.** Several hundred tests pin
the synchronous stores, and they are testing domain behaviour — booking rules,
consent expiry, redaction — none of which is about persistence. Rewriting them
all to `await` would have produced a very large mechanical diff over the tests
that carry the most meaning, and a missed `await` yields a coroutine that is
truthy, so `assert store.get(...)` would keep passing while asserting nothing.
A delegation layer is the cheaper and more honest trade.

**What keeps it honest.** `tests/test_repository_equivalence.py` runs its
contract against three implementations rather than two, so
memory ≡ memory-async ≡ Postgres is a test result and not a claim made here.

Use these for the demo app, for tests that need a working API without a
database, and nowhere else — a real deployment loses every clinic's
configuration, the whole diary and the India consent ledger on restart, which
is the failure the Postgres repositories exist to fix.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ait_voice.core.consent import Consent, ConsentLedger, ConsentPurpose
from ait_voice.core.handoff import (
    HandoffContext,
    HandoffDecision,
    HandoffQueue,
    HandoffRecord,
)
from ait_voice.core.intake import IntakeRecord, IntakeStore
from ait_voice.core.records import (
    ActivitySummary,
    CallRecord,
    CallStore,
    Message,
    Transcript,
)
from ait_voice.core.scheduling import Appointment, BookingHours, Calendar
from ait_voice.core.tenancy import TenantConfig, TenantStore
from ait_voice.core.types import Region, TenantContext


class InMemoryTenantStore:
    """Satisfies :class:`~ait_voice.db.base.TenantRepository`."""

    def __init__(self, inner: TenantStore | None = None) -> None:
        self.inner = inner or TenantStore()

    async def add(self, config: TenantConfig) -> TenantConfig:
        return self.inner.add(config)

    async def get(self, tenant_id: str) -> TenantConfig:
        return self.inner.get(tenant_id)

    async def resolve(self, tenant_id: str) -> TenantContext:
        return self.inner.resolve(tenant_id)

    async def update(self, tenant_id: str, **changes: Any) -> TenantConfig:
        return self.inner.update(tenant_id, **changes)

    async def deactivate(self, tenant_id: str) -> TenantConfig:
        return self.inner.deactivate(tenant_id)

    async def all(self) -> list[TenantConfig]:
        # The sync store expresses this as iteration; the async interface
        # cannot, since __iter__ has no awaitable form. Same data either way.
        return list(self.inner)

    async def active_tenants(self) -> list[TenantConfig]:
        return self.inner.active_tenants()

    async def by_region(self, region: Region) -> list[TenantConfig]:
        return self.inner.by_region(region)

    async def count(self) -> int:
        return len(self.inner)


class InMemoryCallStore:
    """Satisfies :class:`~ait_voice.db.base.CallRepository`."""

    def __init__(self, inner: CallStore | None = None) -> None:
        self.inner = inner or CallStore()

    async def add(self, tenant: TenantContext, record: CallRecord) -> CallRecord:
        return self.inner.add(tenant, record)

    async def get(self, tenant: TenantContext, call_id: str) -> CallRecord | None:
        return self.inner.get(tenant, call_id)

    async def recent(
        self, tenant: TenantContext, *, limit: int = 50, since: datetime | None = None
    ) -> list[CallRecord]:
        return self.inner.recent(tenant, limit=limit, since=since)

    async def count(self, tenant: TenantContext) -> int:
        return self.inner.count(tenant)

    async def attach_transcript(
        self, tenant: TenantContext, transcript: Transcript
    ) -> CallRecord | None:
        return self.inner.attach_transcript(tenant, transcript)

    async def transcript(self, tenant: TenantContext, call_id: str) -> Transcript | None:
        return self.inner.transcript(tenant, call_id)

    async def erase_transcript(self, tenant: TenantContext, call_id: str) -> bool:
        return self.inner.erase_transcript(tenant, call_id)

    async def add_message(self, tenant: TenantContext, message: Message) -> Message:
        return self.inner.add_message(tenant, message)

    async def messages(self, tenant: TenantContext, *, open_only: bool = False) -> list[Message]:
        return self.inner.messages(tenant, open_only=open_only)

    async def resolve_message(
        self, tenant: TenantContext, message_id: str, *, at: datetime | None = None
    ) -> Message | None:
        return self.inner.resolve_message(tenant, message_id, at=at)

    async def summarize(
        self, tenant: TenantContext, *, window_days: int = 7, now: datetime | None = None
    ) -> ActivitySummary:
        return self.inner.summarize(tenant, window_days=window_days, now=now)


class InMemoryCalendar:
    """Satisfies :class:`~ait_voice.db.base.CalendarRepository`."""

    def __init__(self, inner: Calendar | None = None) -> None:
        self.inner = inner or Calendar()

    async def get(self, tenant: TenantContext, appointment_id: str) -> Appointment | None:
        return self.inner.get(tenant, appointment_id)

    async def active(self, tenant: TenantContext) -> list[Appointment]:
        return self.inner.active(tenant)

    async def upcoming(
        self, tenant: TenantContext, *, now: datetime | None = None, limit: int = 50
    ) -> list[Appointment]:
        return self.inner.upcoming(tenant, now=now, limit=limit)

    async def for_caller(self, tenant: TenantContext, caller_ref: str) -> list[Appointment]:
        return self.inner.for_caller(tenant, caller_ref)

    async def is_free(self, tenant: TenantContext, when: datetime) -> bool:
        return self.inner.is_free(tenant, when)

    async def availability(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        *,
        on: datetime | None = None,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[datetime]:
        return self.inner.availability(tenant, config, hours, on=on, now=now, limit=limit)

    async def alternatives(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        around: datetime,
        *,
        now: datetime | None = None,
        count: int = 3,
    ) -> tuple[datetime, ...]:
        return self.inner.alternatives(tenant, config, hours, around, now=now, count=count)

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
    ) -> Appointment:
        return self.inner.book(
            tenant,
            config,
            hours,
            when,
            call_id=call_id,
            caller_ref=caller_ref,
            patient_name=patient_name,
            reason=reason,
            now=now,
        )

    async def reschedule(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        appointment_id: str,
        when: datetime,
        *,
        now: datetime | None = None,
    ) -> Appointment:
        return self.inner.reschedule(tenant, config, hours, appointment_id, when, now=now)

    async def cancel(self, tenant: TenantContext, appointment_id: str) -> Appointment:
        return self.inner.cancel(tenant, appointment_id)


class InMemoryHandoffQueue:
    """Satisfies :class:`~ait_voice.db.base.HandoffRepository`."""

    def __init__(self, inner: HandoffQueue | None = None) -> None:
        self.inner = inner or HandoffQueue()

    async def add(
        self,
        tenant: TenantContext,
        context: HandoffContext,
        decision: HandoffDecision,
        *,
        at: datetime | None = None,
    ) -> HandoffRecord:
        return self.inner.add(tenant, context, decision, at=at)

    async def get(self, tenant: TenantContext, handoff_id: str) -> HandoffRecord | None:
        return self.inner.get(tenant, handoff_id)

    async def pending(self, tenant: TenantContext) -> list[HandoffRecord]:
        return self.inner.pending(tenant)

    async def all(self, tenant: TenantContext) -> list[HandoffRecord]:
        return self.inner.all(tenant)

    async def acknowledge(
        self, tenant: TenantContext, handoff_id: str, *, by: str, at: datetime | None = None
    ) -> HandoffRecord | None:
        return self.inner.acknowledge(tenant, handoff_id, by=by, at=at)


class InMemoryIntakeStore:
    """Satisfies :class:`~ait_voice.db.base.IntakeRepository`."""

    def __init__(self, inner: IntakeStore | None = None) -> None:
        self.inner = inner or IntakeStore()

    async def add(self, tenant: TenantContext, record: IntakeRecord) -> IntakeRecord:
        return self.inner.add(tenant, record)

    async def get(self, tenant: TenantContext, intake_id: str) -> IntakeRecord | None:
        return self.inner.get(tenant, intake_id)

    async def for_call(self, tenant: TenantContext, call_id: str) -> list[IntakeRecord]:
        return self.inner.for_call(tenant, call_id)

    async def recent(self, tenant: TenantContext, *, limit: int = 50) -> list[IntakeRecord]:
        return self.inner.recent(tenant, limit=limit)

    async def erase(self, tenant: TenantContext, intake_id: str) -> bool:
        return self.inner.erase(tenant, intake_id)


class InMemoryConsentLedger:
    """Satisfies :class:`~ait_voice.db.base.ConsentRepository`."""

    def __init__(self, inner: ConsentLedger | None = None) -> None:
        self.inner = inner or ConsentLedger()

    async def grant(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        at: datetime | None = None,
    ) -> Consent:
        return self.inner.grant(tenant, caller_ref, purpose, at=at)

    async def revoke(self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose) -> bool:
        return self.inner.revoke(tenant, caller_ref, purpose)

    async def lookup(
        self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> Consent | None:
        return self.inner.lookup(tenant, caller_ref, purpose)

    async def is_valid(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        now: datetime | None = None,
    ) -> bool:
        return self.inner.is_valid(tenant, caller_ref, purpose, now=now)
