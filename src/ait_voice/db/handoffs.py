"""The handoff queue, in Postgres.

Ordering is the load-bearing part: urgency before recency, so a clinic working
down the list reaches the clinical caller before the routine one who rang two
hours earlier. In memory that was a sort key; here it is an ORDER BY with an
explicit rank, written out rather than relying on the enum's alphabetical order
— which would put `clinical` above `routine` by accident and `soon` above
`urgent` wrongly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from ait_voice.core.handoff import (
    HandoffContext,
    HandoffDecision,
    HandoffMethod,
    HandoffRecord,
    Urgency,
)
from ait_voice.core.types import PHI, TenantContext
from ait_voice.db.connection import Database

#: Higher sorts first. Kept in SQL alongside the Python ordering it mirrors.
_URGENCY_RANK = """
    CASE urgency
        WHEN 'clinical' THEN 3
        WHEN 'urgent'   THEN 2
        WHEN 'soon'     THEN 1
        ELSE 0
    END DESC, at ASC
"""


def _to_record(row: Any) -> HandoffRecord:  # noqa: ANN401 - asyncpg.Record
    return HandoffRecord(
        handoff_id=str(row["handoff_id"]),
        context=HandoffContext(
            call_id=row["call_id"],
            tenant_id=row["tenant_id"],
            reason=row["reason"],
            urgency=Urgency(row["urgency"]),
            caller_number=PHI(row["caller"]) if row["caller"] else None,
            said=tuple(PHI(line) for line in row["said"]),
            turns=row["turns"],
            recovery_attempted=row["recovery_attempted"],
            started_at=row["at"],
        ),
        decision=HandoffDecision(method=HandoffMethod(row["method"])),
        at=row["at"],
        acknowledged_at=row["acknowledged_at"],
        acknowledged_by=row["acknowledged_by"],
    )


class PostgresHandoffQueue:
    """Mirrors :class:`~ait_voice.core.handoff.HandoffQueue`, async."""

    def __init__(self, database: Database) -> None:
        self._db = database

    async def add(
        self,
        tenant: TenantContext,
        context: HandoffContext,
        decision: HandoffDecision,
        *,
        at: datetime | None = None,
    ) -> HandoffRecord:
        handoff_id = uuid.uuid4()
        moment = at or datetime.now(UTC)
        async with self._db.tenant_scope(tenant) as c:
            await c.execute(
                """
                INSERT INTO handoffs (
                    handoff_id, tenant_id, call_id, reason, urgency, method,
                    caller, said, turns, recovery_attempted, at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                """,
                handoff_id,
                tenant.tenant_id,
                context.call_id,
                context.reason,
                str(context.urgency),
                str(decision.method),
                context.caller_number.reveal() if context.caller_number else None,
                [line.reveal() for line in context.said],
                context.turns,
                context.recovery_attempted,
                moment,
            )
        return HandoffRecord(
            handoff_id=str(handoff_id), context=context, decision=decision, at=moment
        )

    async def get(self, tenant: TenantContext, handoff_id: str) -> HandoffRecord | None:
        try:
            identifier = uuid.UUID(handoff_id)
        except ValueError:
            return None
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow("SELECT * FROM handoffs WHERE handoff_id = $1", identifier)
        return _to_record(row) if row else None

    async def pending(self, tenant: TenantContext) -> list[HandoffRecord]:
        """Open handoffs, most urgent first, oldest first within an urgency."""
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                "SELECT * FROM handoffs WHERE acknowledged_at IS NULL ORDER BY " + _URGENCY_RANK  # noqa: S608 - a module constant, no input
            )
        return [_to_record(row) for row in rows]

    async def all(self, tenant: TenantContext) -> list[HandoffRecord]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch("SELECT * FROM handoffs ORDER BY at DESC")
        return [_to_record(row) for row in rows]

    async def acknowledge(
        self,
        tenant: TenantContext,
        handoff_id: str,
        *,
        by: str,
        at: datetime | None = None,
    ) -> HandoffRecord | None:
        """Mark that a person picked this up. Never deletes.

        The record is how a clinic learns a handoff went unanswered for two
        hours, so removing it on acknowledgement would delete the evidence of
        the thing worth measuring.
        """
        try:
            identifier = uuid.UUID(handoff_id)
        except ValueError:
            return None
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                UPDATE handoffs SET acknowledged_at = $2, acknowledged_by = $3
                WHERE handoff_id = $1 RETURNING *
                """,
                identifier,
                at or datetime.now(UTC),
                by,
            )
        return _to_record(row) if row else None
