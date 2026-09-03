"""Turning a finished call into the records the clinic sees.

The seam between the pipeline and P8. It exists so the pipeline stays a
pipeline: it runs a conversation and reports what happened, and this module
decides what of that is worth keeping and where each part belongs.

Three destinations, deliberately, because they have three different retention
obligations — see :mod:`ait_voice.core.audit` for why that separation is load
bearing rather than tidy.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ait_voice.core.audit import AuditEvent, AuditLog, caller_ref
from ait_voice.core.pipeline import CallResult
from ait_voice.core.records import (
    CallOutcome,
    CallRecord,
    Message,
    Speaker,
    Transcript,
    TranscriptTurn,
)
from ait_voice.core.scheduling import Appointment, AppointmentStatus
from ait_voice.core.types import PHI, TenantContext, Utterance
from ait_voice.db.base import CallRepository

#: What a booking action means for the call's recorded outcome.
_BOOKING_OUTCOMES = {
    AppointmentStatus.BOOKED: CallOutcome.APPOINTMENT_BOOKED,
    AppointmentStatus.RESCHEDULED: CallOutcome.APPOINTMENT_RESCHEDULED,
    AppointmentStatus.CANCELLED: CallOutcome.APPOINTMENT_CANCELLED,
}


def outcome_for(result: CallResult, appointment: Appointment | None = None) -> CallOutcome:
    """Classify a finished call.

    Escalation wins over a booking. A call where the agent booked something and
    *then* handed off is an escalation as far as the clinic is concerned —
    somebody still has to pick up the phone, and burying that under a green
    "booked" is how an unmet handoff goes unnoticed.

    A call with no booking is `no_action` rather than anything more flattering.
    """
    if result.escalation_reason == "dependency_failure":
        return CallOutcome.FAILED
    if result.escalated:
        return CallOutcome.ESCALATED
    if appointment is not None:
        return _BOOKING_OUTCOMES.get(appointment.status, CallOutcome.NO_ACTION)
    return CallOutcome.NO_ACTION


def transcript_from(call_id: str, history: list[Utterance]) -> Transcript:
    """Build a transcript from the conversation history.

    Speaker alternates caller-then-agent because that is the order the pipeline
    appends them. Deriving it from position rather than storing a speaker on
    every utterance keeps :class:`Utterance` free of a field only this module
    would read.
    """
    turns = tuple(
        TranscriptTurn(
            speaker=Speaker.CALLER if index % 2 == 0 else Speaker.AGENT,
            text=utterance.text,
        )
        for index, utterance in enumerate(history)
    )
    return Transcript(call_id=call_id, turns=turns)


async def record_call(
    tenant: TenantContext,
    result: CallResult,
    store: CallRepository,
    *,
    history: list[Utterance] | None = None,
    caller_number: str | None = None,
    started_at: datetime | None = None,
    duration_seconds: float = 0.0,
    language: str = "en",
    appointment: Appointment | None = None,
    audit: AuditLog | None = None,
) -> CallRecord:
    """Persist a finished call, and note in the audit log that it happened.

    The audit entry carries counts and codes only. The caller's number goes to
    the record, the words go to the transcript, and neither reaches the log.
    """
    reference = caller_ref(caller_number, tenant_id=tenant.tenant_id) if caller_number else ""
    record = CallRecord(
        call_id=result.call_id,
        tenant_id=tenant.tenant_id,
        started_at=started_at or datetime.now(UTC),
        duration_seconds=duration_seconds,
        turns=result.turns,
        outcome=outcome_for(result, appointment),
        appointment_id=appointment.appointment_id if appointment else None,
        language=language,
        caller=PHI(caller_number) if caller_number else None,
        caller_ref=reference,
        escalation_reason=result.escalation_reason,
        escalation_route=result.escalation_route,
        p95_ms=result.p95_ms,
        latency_observable=result.latency_observable,
    )
    await store.add(tenant, record)

    if history:
        await store.attach_transcript(tenant, transcript_from(result.call_id, history))

    if audit and appointment is not None:
        # The booking is its own auditable fact, separate from the call ending.
        # Times and ids only — an appointment's reason is why someone is
        # unwell, and that never reaches the security log.
        await audit.record(
            tenant,
            AuditEvent.APPOINTMENT_BOOKED
            if appointment.status is not AppointmentStatus.CANCELLED
            else AuditEvent.APPOINTMENT_CANCELLED,
            call_id=result.call_id,
            caller_ref=reference or None,
            appointment_id=appointment.appointment_id,
            starts_at=appointment.starts_at.isoformat(),
        )

    if audit:
        await audit.record(
            tenant,
            AuditEvent.CALL_ENDED,
            call_id=result.call_id,
            caller_ref=reference or None,
            turns=result.turns,
            outcome=str(record.outcome),
            escalated=result.escalated,
            duration_seconds=round(duration_seconds, 1),
        )
    return await store.get(tenant, result.call_id) or record


async def take_message(
    tenant: TenantContext,
    call_id: str,
    store: CallRepository,
    *,
    note: str,
    caller_number: str | None = None,
    at: datetime | None = None,
    audit: AuditLog | None = None,
) -> Message:
    """Record a callback the agent promised on the clinic's behalf.

    Worth being precise about what this is: an obligation on the clinic that
    nothing in this system can discharge. It shows on both surfaces so that an
    unmet promise is visible to someone.
    """
    message = Message(
        message_id=str(uuid.uuid4()),
        call_id=call_id,
        tenant_id=tenant.tenant_id,
        taken_at=at or datetime.now(UTC),
        caller=PHI(caller_number) if caller_number else None,
        note=PHI(note),
    )
    await store.add_message(tenant, message)
    if audit:
        await audit.record(
            tenant,
            AuditEvent.MESSAGE_TAKEN,
            call_id=call_id,
            message_id=message.message_id,
        )
    return message
