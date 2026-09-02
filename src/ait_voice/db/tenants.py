"""The tenant registry, in Postgres.

Deliberately the one table without row-level security: this is the registry
that knows about every clinic, which is what lets every other table know about
exactly one. It holds a clinic's own details and no patient data.
"""

from __future__ import annotations

from typing import Any

from ait_voice.core.tenancy import (
    OutOfHoursPolicy,
    StaffedHours,
    TenantConfig,
    TenantNotFoundError,
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
