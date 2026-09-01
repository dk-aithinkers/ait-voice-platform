"""Multi-tenancy: tenant configuration, and isolation that cannot be forgotten.

Built in-house because constraint C-T4 leaves no choice — no managed voice
platform offers native multi-tenancy, and the market's own workaround is
third-party wrapper products. If the tenant layer must be built regardless,
building it on infrastructure we control is strictly better.

Affirmed at scope definition as day-one work rather than a later addition. With
PHI in scope the isolation boundary is a **compliance surface**, not only an
engineering one: a missing tenant filter is a cross-tenant patient-data
disclosure, which is a breach rather than a defect.

**How isolation is enforced here.** Not by remembering to add a `WHERE
tenant_id = ?` clause. Two mechanisms instead:

1. :class:`TenantScoped` physically partitions storage per tenant, so there is
   no shared collection to forget to filter. Reaching another tenant's data
   requires their :class:`TenantContext`, which a request handler does not have.
2. Every accessor takes :class:`TenantContext` as its first parameter, per the
   affirmed convention, so omission is a type error rather than a runtime
   surprise.

The second is the convention. The first is what makes the convention hard to
violate even deliberately.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Generic, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ait_voice.core.types import Region, TenantContext

T = TypeVar("T")


class OutOfHoursPolicy(StrEnum):
    """What happens when the agent must escalate and nobody is there.

    Decided at rough mockups. "Transfer to a human" silently assumes a human
    exists, and with 24/7 answering in scope that is false for most of the day —
    so the policy is configured per tenant rather than assumed.
    """

    #: Attempt the transfer regardless. Honest only if the number is genuinely
    #: staffed around the clock.
    TRANSFER_ANYWAY = "transfer_anyway"
    #: Take a message and promise a callback. Note this creates an obligation on
    #: the clinic, not on the agent — nothing in this system can fulfil it.
    TAKE_MESSAGE = "take_message"
    #: Hand off to whatever the clinic already does after hours.
    EXISTING_AFTER_HOURS = "existing_after_hours"


class TenantNotFoundError(KeyError):
    """Raised when a tenant id does not resolve."""


class CrossTenantAccessError(RuntimeError):
    """Raised when one tenant's context is used to reach another's data.

    Should be unreachable through the public API. It exists because "should be
    unreachable" is a claim worth having a test for.
    """


@dataclass(frozen=True, slots=True)
class StaffedHours:
    """When a human is actually available to receive a transfer.

    Weekdays are ISO: Monday is 1, Sunday is 7. A tenant with no staffed days is
    never staffed, which is the correct default — assuming someone is there is
    how a caller ends up transferred into a ringing empty room.
    """

    days: frozenset[int] = frozenset()
    opens: time = time(9, 0)
    closes: time = time(17, 0)

    def is_staffed(self, when: datetime, *, tz: ZoneInfo | None = None) -> bool:
        """Whether someone is available at this moment, in the clinic's own time.

        The conversion is the whole point. Staffed hours are written the way a
        clinic says them — "nine to five" — which is nine to five *there*.
        Comparing a UTC instant against those numbers puts a US clinic's front
        desk five to eight hours away from where it actually is, and once
        appointments are being booked that is not a display bug, it is a patient
        told to arrive at half past five in the morning.
        """
        local = when.astimezone(tz) if tz else when
        if local.isoweekday() not in self.days:
            return False
        return self.opens <= local.time() < self.closes

    @classmethod
    def weekdays(cls, opens: time = time(9, 0), closes: time = time(17, 0)) -> StaffedHours:
        return cls(days=frozenset({1, 2, 3, 4, 5}), opens=opens, closes=closes)

    @classmethod
    def never(cls) -> StaffedHours:
        """No staffed hours. Every escalation follows the out-of-hours policy."""
        return cls(days=frozenset())


@dataclass(frozen=True, slots=True)
class TenantConfig:
    """Everything that differs between one clinic and another.

    Frozen. Changes produce a new config via :meth:`with_changes` rather than
    mutating one another request may be holding.
    """

    tenant_id: str
    region: Region
    clinic_name: str
    #: Greeting spoken after the mandatory disclosure. The disclosure itself is
    #: not configurable — see the note on `full_greeting`.
    greeting: str = "How can I help?"
    staffed_hours: StaffedHours = field(default_factory=StaffedHours.weekdays)
    escalation_number: str | None = None
    out_of_hours: OutOfHoursPolicy = OutOfHoursPolicy.TAKE_MESSAGE
    languages: tuple[str, ...] = ("en",)
    #: IANA zone. Staffed hours and appointment times are read in this zone;
    #: everything is stored as an absolute instant.
    timezone: str = "UTC"
    #: DLT registration and 1600-series numbering, for India outbound (C-R6).
    outbound_registered: bool = False
    active: bool = True

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id must not be empty")
        if not self.languages:
            raise ValueError("at least one language is required")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            # Rejected at construction rather than at the first booking, when
            # the consequence is a patient given the wrong hour.
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def local(self, when: datetime | None = None) -> datetime:
        """An instant expressed in the clinic's own time."""
        return (when or datetime.now(UTC)).astimezone(self.tz)

    def context(self) -> TenantContext:
        """The context passed to everything that touches this tenant's data."""
        return TenantContext(
            tenant_id=self.tenant_id,
            region=self.region,
            outbound_registered=self.outbound_registered,
        )

    def with_changes(self, **changes: object) -> TenantConfig:
        return replace(self, **changes)

    def is_staffed(self, when: datetime | None = None) -> bool:
        return self.staffed_hours.is_staffed(when or datetime.now(UTC), tz=self.tz)

    def escalation_route(self, when: datetime | None = None) -> OutOfHoursPolicy | str:
        """Where an escalation goes right now.

        Returns the escalation number when a human is available, and the
        configured out-of-hours policy otherwise. A staffed tenant with no
        number configured is treated as unstaffed — a transfer target that does
        not exist is worse than admitting nobody is there.
        """
        if self.is_staffed(when) and self.escalation_number:
            return self.escalation_number
        return self.out_of_hours


class TenantStore:
    """The tenant registry.

    Deliberately not tenant-scoped itself: this is the one place that knows
    about all tenants, which is what makes every *other* store able to know
    about exactly one.
    """

    def __init__(self) -> None:
        self._configs: dict[str, TenantConfig] = {}

    def add(self, config: TenantConfig) -> TenantConfig:
        self._configs[config.tenant_id] = config
        return config

    def get(self, tenant_id: str) -> TenantConfig:
        try:
            return self._configs[tenant_id]
        except KeyError:
            raise TenantNotFoundError(tenant_id) from None

    def resolve(self, tenant_id: str) -> TenantContext:
        """Tenant id to context. The entry point for any inbound request."""
        config = self.get(tenant_id)
        if not config.active:
            raise TenantNotFoundError(f"{tenant_id} is not active")
        return config.context()

    def update(self, tenant_id: str, **changes: object) -> TenantConfig:
        return self.add(self.get(tenant_id).with_changes(**changes))

    def deactivate(self, tenant_id: str) -> TenantConfig:
        """Stop a tenant answering, without deleting anything.

        Deletion would take the audit log with it, and the audit log is the
        thing that must be retained.
        """
        return self.update(tenant_id, active=False)

    def __len__(self) -> int:
        return len(self._configs)

    def __iter__(self) -> Iterator[TenantConfig]:
        return iter(self._configs.values())

    @property
    def active_tenants(self) -> list[TenantConfig]:
        return [c for c in self._configs.values() if c.active]

    def by_region(self, region: Region) -> list[TenantConfig]:
        return [c for c in self._configs.values() if c.region is region]


class TenantScoped(Generic[T]):
    """Per-tenant storage with no shared collection to forget to filter.

    Every method takes :class:`TenantContext` first and can only ever see that
    tenant's partition. There is no "all records" accessor, because the moment
    one exists somebody filters it by hand and eventually gets it wrong.

    This is the mechanism behind the affirmed convention. The convention says
    pass tenant context explicitly; this makes doing so the only thing that
    works.
    """

    def __init__(self) -> None:
        self._partitions: dict[str, dict[str, T]] = {}

    def _partition(self, tenant: TenantContext) -> dict[str, T]:
        return self._partitions.setdefault(tenant.tenant_id, {})

    def put(self, tenant: TenantContext, key: str, value: T) -> T:
        self._partition(tenant)[key] = value
        return value

    def get(self, tenant: TenantContext, key: str) -> T | None:
        return self._partition(tenant).get(key)

    def require(self, tenant: TenantContext, key: str) -> T:
        value = self.get(tenant, key)
        if value is None:
            raise KeyError(f"{key!r} not found for tenant {tenant.tenant_id!r}")
        return value

    def delete(self, tenant: TenantContext, key: str) -> bool:
        return self._partition(tenant).pop(key, None) is not None

    def keys(self, tenant: TenantContext) -> list[str]:
        return list(self._partition(tenant))

    def values(self, tenant: TenantContext) -> list[T]:
        return list(self._partition(tenant).values())

    def count(self, tenant: TenantContext) -> int:
        return len(self._partition(tenant))

    def clear(self, tenant: TenantContext) -> int:
        """Remove everything for one tenant. Never touches another's partition."""
        removed = len(self._partition(tenant))
        self._partitions[tenant.tenant_id] = {}
        return removed


def assert_same_tenant(expected: TenantContext, actual: TenantContext) -> None:
    """Guard for anywhere two contexts meet.

    Called where a record carries its own tenant id and is about to be handed
    to a caller holding a different one — the shape of bug that becomes a
    disclosure rather than a wrong answer.
    """
    if expected.tenant_id != actual.tenant_id:
        raise CrossTenantAccessError(
            f"tenant {actual.tenant_id!r} attempted to reach data belonging to "
            f"tenant {expected.tenant_id!r}"
        )
