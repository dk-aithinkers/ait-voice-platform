"""The migration runner.

Migrations are the one piece of code that runs with authority the application
deliberately lacks, so getting it wrong is expensive in a way a request handler
is not.
"""

from __future__ import annotations

import pathlib

import pytest

from ait_voice.db.connection import Database
from ait_voice.db.migrate import (
    MIGRATIONS,
    Migration,
    MigrationModified,
    apply,
    load,
)
from tests.conftest import requires_postgres


class TestLoading:
    def test_the_shipped_migrations_load(self) -> None:
        migrations = load()

        assert migrations, "no migrations found — check MIGRATIONS points at db/migrations"
        assert migrations[0].name == "001_initial.sql"

    def test_they_are_ordered_by_filename(self) -> None:
        """Filename order is the contract, so a new file must be numbered."""
        names = [m.name for m in load()]
        assert names == sorted(names)

    def test_the_directory_resolves(self) -> None:
        assert MIGRATIONS.is_dir(), f"{MIGRATIONS} is not a directory"

    def test_an_empty_directory_yields_nothing(self, tmp_path: pathlib.Path) -> None:
        assert load(tmp_path) == []

    def test_the_checksum_follows_the_content(self) -> None:
        assert Migration("a.sql", "SELECT 1").checksum != (Migration("a.sql", "SELECT 2").checksum)

    def test_the_checksum_ignores_the_filename(self) -> None:
        """Renaming a file is not the change worth detecting; editing it is."""
        assert Migration("a.sql", "SELECT 1").checksum == (Migration("b.sql", "SELECT 1").checksum)


@requires_postgres
class TestApplying:
    async def test_applying_twice_is_a_no_op(self, owner: Database) -> None:
        await apply(owner, load())

        assert await apply(owner, load()) == []

    async def test_a_new_migration_is_applied(self, owner: Database) -> None:
        migration = Migration(
            name="999_test_only.sql",
            sql="CREATE TABLE IF NOT EXISTS migration_probe (id integer PRIMARY KEY)",
        )
        try:
            applied = await apply(owner, [*load(), migration])
            assert "999_test_only.sql" in applied

            async with owner.unscoped() as c:
                assert await c.fetchval("SELECT to_regclass('migration_probe')")
        finally:
            async with owner.unscoped() as c:
                await c.execute("DROP TABLE IF EXISTS migration_probe")
                await c.execute(
                    "DELETE FROM schema_migrations WHERE filename = '999_test_only.sql'"
                )

    async def test_editing_an_applied_migration_is_refused(self, owner: Database) -> None:
        """The schema in front of you would no longer be the one the file
        describes — which is how two environments diverge unnoticed."""
        await apply(owner, load())
        tampered = [Migration(name="001_initial.sql", sql="-- rewritten")]

        with pytest.raises(MigrationModified, match="modified since it was applied"):
            await apply(owner, tampered)

    async def test_the_ledger_records_what_ran(self, owner: Database) -> None:
        await apply(owner, load())

        async with owner.unscoped() as c:
            rows = await c.fetch("SELECT filename FROM schema_migrations")

        assert "001_initial.sql" in {r["filename"] for r in rows}

    async def test_rls_is_forced_on_every_scoped_table(self, owner: Database) -> None:
        """Without FORCE the owner bypasses the policy it just created, so this
        is the difference between protection and the appearance of it."""
        await apply(owner, load())

        async with owner.unscoped() as c:
            rows = await c.fetch(
                """
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN (
                    'call_records','transcripts','appointments','messages',
                    'handoffs','intake_records','intake_values','consents'
                )
                """
            )

        assert len(rows) == 8
        for row in rows:
            assert row["relrowsecurity"], f"{row['relname']} has RLS disabled"
            assert row["relforcerowsecurity"], f"{row['relname']} does not FORCE RLS"

    async def test_the_tenants_table_is_deliberately_not_secured(self, owner: Database) -> None:
        """It is the registry that knows about every clinic, and holds no PHI.
        Asserted so that enabling RLS on it later is a deliberate act."""
        await apply(owner, load())

        async with owner.unscoped() as c:
            secured = await c.fetchval(
                "SELECT relrowsecurity FROM pg_class WHERE relname = 'tenants'"
            )

        assert secured is False

    async def test_the_application_role_has_no_ddl_rights(self, owner: Database) -> None:
        """A bug in a request handler must not be able to alter a table."""
        await apply(owner, load())

        async with owner.unscoped() as c:
            can_create = await c.fetchval(
                "SELECT has_schema_privilege('ait_app', 'public', 'CREATE')"
            )

        assert can_create is False


@requires_postgres
class TestTheCommand:
    """`ait-voice-migrate` — what a deploy actually runs."""

    async def test_it_reports_what_it_applied(
        self, capsys: pytest.CaptureFixture[str], owner: Database
    ) -> None:
        from ait_voice.db import migrate

        # A clean slate, so the command has something to report.
        async with owner.unscoped() as c:
            await c.execute("DROP TABLE IF EXISTS schema_migrations")

        assert await migrate._main() == 0  # noqa: SLF001

        out = capsys.readouterr().out
        assert "001_initial.sql" in out
        assert "database:" in out

    async def test_it_says_so_when_there_is_nothing_to_do(
        self, capsys: pytest.CaptureFixture[str], owner: Database
    ) -> None:
        from ait_voice.db import migrate

        await migrate._main()  # noqa: SLF001
        capsys.readouterr()

        assert await migrate._main() == 0  # noqa: SLF001
        assert "already up to date" in capsys.readouterr().out

    async def test_it_never_prints_the_password(
        self, capsys: pytest.CaptureFixture[str], owner: Database
    ) -> None:
        """The DSN carries a credential; `describe()` is the loggable half."""
        import os

        from ait_voice.db import migrate

        password = os.environ.get("AIT_DB_OWNER_PASSWORD", "root")
        await migrate._main()  # noqa: SLF001

        out = capsys.readouterr().out
        assert password not in out or password == "postgres"  # avoid a false pass

    def test_main_wraps_the_async_entry_point(self, capsys: pytest.CaptureFixture[str]) -> None:
        from ait_voice.db import migrate

        assert migrate.main() == 0
        assert "database:" in capsys.readouterr().out
