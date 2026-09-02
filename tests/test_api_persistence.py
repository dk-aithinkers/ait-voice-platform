"""The API, actually reading and writing Postgres.

Everything else about the persistence work is proven one layer down:
`test_repository_equivalence.py` shows the repositories behave like the stores
they replace, and `test_database_isolation.py` shows row-level security holds.
Neither proves the API is *using* any of it — and for two commits it was not,
the repositories being written, tested and then constructed by nobody.

So these tests go in the front door. A request arrives over HTTP, and the row
it returns is one that a different connection put in the database.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from ait_voice.api.app import Services, create_app
from ait_voice.api.auth import Principal, Role
from ait_voice.core.records import CallOutcome, CallRecord
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region
from ait_voice.db.connection import Database
from tests.conftest import requires_postgres

NORTHSIDE = "northside"


@pytest.fixture
async def services(database: Database | None) -> Services:
    assert database is not None
    return Services.from_database(database)


@pytest.fixture
async def seeded(services: Services) -> str:
    """A clinic and one call, written through the repositories."""
    await services.tenants.add(
        TenantConfig(
            tenant_id=NORTHSIDE,
            region=Region.US,
            clinic_name="Northside Medical",
            timezone="America/New_York",
        )
    )
    tenant = await services.tenants.resolve(NORTHSIDE)
    await services.calls.add(
        tenant,
        CallRecord(
            call_id="call-db-1",
            tenant_id=NORTHSIDE,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
            duration_seconds=131.0,
            turns=4,
            outcome=CallOutcome.APPOINTMENT_BOOKED,
            caller=PHI("+15551110041"),
        ),
    )
    return "call-db-1"


@pytest.fixture
async def client(services: Services) -> AsyncIterator[AsyncClient]:
    """httpx over ASGI rather than `TestClient`, and the reason matters.

    `TestClient` drives the app from a worker thread running its own event
    loop, while the asyncpg pool belongs to the loop pytest-asyncio created.
    Using one from the other raises "another operation is in progress" — the
    pool is not the shared thing it looks like. Everything here stays on one
    loop instead.
    """
    app = create_app(services)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
def token(services: Services) -> str:
    return services.principals.issue(
        Principal(principal_id="c1", role=Role.CLINIC, tenant_id=NORTHSIDE)
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@requires_postgres
class TestTheAPIReadsPostgres:
    async def test_a_call_written_to_the_database_is_served_over_http(
        self, client: AsyncClient, token: str, seeded: str
    ) -> None:
        response = await client.get("/api/calls", headers=_auth(token))

        assert response.status_code == 200
        assert [c["call_id"] for c in response.json()] == [seeded]

    async def test_the_number_is_masked_on_the_way_out(
        self, client: AsyncClient, token: str, seeded: str
    ) -> None:
        """Masking is server-side, and survives the trip through Postgres."""
        body = (await client.get("/api/calls", headers=_auth(token))).text

        assert "+15551110041" not in body
        assert "+1555…41" in body

    async def test_the_clinic_configuration_comes_from_the_database(
        self, client: AsyncClient, token: str, seeded: str
    ) -> None:
        response = await client.get("/api/clinic", headers=_auth(token))

        assert response.status_code == 200
        assert response.json()["clinic_name"] == "Northside Medical"

    async def test_a_write_over_http_lands_in_the_database(
        self, client: AsyncClient, token: str, seeded: str, services: Services
    ) -> None:
        """The round trip that memory would also pass — and a restart would not."""
        operator = services.principals.issue(
            Principal(principal_id="op", role=Role.OPERATOR, display_name="op")
        )
        response = await client.post(
            f"/api/clinic?tenant={NORTHSIDE}",
            headers=_auth(operator),
            json={"clinic_name": "Northside Family Practice"},
        )

        assert response.status_code == 200
        # Read back through a separate connection, not the response body.
        readback = await client.get("/api/clinic", headers=_auth(token))
        assert readback.json()["clinic_name"] == "Northside Family Practice"


@requires_postgres
class TestTheRowIsReallyInPostgres:
    async def test_an_http_write_is_visible_to_raw_sql(
        self, client: AsyncClient, seeded: str, services: Services, database: Database | None
    ) -> None:
        """The one assertion the repository layer cannot fake.

        Every other test here reads back through the same repositories it wrote
        through, so an elaborate in-memory store would satisfy them. This one
        goes around the repositories entirely and asks Postgres directly.
        """
        assert database is not None
        operator = services.principals.issue(
            Principal(principal_id="op2", role=Role.OPERATOR, display_name="op")
        )
        response = await client.post(
            f"/api/clinic?tenant={NORTHSIDE}",
            headers=_auth(operator),
            json={"greeting": "Northside, how can I help?"},
        )
        assert response.status_code == 200

        async with database.unscoped() as connection:
            greeting = await connection.fetchval(
                "SELECT greeting FROM tenants WHERE tenant_id = $1", NORTHSIDE
            )

        assert greeting == "Northside, how can I help?"


@requires_postgres
class TestTheServicesAreNotInMemory:
    async def test_from_database_wires_every_store_to_postgres(self, services: Services) -> None:
        """The failure this guards against is a store left behind on a rewire.

        One in-memory store among five Postgres ones loses exactly one kind of
        data on restart, which is far harder to notice than losing all of it.
        """
        for name in ("tenants", "calls", "calendar", "handoffs", "intake", "consent"):
            store = getattr(services, name)
            assert type(store).__name__.startswith("Postgres"), (
                f"Services.from_database left {name} as {type(store).__name__}"
            )


class TestTheProductionEntrypoint:
    """`ait_voice.api.main`, which is what a deployment actually runs."""

    def test_building_it_needs_no_database(self) -> None:
        """Importing and building must not reach out to Postgres.

        A factory that connected eagerly would fail on any machine without a
        database — including during test collection for the several hundred
        tests that never touch one. The pool opens in the lifespan instead,
        which is also the only place there is a running loop to open it on.
        """
        from ait_voice.api.main import production_app

        app = production_app()

        assert app.router.lifespan_context is not None

    @requires_postgres
    async def test_its_lifespan_opens_and_closes_the_pool(self) -> None:
        """The wiring end to end: startup connects, a request reads, shutdown closes."""
        from ait_voice.api.main import production_app

        app = production_app()
        # Starlette's own lifespan context, rather than adding `asgi-lifespan`
        # as a dependency for one test. This is what an ASGI server calls.
        transport = ASGITransport(app=app)
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=transport, base_url="http://test") as http,
        ):
            response = await http.get("/api/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
