"""The calendar, in Postgres.

The interesting change is where double booking is prevented. In memory it was
a lock, which holds for exactly one process; here it is a partial unique index
on ``(tenant_id, starts_at)``, which holds across instances, restarts and
races. :meth:`PostgresCalendar.book` translates the resulting
``UniqueViolationError`` back into :class:`SlotUnavailable` carrying
alternatives, because FR2.5 requires a refusal to offer them and the caller
should not be able to tell which layer said no.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ait_voice.core.scheduling import (
    DEFAULT_HORIZON_DAYS,
    Appointment,
    AppointmentNotFound,
    AppointmentStatus,
    BookingHours,
    SlotUnavailable,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, TenantContext
from ait_voice.db.connection import Database


def _to_appointment(row: Any) -> Appointment:  # noqa: ANN401 - asyncpg.Record
    return Appointment(
        appointment_id=str(row["appointment_id"]),
        tenant_id=row["tenant_id"],
        starts_at=row["starts_at"],
        duration_minutes=row["duration_minutes"],
        status=AppointmentStatus(row["status"]),
        call_id=row["call_id"],
        caller_ref=row["caller_ref"],
        patient_name=PHI(row["patient_name"]) if row["patient_name"] else None,
        reason=PHI(row["reason"]) if row["reason"] else None,
        booked_at=row["booked_at"],
        previous_starts_at=row["previous_starts_at"],
    )


_ACTIVE = ("booked", "rescheduled")


class PostgresCalendar:
    """Mirrors :class:`~ait_voice.core.scheduling.Calendar`, async."""

    def __init__(self, database: Database, *, horizon_days: int = DEFAULT_HORIZON_DAYS) -> None:
        self._db = database
        self._horizon_days = horizon_days

    # -- reading ---------------------------------------------------------

    async def get(self, tenant: TenantContext, appointment_id: str) -> Appointment | None:
        try:
            identifier = uuid.UUID(appointment_id)
        except ValueError:
            return None
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                "SELECT * FROM appointments WHERE appointment_id = $1", identifier
            )
        return _to_appointment(row) if row else None

    async def active(self, tenant: TenantContext) -> list[Appointment]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                "SELECT * FROM appointments WHERE status = ANY($1) ORDER BY starts_at",
                list(_ACTIVE),
            )
        return [_to_appointment(row) for row in rows]

    async def upcoming(
        self, tenant: TenantContext, *, now: datetime | None = None, limit: int = 50
    ) -> list[Appointment]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT * FROM appointments
                WHERE status = ANY($1) AND starts_at >= $2
                ORDER BY starts_at LIMIT $3
                """,
                list(_ACTIVE),
                now or datetime.now(UTC),
                limit,
            )
        return [_to_appointment(row) for row in rows]

    async def for_caller(self, tenant: TenantContext, caller_ref: str) -> list[Appointment]:
        """Identification by opaque reference, never by name.

        Two patients share a name far more often than a phone number, and
        asking a voice agent to disambiguate names is how the wrong person's
        appointment gets cancelled.
        """
        if not caller_ref:
            return []
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT * FROM appointments
                WHERE caller_ref = $1 AND status = ANY($2) ORDER BY starts_at
                """,
                caller_ref,
                list(_ACTIVE),
            )
        return [_to_appointment(row) for row in rows]

    async def is_free(self, tenant: TenantContext, when: datetime) -> bool:
        async with self._db.tenant_scope(tenant) as c:
            taken = await c.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM appointments
                    WHERE starts_at = $1 AND status = ANY($2)
                )
                """,
                when,
                list(_ACTIVE),
            )
        return not taken

    # -- availability ----------------------------------------------------

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
        """Free slots as absolute instants, soonest first.

        The candidate grid is generated in Python and the taken set is fetched
        in one query, rather than a slot-by-slot round trip. Opening hours are
        clinic-local, and expressing that as SQL would be a date-arithmetic
        exercise with a timezone bug waiting inside it.
        """
        moment = now or datetime.now(UTC)
        horizon = moment + timedelta(days=self._horizon_days)
        start_local = (on or moment).astimezone(config.tz)

        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT starts_at FROM appointments
                WHERE status = ANY($1) AND starts_at BETWEEN $2 AND $3
                """,
                list(_ACTIVE),
                moment,
                horizon,
            )
        taken = {row["starts_at"] for row in rows}

        free: list[datetime] = []
        day = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
        while len(free) < limit:
            for local_slot in hours.slots_on(day):
                instant = local_slot.astimezone(UTC)
                if instant < moment or instant > horizon or instant in taken:
                    continue
                free.append(instant)
                if len(free) >= limit:
                    break
            day += timedelta(days=1)
            if day.astimezone(UTC) > horizon:
                break
        return free

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
        """Nearest free slots — FR2.5, and nearest rather than next.

        A caller who asked for Tuesday morning is not served by the first free
        slot in three weeks; that reads as the agent ignoring them.
        """
        candidates = await self.availability(
            tenant, config, hours, on=around - timedelta(days=2), now=now, limit=200
        )
        return tuple(sorted(candidates, key=lambda s: abs(s - around))[:count])

    # -- writing ---------------------------------------------------------

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
        """Claim a slot. The database is what makes this exclusive."""
        import asyncpg

        moment = now or datetime.now(UTC)
        await self._validate(tenant, config, hours, when, moment)

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
        try:
            async with self._db.tenant_scope(tenant) as c:
                await c.execute(
                    """
                    INSERT INTO appointments (
                        appointment_id, tenant_id, starts_at, duration_minutes,
                        status, call_id, caller_ref, patient_name, reason, booked_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    uuid.UUID(appointment.appointment_id),
                    appointment.tenant_id,
                    appointment.starts_at,
                    appointment.duration_minutes,
                    str(appointment.status),
                    appointment.call_id,
                    appointment.caller_ref,
                    patient_name,
                    reason,
                    appointment.booked_at,
                )
        except asyncpg.UniqueViolationError as clash:
            # Another caller took the slot between validation and insert. The
            # index is what actually decides; this turns its verdict back into
            # the refusal the dialog knows how to speak.
            raise SlotUnavailable(
                "that time is already taken",
                await self.alternatives(tenant, config, hours, when, now=moment),
            ) from clash
        return appointment

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
        """Move an appointment. The old slot frees only if the new one takes."""
        import asyncpg

        moment = now or datetime.now(UTC)
        existing = await self.get(tenant, appointment_id)
        if existing is None or not existing.is_active:
            raise AppointmentNotFound(appointment_id)
        if when == existing.starts_at:
            return existing

        await self._validate(tenant, config, hours, when, moment, ignoring=appointment_id)
        try:
            async with self._db.tenant_scope(tenant) as c:
                row = await c.fetchrow(
                    """
                    UPDATE appointments
                    SET starts_at = $2, status = 'rescheduled', previous_starts_at = starts_at
                    WHERE appointment_id = $1
                    RETURNING *
                    """,
                    uuid.UUID(appointment_id),
                    when,
                )
        except asyncpg.UniqueViolationError as clash:
            raise SlotUnavailable(
                "that time is already taken",
                await self.alternatives(tenant, config, hours, when, now=moment),
            ) from clash
        return _to_appointment(row)

    async def cancel(self, tenant: TenantContext, appointment_id: str) -> Appointment:
        """Cancel. The row stays — the clinic needs to know it happened."""
        existing = await self.get(tenant, appointment_id)
        if existing is None or not existing.is_active:
            raise AppointmentNotFound(appointment_id)
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                UPDATE appointments SET status = 'cancelled'
                WHERE appointment_id = $1 RETURNING *
                """,
                uuid.UUID(appointment_id),
            )
        return _to_appointment(row)

    # -- internals -------------------------------------------------------

    async def _validate(
        self,
        tenant: TenantContext,
        config: TenantConfig,
        hours: BookingHours,
        when: datetime,
        moment: datetime,
        *,
        ignoring: str | None = None,
    ) -> None:
        """Every reason a slot cannot be taken, each with alternatives.

        The taken-slot check here is advisory: two callers can both pass it and
        the unique index decides between them. It exists so the common case
        gets a helpful refusal rather than a constraint violation.
        """
        if when.tzinfo is None:
            raise ValueError("appointment times must be timezone-aware")

        local = when.astimezone(config.tz)

        if when < moment:
            raise SlotUnavailable(
                "that time is in the past",
                await self.alternatives(tenant, config, hours, moment, now=moment),
            )
        if when > moment + timedelta(days=self._horizon_days):
            raise SlotUnavailable(
                f"we only book {self._horizon_days} days ahead",
                await self.alternatives(tenant, config, hours, moment, now=moment),
            )
        if not hours.is_open(local):
            raise SlotUnavailable(
                "the clinic is not open then",
                await self.alternatives(tenant, config, hours, when, now=moment),
            )
        if local not in hours.slots_on(local):
            raise SlotUnavailable(
                "appointments start on the half hour"
                if hours.slot_minutes == 30
                else f"appointments start every {hours.slot_minutes} minutes",
                await self.alternatives(tenant, config, hours, when, now=moment),
            )

        async with self._db.tenant_scope(tenant) as c:
            taken = await c.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM appointments
                    WHERE starts_at = $1 AND status = ANY($2)
                      AND ($3::uuid IS NULL OR appointment_id <> $3)
                )
                """,
                when,
                list(_ACTIVE),
                uuid.UUID(ignoring) if ignoring else None,
            )
        if taken:
            raise SlotUnavailable(
                "that time is already taken",
                await self.alternatives(tenant, config, hours, when, now=moment),
            )
