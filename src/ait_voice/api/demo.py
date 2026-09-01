"""A seeded API for looking at the UI without a live call.

Synthetic data only. `project.md` forbids real call audio, transcripts or
caller identity in this repository or on a development workstation, so every
name, number and sentence below is invented.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from ait_voice.api.app import Services, create_app
from ait_voice.api.auth import Principal, Role
from ait_voice.core.records import (
    CallOutcome,
    CallRecord,
    Message,
    Speaker,
    Transcript,
    TranscriptTurn,
)
from ait_voice.core.tenancy import OutOfHoursPolicy, StaffedHours, TenantConfig
from ait_voice.core.types import PHI, Region

DEMO_TRANSCRIPT = (
    (Speaker.AGENT, "You're speaking with an AI assistant at Northside Medical, "
                    "and this call is recorded. How can I help?"),
    (Speaker.CALLER, "Hi, I need to move my appointment next week."),
    (Speaker.AGENT, "Of course. Can I take your date of birth?"),
    (Speaker.CALLER, "Fourth of March, nineteen eighty-five."),
    (Speaker.AGENT, "Thank you. I have you on Tuesday at ten thirty. "
                    "What would suit you better?"),
)


def build_demo() -> Services:
    services = Services()
    services.tenants.add(
        TenantConfig(
            tenant_id="northside",
            region=Region.US,
            clinic_name="Northside Medical",
            greeting="How can I help?",
            staffed_hours=StaffedHours.weekdays(),
            escalation_number="+15551230000",
            out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
        )
    )
    services.tenants.add(
        TenantConfig(
            tenant_id="parkclinic",
            region=Region.INDIA,
            clinic_name="Park Clinic",
            greeting="How may I help you today?",
            languages=("en", "hi", "hi-en"),
            staffed_hours=StaffedHours.never(),
            out_of_hours=OutOfHoursPolicy.EXISTING_AFTER_HOURS,
            outbound_registered=True,
        )
    )

    now = datetime.now(UTC)
    north = services.tenants.resolve("northside")
    seed = [
        ("call-001", 45, CallOutcome.APPOINTMENT_BOOKED, "+15551110041", 130.0, 4, None),
        ("call-002", 120, CallOutcome.ESCALATED, "+15551110072", 38.0, 1,
         "caller_requested_human"),
        ("call-003", 300, CallOutcome.APPOINTMENT_RESCHEDULED, "+15551110019", 96.0, 3, None),
        ("call-004", 900, CallOutcome.ESCALATED, "+15551110088", 22.0, 1, "clinical_content"),
        ("call-005", 1500, CallOutcome.MESSAGE_TAKEN, "+15551110055", 74.0, 3, None),
    ]
    for call_id, minutes_ago, outcome, number, seconds, turns, reason in seed:
        services.calls.add(
            north,
            CallRecord(
                call_id=call_id,
                tenant_id="northside",
                started_at=now - timedelta(minutes=minutes_ago),
                duration_seconds=seconds,
                turns=turns,
                outcome=outcome,
                caller=PHI(number),
                escalation_reason=reason,
                p95_ms=860.0,
            ),
        )
    services.calls.attach_transcript(
        north,
        Transcript(
            "call-001",
            tuple(TranscriptTurn(speaker, PHI(text)) for speaker, text in DEMO_TRANSCRIPT),
        ),
    )
    services.calls.add_message(
        north,
        Message(
            message_id="msg-001",
            call_id="call-005",
            tenant_id="northside",
            taken_at=now - timedelta(minutes=25),
            caller=PHI("+15551110055"),
            note=PHI("Asking about a repeat prescription. Wants a call before 5pm."),
        ),
    )

    park = services.tenants.resolve("parkclinic")
    services.calls.add(
        park,
        CallRecord(
            call_id="call-101",
            tenant_id="parkclinic",
            started_at=now - timedelta(minutes=80),
            duration_seconds=142.0,
            turns=5,
            outcome=CallOutcome.APPOINTMENT_BOOKED,
            language="hi-en",
            caller=PHI("+919990001111"),
            p95_ms=410.0,
            # This call ran over a bundled transport, so the figure above stops
            # short of the audio the caller heard.
            latency_observable=False,
        ),
    )
    services.principals.issue(
        Principal(
            principal_id="operator",
            role=Role.OPERATOR,
            display_name="AI Thinkers operator",
        ),
        os.environ.get("AIT_OPERATOR_TOKEN", "demo-operator-token"),
    )
    services.principals.issue(
        Principal(
            principal_id="clinic:northside",
            role=Role.CLINIC,
            tenant_id="northside",
            display_name="Northside Medical",
        ),
        os.environ.get("AIT_CLINIC_TOKEN", "demo-clinic-token"),
    )
    return services


def demo_app():  # noqa: ANN201 - FastAPI
    return create_app(build_demo(), cors_origins=["http://localhost:5173"])
