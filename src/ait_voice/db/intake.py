"""Intake records, in Postgres.

Only confirmed values ever reach here. :meth:`IntakeSession.completed` refuses
to produce a record while an identifier is unconfirmed (FR3.2), so this store
never has to decide whether a value was checked — by the time it sees one, it
was read back to the caller and agreed to.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from ait_voice.core.intake import FIELDS_BY_NAME, FieldName, IntakeRecord
from ait_voice.core.types import PHI, TenantContext
from ait_voice.db.connection import Database


def _revive(field: FieldName, raw: str) -> object:
    """Turn a stored string back into the type the field is captured as.

    Dates are the reason this exists: `date_of_birth` is a `date` in memory and
    text in the row, and returning a string would quietly change what
    `record.get()` hands to a caller.
    """
    spec = FIELDS_BY_NAME.get(field)
    if spec is None:  # pragma: no cover - the enum is closed
        return raw
    if field is FieldName.DATE_OF_BIRTH:
        return date.fromisoformat(raw)
    return raw


def _stored(value: object) -> str:
    """The text form written to the row.

    Dates round-trip through ISO 8601 so `_revive` can reconstruct the type
    rather than silently handing a caller a string where it expected a date.
    """
    return value.isoformat() if isinstance(value, date) else str(value)


class PostgresIntakeStore:
    """Mirrors :class:`~ait_voice.core.intake.IntakeStore`, async."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def add(self, tenant: TenantContext, record: IntakeRecord) -> IntakeRecord:
        async with self._db.tenant_scope(tenant) as c:
            await c.execute(
                """
                INSERT INTO intake_records (intake_id, tenant_id, call_id, captured_at)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (intake_id) DO NOTHING
                """,
                uuid.UUID(record.intake_id),
                record.tenant_id,
                record.call_id,
                record.captured_at,
            )
            await c.executemany(
                """
                INSERT INTO intake_values (intake_id, tenant_id, field, value)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (intake_id, field) DO UPDATE SET value = EXCLUDED.value
                """,
                [
                    (
                        uuid.UUID(record.intake_id),
                        record.tenant_id,
                        str(name),
                        _stored(wrapped.reveal()),
                    )
                    for name, wrapped in record.values.items()
                ],
            )
        return record

    async def _hydrate(self, row: Any, values: list[Any]) -> IntakeRecord:  # noqa: ANN401
        return IntakeRecord(
            intake_id=str(row["intake_id"]),
            tenant_id=row["tenant_id"],
            call_id=row["call_id"],
            captured_at=row["captured_at"],
            values={
                FieldName(v["field"]): PHI(_revive(FieldName(v["field"]), v["value"]))
                for v in values
                if str(v["intake_id"]) == str(row["intake_id"])
            },
        )

    async def get(self, tenant: TenantContext, intake_id: str) -> IntakeRecord | None:
        try:
            identifier = uuid.UUID(intake_id)
        except ValueError:
            return None
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow("SELECT * FROM intake_records WHERE intake_id = $1", identifier)
            if row is None:
                return None
            values = await c.fetch(
                "SELECT intake_id, field, value FROM intake_values WHERE intake_id = $1",
                identifier,
            )
        return await self._hydrate(row, list(values))

    async def _many(self, tenant: TenantContext, rows: list[Any]) -> list[IntakeRecord]:  # noqa: ANN401
        if not rows:
            return []
        async with self._db.tenant_scope(tenant) as c:
            values = await c.fetch(
                "SELECT intake_id, field, value FROM intake_values WHERE intake_id = ANY($1)",
                [row["intake_id"] for row in rows],
            )
        return [await self._hydrate(row, list(values)) for row in rows]

    async def for_call(self, tenant: TenantContext, call_id: str) -> list[IntakeRecord]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                "SELECT * FROM intake_records WHERE call_id = $1 ORDER BY captured_at",
                call_id,
            )
        return await self._many(tenant, list(rows))

    async def recent(self, tenant: TenantContext, *, limit: int = 50) -> list[IntakeRecord]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                "SELECT * FROM intake_records ORDER BY captured_at DESC LIMIT $1",
                limit,
            )
        return await self._many(tenant, list(rows))

    async def erase(self, tenant: TenantContext, intake_id: str) -> bool:
        """DPDP erasure. Intake is content, and content is erasable.

        The values cascade with the record, so nothing is left orphaned.
        """
        try:
            identifier = uuid.UUID(intake_id)
        except ValueError:
            return False
        async with self._db.tenant_scope(tenant) as c:
            status = await c.execute("DELETE FROM intake_records WHERE intake_id = $1", identifier)
        # asyncpg's execute() returns an untyped command tag.
        return bool(status != "DELETE 0")
