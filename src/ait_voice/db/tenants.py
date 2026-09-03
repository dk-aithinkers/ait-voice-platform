"""The tenant registry, in Postgres.

Deliberately the one table without row-level security: this is the registry
that knows about every clinic, which is what lets every other table know about
exactly one. It holds a clinic's own details and no patient data.
"""

from __future__ import annotations

from typing import Any

from ait_voice.core.tenancy import (
    NumberAlreadyClaimed,
    OutOfHoursPolicy,
    StaffedHours,
    TenantConfig,
    TenantNotFoundError,
    normalize_e164,
)
from ait_voice.core.types import Region, TenantContext
from ait_voice.db.connection import Database

# Queries are written out in full rather than composed from a column constant.
# An f-string here is not injectable — the constant is ours — but SQL assembled
# by string formatting is a habit worth not having in a codebase where a query
# bug is a PHI disclosure, and it keeps the linter useful rather than silenced.


def _to_config(row: Any) -> TenantConfig:  # noqa: ANN401 - asyncpg.Record
    return TenantConfig(
        tenant_id=row["tenant_id"],
        region=Region(row["region"]),
        clinic_name=row["clinic_name"],
        greeting=row["greeting"],
        staffed_hours=StaffedHours(
            days=frozenset(row["staffed_days"]),
            opens=row["staffed_opens"],
            closes=row["staffed_closes"],
        ),
        escalation_number=row["escalation_number"],
        out_of_hours=OutOfHoursPolicy(row["out_of_hours"]),
        languages=tuple(row["languages"]),
        timezone=row["timezone"],
        outbound_registered=row["outbound_registered"],
        active=row["active"],
    )


class PostgresTenantStore:
    """Mirrors :class:`~ait_voice.core.tenancy.TenantStore`, async."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def add(self, config: TenantConfig) -> TenantConfig:
        async with self._db.unscoped() as c:
            await c.execute(
                """
                INSERT INTO tenants (
                    tenant_id, region, clinic_name, greeting, escalation_number,
                    out_of_hours, languages, timezone, staffed_days,
                    staffed_opens, staffed_closes, outbound_registered, active
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                ON CONFLICT (tenant_id) DO UPDATE SET
                    region = EXCLUDED.region,
                    clinic_name = EXCLUDED.clinic_name,
                    greeting = EXCLUDED.greeting,
                    escalation_number = EXCLUDED.escalation_number,
                    out_of_hours = EXCLUDED.out_of_hours,
                    languages = EXCLUDED.languages,
                    timezone = EXCLUDED.timezone,
                    staffed_days = EXCLUDED.staffed_days,
                    staffed_opens = EXCLUDED.staffed_opens,
                    staffed_closes = EXCLUDED.staffed_closes,
                    outbound_registered = EXCLUDED.outbound_registered,
                    active = EXCLUDED.active
                """,
                config.tenant_id,
                str(config.region),
                config.clinic_name,
                config.greeting,
                config.escalation_number,
                str(config.out_of_hours),
                list(config.languages),
                config.timezone,
                sorted(config.staffed_hours.days),
                config.staffed_hours.opens,
                config.staffed_hours.closes,
                config.outbound_registered,
                config.active,
            )
        return config

    async def get(self, tenant_id: str) -> TenantConfig:
        async with self._db.unscoped() as c:
            row = await c.fetchrow(
                """
                SELECT tenant_id, region, clinic_name, greeting, escalation_number,
                       out_of_hours, languages, timezone, staffed_days,
                       staffed_opens, staffed_closes, outbound_registered, active
                FROM tenants WHERE tenant_id = $1
                """,
                tenant_id,
            )
        if row is None:
            raise TenantNotFoundError(tenant_id)
        return _to_config(row)

    async def resolve(self, tenant_id: str) -> TenantContext:
        """Tenant id to context. Refuses an inactive clinic, as in memory."""
        config = await self.get(tenant_id)
        if not config.active:
            raise TenantNotFoundError(f"{tenant_id} is not active")
        return config.context()

    async def update(self, tenant_id: str, **changes: Any) -> TenantConfig:  # noqa: ANN401
        return await self.add((await self.get(tenant_id)).with_changes(**changes))

    async def deactivate(self, tenant_id: str) -> TenantConfig:
        """Stop a clinic answering without deleting it.

        Deletion would cascade to its call records, and the audit log's whole
        purpose is that this history outlives the clinic's activity.
        """
        return await self.update(tenant_id, active=False)

    # -- inbound routing -------------------------------------------------

    async def claim_number(self, tenant_id: str, number: str, *, label: str | None = None) -> str:
        """Route `number` to this clinic, with the database deciding conflicts.

        The primary key on `phone_number` is what makes one number map to one
        clinic. Two operators claiming the same number at the same moment cannot
        both win, and the loser gets a refusal rather than a silent reassignment
        that would send a clinic's callers to somebody else's agent.

        `ON CONFLICT DO NOTHING` then a read-back, rather than an upsert:
        an upsert would quietly move a live number between clinics.
        """
        await self.get(tenant_id)  # Raises if the tenant does not exist.
        normalized = normalize_e164(number)
        async with self._db.unscoped() as connection:
            await connection.execute(
                """
                INSERT INTO tenant_numbers (phone_number, tenant_id, label)
                VALUES ($1, $2, $3)
                ON CONFLICT (phone_number) DO NOTHING
                """,
                normalized,
                tenant_id,
                label,
            )
            owner = await connection.fetchval(
                "SELECT tenant_id FROM tenant_numbers WHERE phone_number = $1", normalized
            )
        if owner != tenant_id:
            raise NumberAlreadyClaimed(
                f"{normalized} is already routed to tenant {owner!r}. Release it "
                "there before claiming it here."
            )
        return normalized

    async def release_number(self, number: str) -> bool:
        normalized = normalize_e164(number)
        async with self._db.unscoped() as connection:
            result = await connection.execute(
                "DELETE FROM tenant_numbers WHERE phone_number = $1", normalized
            )
        # asyncpg returns the command tag, e.g. "DELETE 1".
        return str(result).endswith(" 1")

    async def numbers(self, tenant_id: str) -> list[str]:
        async with self._db.unscoped() as connection:
            rows = await connection.fetch(
                "SELECT phone_number FROM tenant_numbers WHERE tenant_id = $1 "
                "ORDER BY phone_number",
                tenant_id,
            )
        return [row["phone_number"] for row in rows]

    async def resolve_number(self, number: str) -> TenantContext:
        """The number a caller dialled, to the clinic that answers it."""
        normalized = normalize_e164(number)
        async with self._db.unscoped() as connection:
            tenant_id = await connection.fetchval(
                "SELECT tenant_id FROM tenant_numbers WHERE phone_number = $1", normalized
            )
        if tenant_id is None:
            raise TenantNotFoundError(f"no clinic answers {normalized}")
        return await self.resolve(str(tenant_id))

    async def all(self) -> list[TenantConfig]:
        async with self._db.unscoped() as c:
            rows = await c.fetch(
                """
                SELECT tenant_id, region, clinic_name, greeting, escalation_number,
                       out_of_hours, languages, timezone, staffed_days,
                       staffed_opens, staffed_closes, outbound_registered, active
                FROM tenants ORDER BY tenant_id
                """
            )
        return [_to_config(row) for row in rows]

    async def active_tenants(self) -> list[TenantConfig]:
        return [config for config in await self.all() if config.active]

    async def by_region(self, region: Region) -> list[TenantConfig]:
        return [config for config in await self.all() if config.region is region]

    async def count(self) -> int:
        async with self._db.unscoped() as c:
            return await c.fetchval("SELECT count(*) FROM tenants") or 0


__all__ = ["PostgresTenantStore"]
