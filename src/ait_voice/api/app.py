"""The JSON API behind the operator console and the clinic view.

Read-heavy by design. The clinic surface is read-only per
`scope-document.md`; the only writes are operator configuration and resolving
a callback message, which is the clinic discharging an obligation rather than
changing anything about the system.

**Every data route depends on `scope`.** That dependency is the only way to
obtain a :class:`TenantContext`, and every store method needs one, so a handler
that forgets tenant scoping does not compile into anything useful — it has
nothing to pass. This is the HTTP-side equivalent of the explicit-tenant-
parameter convention, and it is what makes a separate client safe to add.
"""

# NOTE: deliberately no ``from __future__ import annotations`` here. FastAPI
# resolves handler annotations at runtime against module globals; with deferred
# annotations the dependency aliases defined inside create_app() are unresolvable
# strings, and FastAPI silently reinterprets them as query parameters. The
# symptom is a 422 asking for a "principal" query param on an authenticated
# route, which is a confusing way to learn this.
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ait_voice.api.auth import (
    AuthError,
    ForbiddenError,
    Principal,
    PrincipalStore,
    resolve_scope,
    seed_from_environment,
)
from ait_voice.core.scheduling import (
    AppointmentNotFound,
    BookingHours,
    SlotUnavailable,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import TenantContext
from ait_voice.db.base import (
    CalendarRepository,
    CallRepository,
    ConsentRepository,
    HandoffRepository,
    IntakeRepository,
    TenantRepository,
)
from ait_voice.db.calls import PostgresCallStore
from ait_voice.db.connection import Database
from ait_voice.db.consent import PostgresConsentLedger
from ait_voice.db.handoffs import PostgresHandoffQueue
from ait_voice.db.intake import PostgresIntakeStore
from ait_voice.db.memory import (
    InMemoryCalendar,
    InMemoryCallStore,
    InMemoryConsentLedger,
    InMemoryHandoffQueue,
    InMemoryIntakeStore,
    InMemoryTenantStore,
)
from ait_voice.db.scheduling import PostgresCalendar
from ait_voice.db.tenants import PostgresTenantStore


class Services:
    """Everything the API reads and writes.

    Held on the app rather than in module globals so tests build their own and
    two instances never share a store.

    Typed against the protocols in :mod:`ait_voice.db.base`, never against a
    concrete store. That is what makes the persistence choice a wiring decision
    rather than something the handlers know about — and it means handing this
    a synchronous :class:`~ait_voice.core.records.CallStore` is a type error
    under `mypy --strict`, not a deployment that loses every call on restart.

    Defaults are in-memory, so a test or the demo app can construct one with no
    arguments and no database. :meth:`from_database` is what a real deployment
    uses; see :mod:`ait_voice.db.memory` for why the default is not.
    """

    def __init__(
        self,
        *,
        tenants: TenantRepository | None = None,
        calls: CallRepository | None = None,
        principals: PrincipalStore | None = None,
        calendar: CalendarRepository | None = None,
        booking_hours: BookingHours | None = None,
        handoffs: HandoffRepository | None = None,
        intake: IntakeRepository | None = None,
        consent: ConsentRepository | None = None,
    ) -> None:
        self.tenants = tenants or InMemoryTenantStore()
        self.calls = calls or InMemoryCallStore()
        self.principals = principals or PrincipalStore()
        self.calendar = calendar or InMemoryCalendar()
        # One booking policy for now. Per-clinic hours belong on TenantConfig
        # once a clinic asks for different ones; inventing that setting before
        # anyone needs it would be guessing at their diary.
        self.booking_hours = booking_hours or BookingHours()
        self.handoffs = handoffs or InMemoryHandoffQueue()
        self.intake = intake or InMemoryIntakeStore()
        # Not read by any route today — outbound consent (C-R9) is checked
        # before a call is placed, not over HTTP. It is held here so there is
        # one place a deployment's storage is assembled rather than two.
        self.consent = consent or InMemoryConsentLedger()

    @classmethod
    def from_database(
        cls,
        database: Database,
        *,
        principals: PrincipalStore | None = None,
        booking_hours: BookingHours | None = None,
    ) -> "Services":
        """The real wiring: every store backed by Postgres.

        `principals` stays in memory deliberately. It holds API tokens rather
        than clinic data, it is seeded from the environment at startup, and it
        has no Postgres implementation to be inconsistent with — inventing a
        table for it here would be scope this change has no reason to take.
        """
        return cls(
            tenants=PostgresTenantStore(database),
            calls=PostgresCallStore(database),
            calendar=PostgresCalendar(database),
            handoffs=PostgresHandoffQueue(database),
            intake=PostgresIntakeStore(database),
            consent=PostgresConsentLedger(database),
            principals=principals,
            booking_hours=booking_hours,
        )


def create_app(
    services: Services | None = None,
    *,
    cors_origins: list[str] | None = None,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
) -> FastAPI:
    services = services or Services()
    seed_from_environment(services.principals)

    app = FastAPI(
        title="AI Thinkers Voice — operator API",
        version="0.1.0",
        # No interactive docs by default: the schema describes PHI-bearing
        # endpoints, and an unauthenticated schema endpoint is free
        # reconnaissance. Enable deliberately in a development environment.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # A Postgres-backed deployment passes one to open and close the pool;
        # the in-memory app has nothing to open. See `ait_voice.api.main`.
        lifespan=lifespan,
    )
    app.state.services = services

    if cors_origins:
        # Never "*": credentials are sent on every request, and a wildcard
        # origin with credentials is how a third-party page reads a clinic's
        # calls. The dev origin is passed explicitly.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    def current_principal(
        authorization: Annotated[str | None, Header()] = None,
    ) -> Principal:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        try:
            return services.principals.authenticate(token)
        except AuthError as exc:
            # 401 with no detail about which part failed.
            raise HTTPException(status_code=401, detail="unauthenticated") from exc

    async def scope(
        principal: Annotated[Principal, Depends(current_principal)],
        tenant: Annotated[str | None, Query()] = None,
    ) -> TenantContext:
        try:
            return await resolve_scope(principal, tenant, services.tenants)
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    def operator_only(
        principal: Annotated[Principal, Depends(current_principal)],
    ) -> Principal:
        if not principal.is_operator:
            raise HTTPException(status_code=403, detail="operator role required")
        return principal

    Scope = Annotated[TenantContext, Depends(scope)]
    Me = Annotated[Principal, Depends(current_principal)]
    Operator = Annotated[Principal, Depends(operator_only)]

    # -- identity --------------------------------------------------------

    @app.get("/api/me")
    def me(principal: Me) -> dict[str, Any]:
        """What the client needs to decide which surface to render."""
        return {
            "principal_id": principal.principal_id,
            "role": str(principal.role),
            "tenant_id": principal.tenant_id,
            "display_name": principal.display_name,
        }

    # -- clinics ---------------------------------------------------------

    @app.get("/api/clinics")
    async def list_clinics(principal: Operator) -> list[dict[str, Any]]:
        """Operator console, clinics list. Operator-only by definition."""
        return [_clinic_json(c) for c in await services.tenants.all()]

    @app.get("/api/clinic")
    async def get_clinic(tenant: Scope) -> dict[str, Any]:
        return _clinic_json(await services.tenants.get(tenant.tenant_id))

    @app.post("/api/clinic")
    async def update_clinic(
        tenant: Scope, principal: Operator, changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Clinic configuration. Operator-only: the clinic surface is read-only.

        Only known fields are applied. An unrecognised key is rejected rather
        than ignored, so a client typo fails loudly instead of silently not
        taking effect.
        """
        allowed = {"clinic_name", "greeting", "escalation_number", "out_of_hours"}
        unknown = set(changes) - allowed
        if unknown:
            raise HTTPException(status_code=400, detail=f"unknown field(s): {sorted(unknown)}")
        updated = await services.tenants.update(tenant.tenant_id, **changes)
        return _clinic_json(updated)

    # -- calls -----------------------------------------------------------

    @app.get("/api/calls")
    async def list_calls(
        tenant: Scope, limit: Annotated[int, Query(ge=1, le=200)] = 50
    ) -> list[dict[str, Any]]:
        """Recent calls. Numbers are masked in `summary()`, not by the client."""
        return [r.summary() for r in await services.calls.recent(tenant, limit=limit)]

    @app.get("/api/calls/{call_id}")
    async def get_call(tenant: Scope, call_id: str) -> dict[str, Any]:
        record = await services.calls.get(tenant, call_id)
        if record is None:
            # 404 rather than 403 for another tenant's call id: distinguishing
            # them would confirm the id exists somewhere.
            raise HTTPException(status_code=404, detail="no such call")
        transcript = await services.calls.transcript(tenant, call_id)
        return {
            **record.summary(),
            "caller_masked": record.caller_masked,
            "transcript": transcript.rendered() if transcript else None,
        }

    @app.get("/api/summary")
    async def activity(
        tenant: Scope, days: Annotated[int, Query(ge=1, le=90)] = 7
    ) -> dict[str, Any]:
        summary = await services.calls.summarize(tenant, window_days=days)
        return {
            "window_days": summary.window_days,
            "calls_answered": summary.calls_answered,
            "appointments_booked": summary.appointments_booked,
            "appointments_changed": summary.appointments_changed,
            "escalated": summary.escalated,
            "escalation_rate": summary.escalation_rate,
            "messages_open": summary.messages_open,
            "average_duration_seconds": round(summary.average_duration_seconds, 1),
        }

    # -- messages --------------------------------------------------------

    @app.get("/api/messages")
    async def list_messages(tenant: Scope, open_only: bool = False) -> list[dict[str, Any]]:
        """The callback queue. Notes are revealed here — this is the detail view."""
        return [
            m.summary(reveal_note=True)
            for m in await services.calls.messages(tenant, open_only=open_only)
        ]

    @app.post("/api/messages/{message_id}/resolve")
    async def resolve_message(tenant: Scope, message_id: str) -> dict[str, Any]:
        """Mark a callback as made.

        Writable by a clinic user, which is the one exception to the read-only
        clinic surface: the obligation is theirs, so discharging it must be too.
        """
        resolved = await services.calls.resolve_message(tenant, message_id, at=datetime.now(UTC))
        if resolved is None:
            raise HTTPException(status_code=404, detail="no such message")
        return resolved.summary(reveal_note=True)

    # -- appointments ----------------------------------------------------

    @app.get("/api/appointments")
    async def list_appointments(
        tenant: Scope, limit: Annotated[int, Query(ge=1, le=200)] = 50
    ) -> list[dict[str, Any]]:
        """Upcoming appointments — FR6.4.

        Read-only: the clinic surface is read-only per the scope document, and
        the agent is what books. Summaries carry no patient name; a diary needs
        times, not identities.
        """
        config = await services.tenants.get(tenant.tenant_id)
        return [
            {
                **appointment.summary(),
                "local_start": appointment.local_start(config).isoformat(),
                "spoken": appointment.spoken(config),
            }
            for appointment in await services.calendar.upcoming(tenant, limit=limit)
        ]

    @app.get("/api/availability")
    async def availability(
        tenant: Scope, limit: Annotated[int, Query(ge=1, le=50)] = 10
    ) -> list[dict[str, str]]:
        """Free slots, so an operator can see what the agent would offer."""
        config = await services.tenants.get(tenant.tenant_id)
        return [
            {
                "starts_at": slot.isoformat(),
                "local_start": slot.astimezone(config.tz).isoformat(),
            }
            for slot in await services.calendar.availability(
                tenant, config, services.booking_hours, limit=limit
            )
        ]

    @app.post("/api/appointments/{appointment_id}/cancel")
    async def cancel_appointment(
        tenant: Scope, principal: Operator, appointment_id: str
    ) -> dict[str, Any]:
        """Cancel on the clinic's behalf. Operator-only — see above.

        Exists because a clinic that has to phone AI Thinkers to cancel one
        appointment is worse off than before the agent existed.
        """
        try:
            cancelled = await services.calendar.cancel(tenant, appointment_id)
        except AppointmentNotFound as exc:
            raise HTTPException(status_code=404, detail="no such appointment") from exc
        return cancelled.summary()

    # -- handoffs --------------------------------------------------------

    @app.get("/api/handoffs")
    async def list_handoffs(tenant: Scope, open_only: bool = True) -> list[dict[str, Any]]:
        """The queue of calls waiting for a person.

        Summaries only — no PHI. The briefing is fetched per record, so a list
        left open on a screen does not display what every caller said.
        """
        records = (
            await services.handoffs.pending(tenant)
            if open_only
            else await services.handoffs.all(tenant)
        )
        return [record.summary() for record in records]

    @app.get("/api/handoffs/{handoff_id}")
    async def get_handoff(tenant: Scope, handoff_id: str) -> dict[str, Any]:
        """The briefing a person reads before picking the call up — C-T6.

        This is the one endpoint that deliberately returns what the caller
        said. Withholding it is the failure the whole feature exists to
        prevent, and it is reachable only by a principal scoped to this tenant.
        """
        record = await services.handoffs.get(tenant, handoff_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such handoff")
        return {**record.summary(), "briefing": record.context.for_human()}

    @app.post("/api/handoffs/{handoff_id}/acknowledge")
    async def acknowledge_handoff(tenant: Scope, principal: Me, handoff_id: str) -> dict[str, Any]:
        """Mark that a person has picked this up.

        Writable by a clinic user: the obligation is theirs, so recording that
        they met it must be theirs too — the same exception the callback queue
        already makes.
        """
        record = await services.handoffs.acknowledge(tenant, handoff_id, by=principal.principal_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such handoff")
        return record.summary()

    # -- intake ----------------------------------------------------------

    @app.get("/api/intake")
    async def list_intake(
        tenant: Scope, limit: Annotated[int, Query(ge=1, le=200)] = 50
    ) -> list[dict[str, Any]]:
        """Which intakes exist and what they hold — not what they say.

        Every intake value is PHI, so a list shows field names only. Enough for
        a clinic to see the work was done without a date of birth on a screen
        at a front desk.
        """
        return [record.summary() for record in await services.intake.recent(tenant, limit=limit)]

    @app.get("/api/intake/{intake_id}")
    async def get_intake(tenant: Scope, intake_id: str) -> dict[str, Any]:
        """The captured details, for a person who needs to act on them.

        Every value here was read back to the caller and confirmed aloud
        (FR3.2), which is what makes it safe to act on.
        """
        record = await services.intake.get(tenant, intake_id)
        if record is None:
            raise HTTPException(status_code=404, detail="no such intake")
        return {**record.summary(), "details": record.for_clinician()}

    @app.post("/api/intake/{intake_id}/erase")
    async def erase_intake(tenant: Scope, principal: Operator, intake_id: str) -> dict[str, Any]:
        """Erase captured details on request — DPDP, and good practice anyway.

        Operator-only, and irreversible. The call record and the audit entry
        survive: the clinic still knows the call happened and the security log
        still holds the fact, because those carry no personal data.
        """
        erased = await services.intake.erase(tenant, intake_id)
        if not erased:
            raise HTTPException(status_code=404, detail="no such intake")
        return {"intake_id": intake_id, "erased": True}

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(SlotUnavailable)
    def slot_taken(_request: Request, exc: SlotUnavailable) -> JSONResponse:
        """409 with the alternatives attached, never a bare refusal.

        FR2.5 requires alternatives to be offered, and a caller told only "no"
        is the outcome the acceptance criteria forbid.
        """
        return JSONResponse(
            status_code=409,
            content={
                "detail": str(exc),
                "alternatives": [slot.isoformat() for slot in exc.alternatives],
            },
        )

    return app


def _clinic_json(config: TenantConfig) -> dict[str, Any]:
    return {
        "tenant_id": config.tenant_id,
        "clinic_name": config.clinic_name,
        "region": str(config.region),
        "greeting": config.greeting,
        "escalation_number": config.escalation_number,
        "out_of_hours": str(config.out_of_hours),
        "languages": list(config.languages),
        "outbound_registered": config.outbound_registered,
        "active": config.active,
        "is_staffed_now": config.is_staffed(),
    }
