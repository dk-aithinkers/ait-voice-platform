"""Tenant isolation, enforced by Postgres rather than only by our code.

The application already makes cross-tenant access hard to write by accident.
These tests are about the second, independent layer: what happens when a query
gets it wrong anyway. Every one is written from the attacker's side — a valid
connection reaching for another clinic's rows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from ait_voice.core.types import Region, TenantContext
from ait_voice.db.connection import (
    DEFAULT_APP_USER,
    Database,
    DatabaseSettings,
    SuperuserRefused,
)
from tests.conftest import requires_postgres

NORTH = TenantContext(tenant_id="northside", region=Region.US)
PARK = TenantContext(tenant_id="parkclinic", region=Region.INDIA)

pytestmark = requires_postgres


@pytest.fixture
async def seeded(owner: Database) -> None:
    """Two clinics with one call each, inserted as the owner."""
    async with owner.unscoped() as c:
        await c.execute(
            """
            INSERT INTO tenants (tenant_id, region, clinic_name) VALUES
              ('northside','us','Northside Medical'),
              ('parkclinic','india','Park Clinic')
            ON CONFLICT (tenant_id) DO NOTHING
            """
        )
        await c.execute(
            """
            INSERT INTO call_records (call_id, tenant_id, started_at, caller) VALUES
              ('call-n1','northside', now(), '+15551110041'),
              ('call-p1','parkclinic', now(), '+919990001111')
            ON CONFLICT (tenant_id, call_id) DO NOTHING
            """
        )


class TestRowLevelSecurity:
    async def test_a_clinic_sees_only_its_own_rows(self, database: Database, seeded: None) -> None:
        async with database.tenant_scope(NORTH) as c:
            rows = await c.fetch("SELECT call_id FROM call_records")

        assert [r["call_id"] for r in rows] == ["call-n1"]

    async def test_an_unfiltered_query_still_cannot_cross_tenants(
        self, database: Database, seeded: None
    ) -> None:
        """The whole point: no WHERE clause, and still only one clinic's rows."""
        async with database.tenant_scope(PARK) as c:
            rows = await c.fetch("SELECT call_id, tenant_id FROM call_records")

        assert {r["tenant_id"] for r in rows} == {"parkclinic"}

    async def test_reaching_for_another_tenant_by_id_returns_nothing(
        self, database: Database, seeded: None
    ) -> None:
        """Not an error — simply absent, which is what a policy does."""
        async with database.tenant_scope(NORTH) as c:
            rows = await c.fetch("SELECT call_id FROM call_records WHERE tenant_id = 'parkclinic'")

        assert rows == []

    async def test_a_connection_with_no_tenant_sees_nothing(
        self, database: Database, seeded: None
    ) -> None:
        """`x = NULL` is never true, so a forgotten scope fails closed."""
        async with database.unscoped() as c:
            rows = await c.fetch("SELECT call_id FROM call_records")

        assert rows == []

    async def test_writing_into_another_tenant_is_refused(
        self, database: Database, seeded: None
    ) -> None:
        """WITH CHECK, not just USING: reads and writes are both bounded."""
        import asyncpg

        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with database.tenant_scope(NORTH) as c:
                await c.execute(
                    "INSERT INTO call_records (call_id, tenant_id, started_at) "
                    "VALUES ('smuggled', 'parkclinic', now())"
                )

    async def test_the_tenant_does_not_leak_onto_a_pooled_connection(
        self, database: Database, seeded: None
    ) -> None:
        """SET LOCAL, not SET: the value dies with the transaction rather than
        following the connection to whoever borrows it next."""
        async with database.tenant_scope(NORTH) as c:
            await c.fetch("SELECT 1")

        async with database.unscoped() as c:
            rows = await c.fetch("SELECT call_id FROM call_records")

        assert rows == []

    async def test_the_tenant_registry_is_readable_unscoped(
        self, database: Database, seeded: None
    ) -> None:
        """`tenants` deliberately has no policy — it is the registry that knows
        about every clinic, and it holds no patient data."""
        async with database.unscoped() as c:
            rows = await c.fetch("SELECT tenant_id FROM tenants")

        assert {r["tenant_id"] for r in rows} >= {"northside", "parkclinic"}


class TestSuperuserGuard:
    async def test_connecting_as_a_superuser_is_refused(
        self, owner_settings: DatabaseSettings
    ) -> None:
        """A superuser bypasses RLS unconditionally — FORCE does not apply to
        them — so the policies would be on and enforcing nothing. That failure
        looks exactly like success, which is why it is refused at startup."""
        database = Database(owner_settings)

        with pytest.raises(SuperuserRefused, match="bypass row-level security"):
            await database.connect()

    async def test_the_refusal_names_the_role_to_use_instead(
        self, owner_settings: DatabaseSettings
    ) -> None:
        with pytest.raises(SuperuserRefused, match=DEFAULT_APP_USER):
            await Database(owner_settings).connect()

    async def test_migrations_may_opt_in(self, owner: Database) -> None:
        """Schema changes legitimately need owner authority."""
        async with owner.unscoped() as c:
            assert await c.fetchval("SELECT 1") == 1

    async def test_the_application_role_is_not_a_superuser(self, database: Database) -> None:
        async with database.unscoped() as c:
            assert (
                await c.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                is False
            )


class TestDoubleBookingConstraint:
    """The guarantee that used to be an in-process lock, and therefore held for
    exactly one API instance."""

    @pytest.fixture
    def slot(self) -> datetime:
        return datetime(2027, 3, 4, 14, 30, tzinfo=UTC)

    async def test_two_bookings_of_one_slot_are_refused(
        self, database: Database, seeded: None, slot: datetime
    ) -> None:
        import asyncpg

        async with database.tenant_scope(NORTH) as c:
            await c.execute(
                "INSERT INTO appointments (appointment_id, tenant_id, starts_at) "
                "VALUES ($1, 'northside', $2)",
                uuid.uuid4(),
                slot,
            )

        with pytest.raises(asyncpg.UniqueViolationError):
            async with database.tenant_scope(NORTH) as c:
                await c.execute(
                    "INSERT INTO appointments (appointment_id, tenant_id, starts_at) "
                    "VALUES ($1, 'northside', $2::timestamptz)",
                    uuid.uuid4(),
                    slot,
                )

    async def test_two_clinics_may_hold_the_same_slot(
        self, database: Database, seeded: None
    ) -> None:
        """They are not competing for one room."""
        moment = datetime(2027, 3, 5, 14, 30, tzinfo=UTC)
        for tenant in (NORTH, PARK):
            async with database.tenant_scope(tenant) as c:
                await c.execute(
                    "INSERT INTO appointments (appointment_id, tenant_id, starts_at) "
                    "VALUES ($1, $2, $3)",
                    uuid.uuid4(),
                    tenant.tenant_id,
                    moment,
                )

    async def test_a_cancelled_slot_can_be_rebooked(self, database: Database, seeded: None) -> None:
        """The partial index is what allows this — a plain unique index would
        keep the slot blocked forever."""
        moment = datetime(2027, 3, 6, 14, 30, tzinfo=UTC)
        first = uuid.uuid4()
        async with database.tenant_scope(NORTH) as c:
            await c.execute(
                "INSERT INTO appointments (appointment_id, tenant_id, starts_at) "
                "VALUES ($1, 'northside', $2)",
                first,
                moment,
            )
            await c.execute(
                "UPDATE appointments SET status = 'cancelled' WHERE appointment_id = $1",
                first,
            )
            await c.execute(
                "INSERT INTO appointments (appointment_id, tenant_id, starts_at) "
                "VALUES ($1, 'northside', $2)",
                uuid.uuid4(),
                moment,
            )
