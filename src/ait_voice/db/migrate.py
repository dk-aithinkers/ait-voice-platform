"""Migration runner.

Plain SQL files applied in filename order, with what has run recorded in the
database. No ORM and no migration framework: the schema is Postgres-specific by
choice — row-level security, partial unique indexes, array columns — and a tool
that abstracts the dialect would abstract away the parts doing the work.

Migrations run as the owner. The application runs as ``ait_app``, which has no
schema authority at all, so a bug in a request handler cannot alter a table.
"""

from __future__ import annotations

import asyncio
import hashlib
import pathlib
import sys
from dataclasses import dataclass

from ait_voice.db.connection import Database, DatabaseSettings

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "db" / "migrations"

_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    text PRIMARY KEY,
    checksum    text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    """One migration file, read before any connection is opened."""

    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()


def load(directory: pathlib.Path = MIGRATIONS) -> list[Migration]:
    """Read the migration files, in filename order.

    Synchronous, and called before the async work begins: reading files inside
    the event loop blocks it, and there is no reason to. Filename order is the
    contract — prefix a new file with the next number.
    """
    return [
        Migration(name=path.name, sql=path.read_text()) for path in sorted(directory.glob("*.sql"))
    ]


class MigrationModified(RuntimeError):
    """An applied migration changed on disk.

    The schema in front of you is then not the one the file describes. Editing
    an applied migration is how two environments diverge with nothing to show
    for it, so this refuses rather than re-running or ignoring.
    """


async def apply(database: Database, migrations: list[Migration]) -> list[str]:
    """Apply every migration not yet recorded. Returns what it ran."""
    applied: list[str] = []
    async with database.unscoped() as connection:
        await connection.execute(_LEDGER)
        seen = {
            row["filename"]: row["checksum"]
            for row in await connection.fetch("SELECT filename, checksum FROM schema_migrations")
        }

        for migration in migrations:
            if migration.name in seen:
                if seen[migration.name] != migration.checksum:
                    raise MigrationModified(
                        f"{migration.name} has been modified since it was applied. "
                        "Add a new migration rather than editing an applied one."
                    )
                continue

            await connection.execute(migration.sql)
            await connection.execute(
                "INSERT INTO schema_migrations (filename, checksum) VALUES ($1, $2)",
                migration.name,
                migration.checksum,
            )
            applied.append(migration.name)
    return applied


async def _main() -> int:
    settings = DatabaseSettings.from_environment(owner=True)
    database = Database(settings)
    migrations = load()
    # Owner credentials: migrations need the schema authority the running
    # application deliberately lacks.
    await database.connect(allow_superuser=True)
    try:
        ran = await apply(database, migrations)
    finally:
        await database.close()

    print(f"\n  database: {settings.describe()}")
    if ran:
        for name in ran:
            print(f"  applied:  {name}")
    else:
        print("  applied:  nothing — already up to date")
    print()
    return 0


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
