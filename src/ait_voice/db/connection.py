"""Database connections, and the tenant scope that cannot be forgotten.

The application connects as ``ait_app``, a role that is deliberately neither a
superuser nor the owner of any table. That is load-bearing rather than tidy:
**a superuser bypasses row-level security unconditionally**, and ``FORCE ROW
LEVEL SECURITY`` does not apply to them. Connect as ``postgres`` and every
policy in ``001_initial.sql`` is still enabled, still forced, and enforcing
nothing — a failure that looks exactly like success.

:func:`tenant_scope` is the only way to obtain a connection for reading or
writing tenant data, and it always issues ``SET LOCAL app.tenant_id`` inside a
transaction. ``SET LOCAL`` rather than ``SET`` matters for the same reason: the
value dies with the transaction, so it cannot leak past a commit onto the next
request that borrows the same pooled connection.

This mirrors :class:`~ait_voice.core.tenancy.TenantScoped` one layer down. In
process, a caller has no way to reach another tenant's partition. Over SQL, a
caller has no way to open a connection without declaring which tenant they are.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ait_voice.core.types import TenantContext

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    import asyncpg

#: The role the application uses. Never `postgres` — see the module docstring.
DEFAULT_APP_USER = "ait_app"


class SuperuserRefused(RuntimeError):
    """The application is connecting as a role that bypasses RLS.

    Raised at startup rather than discovered later, because the symptom of
    getting this wrong is *everything working* while tenant isolation silently
    does nothing.
    """


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """Where the database is, and who we connect as."""

    host: str = "localhost"
    port: int = 5432
    database: str = "ait-voice"
    user: str = DEFAULT_APP_USER
    password: str = ""
    min_size: int = 1
    max_size: int = 10

    @classmethod
    def from_environment(cls, *, owner: bool = False) -> DatabaseSettings:
        """Read settings from the environment.

        ``owner=True`` returns the migration credentials, which are separate on
        purpose: schema changes need authority the running application must not
        have.
        """
        prefix = "AIT_DB_OWNER" if owner else "AIT_DB"
        return cls(
            host=os.environ.get("AIT_DB_HOST", "localhost"),
            port=int(os.environ.get("AIT_DB_PORT", "5432")),
            database=os.environ.get("AIT_DB_NAME", "ait-voice"),
            user=os.environ.get(f"{prefix}_USER", DEFAULT_APP_USER if not owner else "postgres"),
            password=os.environ.get(f"{prefix}_PASSWORD", ""),
        )

    def dsn(self) -> str:
        """A libpq DSN. Never logged — it carries the password."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def describe(self) -> str:
        """Safe to log: everything except the password."""
        return f"{self.user}@{self.host}:{self.port}/{self.database}"


class Database:
    """A connection pool, and the only route to tenant-scoped data."""

    def __init__(self, settings: DatabaseSettings | None = None) -> None:
        self._settings = settings or DatabaseSettings.from_environment()
        self._pool: asyncpg.Pool[Any] | None = None

    @property
    def settings(self) -> DatabaseSettings:
        return self._settings

    async def connect(self, *, allow_superuser: bool = False) -> None:
        """Open the pool, and refuse a role that would defeat RLS.

        ``allow_superuser`` exists for migrations, which legitimately need
        owner authority. Nothing that serves a request should pass it.
        """
        import asyncpg

        self._pool = await asyncpg.create_pool(
            dsn=self._settings.dsn(),
            min_size=self._settings.min_size,
            max_size=self._settings.max_size,
        )
        if not allow_superuser:
            async with self._pool.acquire() as connection:
                is_super = await connection.fetchval(
                    "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
                )
            if is_super:
                await self.close()
                raise SuperuserRefused(
                    f"connected as {self._settings.user!r}, which is a superuser. "
                    "Superusers bypass row-level security unconditionally, so "
                    "tenant isolation would be switched on and enforcing nothing. "
                    f"Connect as {DEFAULT_APP_USER!r} instead."
                )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool[Any]:
        if self._pool is None:
            raise RuntimeError("database is not connected; call connect() first")
        return self._pool

    @asynccontextmanager
    async def tenant_scope(self, tenant: TenantContext) -> AsyncIterator[asyncpg.Connection[Any]]:
        """A connection bound to one tenant, inside a transaction.

        Every read and write of tenant data goes through here. The transaction
        is not optional: ``SET LOCAL`` only has meaning inside one, and using
        plain ``SET`` would leave the tenant set on a pooled connection for
        whoever borrows it next — which is the exact cross-tenant disclosure
        this is meant to prevent.
        """
        async with self.pool.acquire() as connection, connection.transaction():
            # set_config's third argument is `is_local`. Parameterised rather
            # than interpolated: a tenant id reaches this from a URL.
            await connection.execute(
                "SELECT set_config('app.tenant_id', $1, true)", tenant.tenant_id
            )
            yield connection

    @asynccontextmanager
    async def unscoped(self) -> AsyncIterator[asyncpg.Connection[Any]]:
        """A connection with no tenant set, for the tenant registry itself.

        Safe because `tenants` is the one table without row-level security: it
        is the registry that knows about every clinic, which is what lets every
        other table know about exactly one. It holds no patient data.

        Any tenant-scoped table read through here returns nothing, because the
        policy compares against an unset setting and `x = NULL` is never true.
        That is the correct failure direction, and it is why this is safe to
        expose at all.
        """
        async with self.pool.acquire() as connection, connection.transaction():
            yield connection
