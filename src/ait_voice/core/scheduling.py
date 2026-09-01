"""The agent's own calendar — booking, rescheduling, cancelling.

P7. Scoped deliberately: `requirements.md` records that FR2 operates against
the **agent-owned calendar only**, and that the system *"shall not read from or
write to any external clinical or practice-management system."* EHR integration
is P13, a fast-follow, and R-02's fallback position is exactly this module.

Two properties are load-bearing.

**Double booking must be impossible, not unlikely.** Two callers reaching the
agent at the same moment is the normal case, not an edge case — 24/7 answering
with simultaneous callers is the capability P6 exists to provide. So a slot is
claimed atomically: :meth:`Calendar.book` either takes the slot or raises, and
never returns a booking that a concurrent call also holds. The in-memory
implementation uses a lock; a database implementation needs a unique constraint
on (tenant, slot) and must not lose that property in translation.

**Times are clinic-local at the edges and absolute inside.** Everything is
stored as a UTC instant. Everything a caller hears, and every availability
window, is computed in the clinic's own zone. Getting this backwards means
telling a patient to arrive at an hour the clinic is shut.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum

from ait_voice.core.tenancy import TenantConfig, TenantScoped
from ait_voice.core.types import PHI, TenantContext

#: Appointment lengths are a per-clinic setting; this is the default when none
#: is configured, and it is a common consultation length rather than a claim.
DEFAULT_SLOT_MINUTES = 30

#: How far ahead the agent will offer. Beyond this the clinic's own plans are
#: too uncertain for a phone agent to commit on their behalf.
DEFAULT_HORIZON_DAYS = 30


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class SlotUnavailable(RuntimeError):
    """The requested time is not bookable.

    Carries alternatives, because FR2.5 requires the agent to offer them and a
    refusal with nothing to offer ends a call in the one way the acceptance
    criteria forbid: *"does not end the call without either booking or
    escalating."*
    """

    def __init__(self, message: str, alternatives: tuple[datetime, ...] = ()) -> None:
        super().__init__(message)
        self.alternatives = alternatives


class AppointmentNotFound(KeyError):
    """No such appointment for this tenant."""


@dataclass(frozen=True, slots=True)
class BookingHours:
    """When a clinic accepts appointments, in its own local time.

    Distinct from :class:`~ait_voice.core.tenancy.StaffedHours`, which is about
    whether a human can take a *transfer*. A clinic can be bookable all week and
    have nobody on the phone at 3am; conflating the two would either refuse
    valid bookings or transfer callers into an empty room.
    """

    days: frozenset[int] = frozenset({1, 2, 3, 4, 5})
    opens: time = time(9, 0)
    closes: time = time(17, 0)
    slot_minutes: int = DEFAULT_SLOT_MINUTES

    def __post_init__(self) -> None:
        if self.slot_minutes <= 0:
            raise ValueError("slot_minutes must be positive")
        if self.opens >= self.closes:
            raise ValueError("opens must be before closes")

    def is_open(self, local: datetime) -> bool:
        if local.isoweekday() not in self.days:
            return False
        return self.opens <= local.time() < self.closes

    def slots_on(self, local_day: datetime) -> list[datetime]:
        """Every slot start on one local day, in local time."""
        if local_day.isoweekday() not in self.days:
            return []
        start = local_day.replace(
            hour=self.opens.hour, minute=self.opens.minute, second=0, microsecond=0
        )
        end = local_day.replace(
            hour=self.closes.hour, minute=self.closes.minute, second=0, microsecond=0
        )
        step = timedelta(minutes=self.slot_minutes)
        slots: list[datetime] = []
        cursor = start
        while cursor < end:
            slots.append(cursor)
            cursor += step
        return slots


@dataclass(frozen=True, slots=True)
class Appointment:
    """One booked appointment.

    ``patient_name`` and ``reason`` are things a caller said about their health,
    so both are PHI. ``caller_ref`` is the opaque, tenant-salted reference that
    also appears in the audit log, which is how a booking is correlated with the
    call that created it without putting identity in the security record.
    """

    appointment_id: str
    tenant_id: str
    #: The absolute instant. Local rendering happens at the edges.
    starts_at: datetime
    duration_minutes: int = DEFAULT_SLOT_MINUTES
    status: AppointmentStatus = AppointmentStatus.BOOKED
    call_id: str | None = None
    caller_ref: str = ""
    patient_name: PHI[str] | None = None
    reason: PHI[str] | None = None
    booked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: Set when this booking replaced an earlier one, so a reschedule keeps its
    #: history rather than looking like a cancellation and an unrelated booking.
    previous_starts_at: datetime | None = None

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_active(self) -> bool:
        return self.status in (AppointmentStatus.BOOKED, AppointmentStatus.RESCHEDULED)

    def local_start(self, config: TenantConfig) -> datetime:
        return self.starts_at.astimezone(config.tz)

    def spoken(self, config: TenantConfig) -> str:
        """What the agent reads back to the caller.

        FR2.4 requires the resulting date and time to be stated aloud before the
        call ends. Built here rather than left to the model, because a
        model-composed confirmation can drift from what was actually persisted
        — and the whole value of the read-back is that it matches the booking.
        """
        local = self.local_start(config)
        # No leading zero on the hour: "9:30", not "09:30", because this is
        # spoken aloud rather than displayed.
        hour = local.strftime("%I").lstrip("0") or "12"
        return f"{local.strftime('%A %-d %B')} at {hour}:{local.strftime('%M %p').lower()}"

    def summary(self) -> dict[str, object]:
        """List shape. Carries no PHI — a name is not needed to show a diary."""
        return {
            "appointment_id": self.appointment_id,
            "starts_at": self.starts_at.isoformat(),
            "duration_minutes": self.duration_minutes,
            "status": str(self.status),
            "call_id": self.call_id,
            "rescheduled_from": self.previous_starts_at.isoformat()
            if self.previous_starts_at
            else None,
        }


class Calendar:
    """Tenant-partitioned appointments, with atomic slot claiming."""

    def __init__(self, *, horizon_days: int = DEFAULT_HORIZON_DAYS) -> None:
        self._appointments: TenantScoped[Appointment] = TenantScoped()
        self._horizon_days = horizon_days
        # One lock, not one per tenant: contention is negligible at this scale
        # and a per-tenant lock map is another thing to get wrong.
        self._lock = threading.Lock()

    # -- reading ---------------------------------------------------------

    def get(self, tenant: TenantContext, appointment_id: str) -> Appointment | None:
        return self._appointments.get(tenant, appointment_id)

    def active(self, tenant: TenantContext) -> list[Appointment]:
        return sorted(
            (a for a in self._appointments.values(tenant) if a.is_active),
            key=lambda a: a.starts_at,
        )

    def upcoming(
        self, tenant: TenantContext, *, now: datetime | None = None, limit: int = 50
    ) -> list[Appointment]:
        moment = now or datetime.now(UTC)
        return [a for a in self.active(tenant) if a.starts_at >= moment][:limit]

    def for_caller(self, tenant: TenantContext, caller_ref: str) -> list[Appointment]:
        """A caller's own active appointments — what FR2.2 and FR2.3 identify.

        Identification is by the opaque reference rather than by name: two
        patients share a name far more often than they share a phone number,
        and asking a voice agent to disambiguate names is how the wrong
        person's appointment gets cancelled.
        """
        if not caller_ref:
            return []
        return [a for a in self.active(tenant) if a.caller_ref == caller_ref]

    def is_free(self, tenant: TenantContext, when: datetime) -> bool:
        return not any(
            a.starts_at == when for a in self._appointments.values(tenant) if a.is_active
        )

    # -- availability ----------------------------------------------------

    def availability(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        *,
        on: datetime | None = None,
        now: datetime | None = None,
        limit: int = 20,
    ) -> list[datetime]:
        """Free slots, as absolute instants, ordered soonest first."""
        moment = now or datetime.now(UTC)
        start_local = (on or moment).astimezone(config.tz)
        horizon = moment + timedelta(days=self._horizon_days)

        free: list[datetime] = []
        day = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
        while len(free) < limit:
            for local_slot in hours.slots_on(day):
                instant = local_slot.astimezone(UTC)
                if instant < moment or instant > horizon:
                    continue
                if self.is_free(tenant, instant):
                    free.append(instant)
                    if len(free) >= limit:
                        break
            day += timedelta(days=1)
            if day.astimezone(UTC) > horizon:
                break
        return free

    def alternatives(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        around: datetime,
        *,
        now: datetime | None = None,
        count: int = 3,
    ) -> tuple[datetime, ...]:
        """Slots nearest a requested time — FR2.5.

        Nearest rather than next: a caller who asked for Tuesday morning is
        better served by Tuesday afternoon than by the first free slot in three
        weeks, and offering the latter reads as the agent ignoring them.
        """
        candidates = self.availability(
            tenant, config, hours, on=around - timedelta(days=2), now=now, limit=200
        )
        return tuple(sorted(candidates, key=lambda s: abs(s - around))[:count])

    # -- writing ---------------------------------------------------------

    def book(
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
        """Claim a slot. Raises :class:`SlotUnavailable` rather than double-booking.

        The check and the write happen under one lock. Splitting them — check
        availability, return to the caller, then write — is precisely the race
        that puts two patients in one slot, and with simultaneous callers it is
        a matter of load rather than luck.
        """
        moment = now or datetime.now(UTC)
        with self._lock:
            self._validate_slot(tenant, config, hours, when, moment)
            appointment = Appointment(
                appointment_id=str(uuid.uuid4()),
                tenant_id=tenant.tenant_id,
                starts_at=when,
                duration_minutes=hours.slot_minutes,
                call_id=call_id,
                caller_ref=caller_ref,
                patient_name=PHI(patient_name) if patient_name else None,
                reason=PHI(reason) if reason else None,
                booked_at=moment,
            )
            self._appointments.put(tenant, appointment.appointment_id, appointment)
            return appointment

    def reschedule(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        appointment_id: str,
        when: datetime,
        *,
        now: datetime | None = None,
    ) -> Appointment:
        """Move an appointment — FR2.2. The old slot frees only if the new one takes."""
        moment = now or datetime.now(UTC)
        with self._lock:
            existing = self._appointments.get(tenant, appointment_id)
            if existing is None or not existing.is_active:
                raise AppointmentNotFound(appointment_id)
            if when == existing.starts_at:
                return existing
            self._validate_slot(tenant, config, hours, when, moment, ignoring=appointment_id)
            moved = replace(
                existing,
                starts_at=when,
                status=AppointmentStatus.RESCHEDULED,
                previous_starts_at=existing.starts_at,
            )
            self._appointments.put(tenant, appointment_id, moved)
            return moved

    def cancel(self, tenant: TenantContext, appointment_id: str) -> Appointment:
        """Cancel — FR2.3. The row stays; the clinic needs to know it happened."""
        with self._lock:
            existing = self._appointments.get(tenant, appointment_id)
            if existing is None or not existing.is_active:
                raise AppointmentNotFound(appointment_id)
            cancelled = replace(existing, status=AppointmentStatus.CANCELLED)
            self._appointments.put(tenant, appointment_id, cancelled)
            return cancelled

    # -- internals -------------------------------------------------------

    def _validate_slot(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        when: datetime,
        moment: datetime,
        *,
        ignoring: str | None = None,
    ) -> None:
        """Every reason a slot cannot be taken, each with alternatives to offer."""
        if when.tzinfo is None:
            # A naive datetime here would be silently interpreted as UTC and
            # book someone hours from where they meant.
            raise ValueError("appointment times must be timezone-aware")

        local = when.astimezone(config.tz)

        if when < moment:
            raise SlotUnavailable(
                "that time is in the past",
                self.alternatives(tenant, config, hours, moment, now=moment),
            )
        if when > moment + timedelta(days=self._horizon_days):
            raise SlotUnavailable(
                f"we only book {self._horizon_days} days ahead",
                self.alternatives(tenant, config, hours, moment, now=moment),
            )
        if not hours.is_open(local):
            raise SlotUnavailable(
                "the clinic is not open then",
                self.alternatives(tenant, config, hours, when, now=moment),
            )
        if local not in hours.slots_on(local):
            raise SlotUnavailable(
                "appointments start on the half hour"
                if hours.slot_minutes == 30
                else f"appointments start every {hours.slot_minutes} minutes",
                self.alternatives(tenant, config, hours, when, now=moment),
            )
        taken = any(
            a.starts_at == when and a.is_active and a.appointment_id != ignoring
            for a in self._appointments.values(tenant)
        )
        if taken:
            raise SlotUnavailable(
                "that time is already taken",
                self.alternatives(tenant, config, hours, when, now=moment),
            )

    def __iter__(self) -> Iterator[str]:
        raise TypeError("Calendar is not iterable without tenant context. Use active(tenant).")
