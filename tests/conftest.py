"""Shared fixtures.

Database tests run against real Postgres, never a stand-in. Row-level security,
partial unique indexes and `SET LOCAL` are all engine-specific, and testing
them on anything else would be testing something we do not ship.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from ait_voice.db.connection import Database, DatabaseSettings

#: Set by CI's Postgres service container and by a local `ait-voice` database.
_REQUIRED = ("AIT_DB_NAME",)


def postgres_available() -> bool:
    return all(os.environ.get(name) for name in _REQUIRED)


requires_postgres = pytest.mark.skipif(
    not postgres_available(),
    reason="needs Postgres — set AIT_DB_NAME (see docs/database.md)",
)


@pytest.fixture
def app_settings() -> DatabaseSettings:
    """Application credentials: `ait_app`, deliberately not a superuser."""
    return DatabaseSettings(
        host=os.environ.get("AIT_DB_HOST", "localhost"),
        port=int(os.environ.get("AIT_DB_PORT", "5432")),
        database=os.environ.get("AIT_DB_NAME", "ait-voice"),
        user=os.environ.get("AIT_DB_USER", "ait_app"),
        password=os.environ.get("AIT_DB_PASSWORD", "local_dev_only"),
    )


@pytest.fixture
def owner_settings() -> DatabaseSettings:
    """Owner credentials, for seeding and schema work only."""
    return DatabaseSettings(
        host=os.environ.get("AIT_DB_HOST", "localhost"),
        port=int(os.environ.get("AIT_DB_PORT", "5432")),
        database=os.environ.get("AIT_DB_NAME", "ait-voice"),
        user=os.environ.get("AIT_DB_OWNER_USER", "postgres"),
        password=os.environ.get("AIT_DB_OWNER_PASSWORD", "root"),
    )


@pytest.fixture
async def database(app_settings: DatabaseSettings) -> AsyncIterator[Database | None]:
    """A connected pool, or None when Postgres is not configured.

    None rather than an error so a suite that is parameterised over both an
    in-memory and a Postgres implementation can run its in-memory half on a
    machine with no database. The Postgres half is not generated at all in that
    case — see `postgres_available` — so nothing silently skips a check while
    reporting green.
    """
    if not postgres_available():
        yield None
        return
    db = Database(app_settings)
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


#: Every tenant-scoped table, child-first so foreign keys do not object.
#: `tenants` is included: a test that leaves clinics behind changes what the
#: next test sees, and a shared database only stays deterministic if each test
#: starts from the same place.
_TABLES = (
    "intake_values",
    "intake_records",
    "transcripts",
    "appointments",
    "messages",
    "handoffs",
    "consents",
    "call_records",
    "tenants",
)


@pytest.fixture(autouse=True)
async def clean_database(request: pytest.FixtureRequest) -> AsyncIterator[None]:
    """Empty the database before each database test.

    Without this the suite passes exactly once. The double-booking tests insert
    an appointment and the unique index then refuses the same slot on every
    later run — a failure that looks like a broken constraint and is really a
    dirty fixture.

    Truncation runs as the owner, because `ait_app` deliberately has no DDL
    rights and TRUNCATE is DDL.
    """
    if not postgres_available() or "database" not in request.fixturenames:
        yield
        return

    settings = DatabaseSettings(
        host=os.environ.get("AIT_DB_HOST", "localhost"),
        port=int(os.environ.get("AIT_DB_PORT", "5432")),
        database=os.environ.get("AIT_DB_NAME", "ait-voice"),
        user=os.environ.get("AIT_DB_OWNER_USER", "postgres"),
        password=os.environ.get("AIT_DB_OWNER_PASSWORD", "root"),
    )
    db = Database(settings)
    await db.connect(allow_superuser=True)
    try:
        async with db.unscoped() as connection:
            await connection.execute(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE")
    finally:
        await db.close()
    yield


@pytest.fixture
async def owner(owner_settings: DatabaseSettings) -> AsyncIterator[Database | None]:
    if not postgres_available():
        yield None
        return
    db = Database(owner_settings)
    await db.connect(allow_superuser=True)
    try:
        yield db
    finally:
        await db.close()


#: Set when a real S3 implementation (MinIO locally, a service in CI) is up.
_S3_REQUIRED = ("AIT_S3_ENDPOINT",)


def s3_available() -> bool:
    return all(os.environ.get(name) for name in _S3_REQUIRED)


requires_s3 = pytest.mark.skipif(
    not s3_available(),
    reason="needs a real S3 — set AIT_S3_ENDPOINT (see docs/deploying.md)",
)


@pytest.fixture
def s3_client():  # noqa: ANN201 - a boto3 client, untyped without the stubs
    """A client against a real S3 implementation, or skip.

    The audit sink's guarantees are S3 semantics — conditional writes, delete
    markers, Object Lock protecting versions rather than the current view. The
    in-memory double models all three, but it models them the way we believe
    they work, and that belief was wrong twice. This is the check that the
    belief still matches the implementation.
    """
    if not s3_available():
        pytest.skip("no S3 endpoint configured")
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["AIT_S3_ENDPOINT"],
        aws_access_key_id=os.environ.get("AIT_S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("AIT_S3_SECRET_KEY", "minioadmin"),
        region_name="us-east-1",
    )
