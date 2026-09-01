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
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ait_voice.api.auth import (
    AuthError,
    ForbiddenError,
    Principal,
    PrincipalStore,
    resolve_scope,
    seed_from_environment,
)
from ait_voice.core.records import CallStore
from ait_voice.core.tenancy import TenantConfig, TenantStore
from ait_voice.core.types import TenantContext


class Services:
    """Everything the API reads and writes.

    Held on the app rather than in module globals so tests build their own and
    two instances never share a store.
    """

    def __init__(
        self,
        *,
        tenants: TenantStore | None = None,
        calls: CallStore | None = None,
        principals: PrincipalStore | None = None,
    ) -> None:
        self.tenants = tenants or TenantStore()
        self.calls = calls or CallStore()
        self.principals = principals or PrincipalStore()


def create_app(
    services: Services | None = None, *, cors_origins: list[str] | None = None
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

    def scope(
        principal: Annotated[Principal, Depends(current_principal)],
        tenant: Annotated[str | None, Query()] = None,
    ) -> TenantContext:
        try:
            return resolve_scope(principal, tenant, services.tenants)
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
    def list_clinics(principal: Operator) -> list[dict[str, Any]]:
        """Operator console, clinics list. Operator-only by definition."""
        return [_clinic_json(c) for c in services.tenants]

    @app.get("/api/clinic")
    def get_clinic(tenant: Scope) -> dict[str, Any]:
        return _clinic_json(services.tenants.get(tenant.tenant_id))

    @app.post("/api/clinic")
    def update_clinic(
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
            raise HTTPException(
                status_code=400, detail=f"unknown field(s): {sorted(unknown)}"
            )
        updated = services.tenants.update(tenant.tenant_id, **changes)
        return _clinic_json(updated)

    # -- calls -----------------------------------------------------------

    @app.get("/api/calls")
    def list_calls(
        tenant: Scope, limit: Annotated[int, Query(ge=1, le=200)] = 50
    ) -> list[dict[str, Any]]:
        """Recent calls. Numbers are masked in `summary()`, not by the client."""
        return [r.summary() for r in services.calls.recent(tenant, limit=limit)]

    @app.get("/api/calls/{call_id}")
    def get_call(tenant: Scope, call_id: str) -> dict[str, Any]:
        record = services.calls.get(tenant, call_id)
        if record is None:
            # 404 rather than 403 for another tenant's call id: distinguishing
            # them would confirm the id exists somewhere.
            raise HTTPException(status_code=404, detail="no such call")
        transcript = services.calls.transcript(tenant, call_id)
        return {
            **record.summary(),
            "caller_masked": record.caller_masked,
            "transcript": transcript.rendered() if transcript else None,
        }

    @app.get("/api/summary")
    def activity(
        tenant: Scope, days: Annotated[int, Query(ge=1, le=90)] = 7
    ) -> dict[str, Any]:
        summary = services.calls.summarize(tenant, window_days=days)
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
    def list_messages(
        tenant: Scope, open_only: bool = False
    ) -> list[dict[str, Any]]:
        """The callback queue. Notes are revealed here — this is the detail view."""
        return [
            m.summary(reveal_note=True)
            for m in services.calls.messages(tenant, open_only=open_only)
        ]

    @app.post("/api/messages/{message_id}/resolve")
    def resolve_message(tenant: Scope, message_id: str) -> dict[str, Any]:
        """Mark a callback as made.

        Writable by a clinic user, which is the one exception to the read-only
        clinic surface: the obligation is theirs, so discharging it must be too.
        """
        resolved = services.calls.resolve_message(
            tenant, message_id, at=datetime.now(UTC)
        )
        if resolved is None:
            raise HTTPException(status_code=404, detail="no such message")
        return resolved.summary(reveal_note=True)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

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
