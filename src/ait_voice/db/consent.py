"""The consent ledger, in Postgres.

The property that matters survives the move unchanged: **expiry is evaluated at
read time, not stamped at write time**. The row records when consent was
granted and in which region; whether it is still valid is computed by
:class:`~ait_voice.core.consent.Consent` from those two facts. A stored
`expires_at` would be a second copy of a rule that C-R9 owns, and a rule stored
twice is a rule that can disagree with itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ait_voice.core.consent import Consent, ConsentPurpose
from ait_voice.core.types import Region, TenantContext
from ait_voice.db.connection import Database


class PostgresConsentLedger:
    """Mirrors :class:`~ait_voice.core.consent.ConsentLedger`, async."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def grant(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        at: datetime | None = None,
    ) -> Consent:
        moment = at or datetime.now(UTC)
        async with self._db.tenant_scope(tenant) as c:
            await c.execute(
                """
                INSERT INTO consents (tenant_id, caller_ref, purpose, granted_at, region)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (tenant_id, caller_ref, purpose)
                DO UPDATE SET granted_at = EXCLUDED.granted_at
                """,
                tenant.tenant_id,
                caller_ref,
                str(purpose),
                moment,
                str(tenant.region),
            )
        return Consent(
            caller_ref=caller_ref,
            purpose=purpose,
            granted_at=moment,
            region=tenant.region,
        )

    async def revoke(self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose) -> bool:
        """Withdraw consent. Always available, in every jurisdiction."""
        async with self._db.tenant_scope(tenant) as c:
            status = await c.execute(
                """
                DELETE FROM consents
                WHERE caller_ref = $1 AND purpose = $2
                """,
                caller_ref,
                str(purpose),
            )
        # asyncpg's execute() returns an untyped command tag.
        return bool(status != "DELETE 0")

    async def lookup(
        self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> Consent | None:
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                SELECT granted_at, region FROM consents
                WHERE caller_ref = $1 AND purpose = $2
                """,
                caller_ref,
                str(purpose),
            )
        if row is None:
            return None
        return Consent(
            caller_ref=caller_ref,
            purpose=purpose,
            granted_at=row["granted_at"],
            region=Region(row["region"]),
        )

    async def is_valid(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        now: datetime | None = None,
    ) -> bool:
        consent = await self.lookup(tenant, caller_ref, purpose)
        return bool(consent and consent.is_valid(now=now))
