"""Call records, transcripts and callback messages, in Postgres.

Every query here runs inside :meth:`Database.tenant_scope`, so row-level
security bounds it whether or not the SQL mentions ``tenant_id``. Several
queries include the filter anyway — belt and braces, and it keeps the intent
readable to someone who has not yet read ``001_initial.sql``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from ait_voice.core.records import (
    ActivitySummary,
    CallOutcome,
    CallRecord,
    Message,
    Speaker,
    Transcript,
    TranscriptTurn,
)
from ait_voice.core.types import PHI, TenantContext
from ait_voice.db.connection import Database


def _to_record(row: Any) -> CallRecord:  # noqa: ANN401 - asyncpg.Record
    return CallRecord(
        call_id=row["call_id"],
        tenant_id=row["tenant_id"],
        started_at=row["started_at"],
        duration_seconds=row["duration_seconds"],
        turns=row["turns"],
        outcome=CallOutcome(row["outcome"]),
        language=row["language"],
        caller=PHI(row["caller"]) if row["caller"] else None,
        caller_ref=row["caller_ref"],
        escalation_reason=row["escalation_reason"],
        escalation_route=row["escalation_route"],
        p95_ms=row["p95_ms"],
        latency_observable=row["latency_observable"],
        has_transcript=row["has_transcript"],
        appointment_id=str(row["appointment_id"]) if row["appointment_id"] else None,
    )


def _to_message(row: Any) -> Message:  # noqa: ANN401 - asyncpg.Record
    return Message(
        message_id=str(row["message_id"]),
        call_id=row["call_id"],
        tenant_id=row["tenant_id"],
        taken_at=row["taken_at"],
        caller=PHI(row["caller"]) if row["caller"] else None,
        note=PHI(row["note"]) if row["note"] else None,
        resolved_at=row["resolved_at"],
    )


class PostgresCallStore:
    """Mirrors :class:`~ait_voice.core.records.CallStore`, async."""

    def __init__(self, database: Database) -> None:
        self._db = database

    # -- records ---------------------------------------------------------

    async def add(self, tenant: TenantContext, record: CallRecord) -> CallRecord:
        async with self._db.tenant_scope(tenant) as c:
            await c.execute(
                """
                INSERT INTO call_records (
                    call_id, tenant_id, started_at, duration_seconds, turns,
                    outcome, language, caller, caller_ref, escalation_reason,
                    escalation_route, p95_ms, latency_observable, appointment_id
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                ON CONFLICT (tenant_id, call_id) DO UPDATE SET
                    duration_seconds = EXCLUDED.duration_seconds,
                    turns = EXCLUDED.turns,
                    outcome = EXCLUDED.outcome,
                    escalation_reason = EXCLUDED.escalation_reason,
                    escalation_route = EXCLUDED.escalation_route,
                    p95_ms = EXCLUDED.p95_ms,
                    latency_observable = EXCLUDED.latency_observable,
                    appointment_id = EXCLUDED.appointment_id
                """,
                record.call_id,
                record.tenant_id,
                record.started_at,
                record.duration_seconds,
                record.turns,
                str(record.outcome),
                record.language,
                record.caller.reveal() if record.caller else None,
                record.caller_ref,
                record.escalation_reason,
                record.escalation_route,
                record.p95_ms,
                record.latency_observable,
                uuid.UUID(record.appointment_id) if record.appointment_id else None,
            )
        return record

    async def get(self, tenant: TenantContext, call_id: str) -> CallRecord | None:
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                SELECT r.*, EXISTS (
                    SELECT 1 FROM transcripts t
                    WHERE t.tenant_id = r.tenant_id AND t.call_id = r.call_id
                ) AS has_transcript
                FROM call_records r
                WHERE r.call_id = $1
                """,
                call_id,
            )
        return _to_record(row) if row else None

    async def recent(
        self,
        tenant: TenantContext,
        *,
        limit: int = 50,
        since: datetime | None = None,
    ) -> list[CallRecord]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT r.*, EXISTS (
                    SELECT 1 FROM transcripts t
                    WHERE t.tenant_id = r.tenant_id AND t.call_id = r.call_id
                ) AS has_transcript
                FROM call_records r
                WHERE ($1::timestamptz IS NULL OR r.started_at >= $1)
                ORDER BY r.started_at DESC
                LIMIT $2
                """,
                since,
                limit,
            )
        return [_to_record(row) for row in rows]

    async def count(self, tenant: TenantContext) -> int:
        async with self._db.tenant_scope(tenant) as c:
            return await c.fetchval("SELECT count(*) FROM call_records") or 0

    # -- transcripts -----------------------------------------------------

    async def attach_transcript(
        self, tenant: TenantContext, transcript: Transcript
    ) -> CallRecord | None:
        """Store a transcript. Returns None when no such call exists here.

        Which is also what a cross-tenant attempt gets: the foreign key cannot
        see the other clinic's call, so there is nothing to attach to.
        """
        if await self.get(tenant, transcript.call_id) is None:
            return None
        async with self._db.tenant_scope(tenant) as c:
            await c.execute("DELETE FROM transcripts WHERE call_id = $1", transcript.call_id)
            await c.executemany(
                """
                INSERT INTO transcripts (call_id, tenant_id, turn_index, speaker, text)
                VALUES ($1,$2,$3,$4,$5)
                """,
                [
                    (
                        transcript.call_id,
                        tenant.tenant_id,
                        index,
                        str(turn.speaker),
                        turn.text.reveal(),
                    )
                    for index, turn in enumerate(transcript.turns)
                ],
            )
        return await self.get(tenant, transcript.call_id)

    async def transcript(self, tenant: TenantContext, call_id: str) -> Transcript | None:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT speaker, text FROM transcripts
                WHERE call_id = $1 ORDER BY turn_index
                """,
                call_id,
            )
        if not rows:
            return None
        return Transcript(
            call_id=call_id,
            turns=tuple(
                TranscriptTurn(speaker=Speaker(r["speaker"]), text=PHI(r["text"])) for r in rows
            ),
        )

    async def erase_transcript(self, tenant: TenantContext, call_id: str) -> bool:
        """Delete a call's words, keeping the record that the call happened.

        DPDP erasure at the granularity a clinic can live with: the operational
        history survives, the patient's words do not.
        """
        async with self._db.tenant_scope(tenant) as c:
            status = await c.execute("DELETE FROM transcripts WHERE call_id = $1", call_id)
        # asyncpg's execute() returns an untyped command tag.
        return bool(status != "DELETE 0")

    # -- messages --------------------------------------------------------

    async def add_message(self, tenant: TenantContext, message: Message) -> Message:
        async with self._db.tenant_scope(tenant) as c:
            await c.execute(
                """
                INSERT INTO messages (
                    message_id, tenant_id, call_id, taken_at, caller, note, resolved_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (message_id) DO NOTHING
                """,
                uuid.UUID(message.message_id),
                message.tenant_id,
                message.call_id,
                message.taken_at,
                message.caller.reveal() if message.caller else None,
                message.note.reveal() if message.note else None,
                message.resolved_at,
            )
        return message

    async def messages(self, tenant: TenantContext, *, open_only: bool = False) -> list[Message]:
        async with self._db.tenant_scope(tenant) as c:
            rows = await c.fetch(
                """
                SELECT * FROM messages
                WHERE ($1::boolean IS NOT TRUE OR resolved_at IS NULL)
                ORDER BY taken_at DESC
                """,
                open_only,
            )
        return [_to_message(row) for row in rows]

    async def resolve_message(
        self, tenant: TenantContext, message_id: str, *, at: datetime | None = None
    ) -> Message | None:
        try:
            identifier = uuid.UUID(message_id)
        except ValueError:
            return None
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                UPDATE messages SET resolved_at = $2
                WHERE message_id = $1
                RETURNING *
                """,
                identifier,
                at or datetime.now(UTC),
            )
        return _to_message(row) if row else None

    # -- aggregates ------------------------------------------------------

    async def summarize(
        self,
        tenant: TenantContext,
        *,
        window_days: int = 7,
        now: datetime | None = None,
    ) -> ActivitySummary:
        """Counted facts over a window. Nothing derived, nothing modelled.

        No hours-saved figure, here or anywhere: RAID item I-02 records that
        the success metrics carry no baseline and no measurement window.
        """
        cutoff = (now or datetime.now(UTC)) - timedelta(days=window_days)
        async with self._db.tenant_scope(tenant) as c:
            row = await c.fetchrow(
                """
                SELECT
                    count(*) AS answered,
                    count(*) FILTER (WHERE outcome = 'appointment_booked') AS booked,
                    count(*) FILTER (
                        WHERE outcome IN ('appointment_rescheduled','appointment_cancelled')
                    ) AS changed,
                    count(*) FILTER (WHERE outcome = 'escalated') AS escalated,
                    coalesce(avg(duration_seconds), 0) AS average_duration
                FROM call_records WHERE started_at >= $1
                """,
                cutoff,
            )
            open_messages = await c.fetchval(
                "SELECT count(*) FROM messages WHERE resolved_at IS NULL"
            )
        return ActivitySummary(
            window_days=window_days,
            calls_answered=row["answered"],
            appointments_booked=row["booked"],
            appointments_changed=row["changed"],
            escalated=row["escalated"],
            messages_open=open_messages or 0,
            average_duration_seconds=float(row["average_duration"]),
        )
