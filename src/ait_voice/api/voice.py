"""The endpoint Twilio actually dials.

Everything else was built and could not take a call, because there was nothing
for a carrier to reach: `providers/twilio_telephony.py` exposes a WebSocket
server and `providers/conversation_relay.py` renders TwiML, and no HTTP service
served either. This is that service.

Two routes, and the split is Twilio's, not ours.

``POST /voice/incoming`` — a call arrives. Twilio asks what to do; we answer
with TwiML naming a WebSocket URL. This request is signed, so we check it.

``WS /voice/relay`` — Twilio opens the socket the TwiML named and streams the
conversation over it. **This connection carries no credential**, so the URL in
the TwiML carries a short-lived signed token instead; see
:mod:`ait_voice.api.voice_auth`.

Kept as its own ASGI app rather than routes on the operator API. They have
different exposure — one is a public carrier webhook, the other is behind
authenticated operator sessions — and different scaling shapes, since a call
holds its socket open for minutes while an API request does not. Same image,
different command.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import FastAPI, Form, Header, HTTPException, Request, WebSocket
from fastapi.responses import Response

from ait_voice.api.voice_auth import (
    RelayTokenInvalid,
    mint_relay_token,
    validate_twilio_signature,
    verify_relay_token,
)
from ait_voice.core.audit import AuditEvent
from ait_voice.core.pipeline import VoicePipeline
from ait_voice.core.recording import record_call
from ait_voice.core.tenancy import TenantNotFoundError
from ait_voice.core.types import PHI
from ait_voice.db.base import AuditSink, CallRepository, TenantRepository
from ait_voice.providers.conversation_relay import (
    ConversationRelayTransport,
    RelayConfig,
    inbound_twiml,
)

log = logging.getLogger(__name__)


class VoiceServices:
    """What the voice service needs, which is much less than the operator API."""

    def __init__(
        self,
        *,
        tenants: TenantRepository,
        calls: CallRepository,
        audit: AuditSink,
        pipeline: VoicePipeline,
        relay: ConversationRelayTransport,
        websocket_base: str,
        auth_token: str = "",
    ) -> None:
        self.tenants = tenants
        self.calls = calls
        self.audit = audit
        self.pipeline = pipeline
        self.relay = relay
        #: wss://host — the TwiML tells Twilio where to connect.
        self.websocket_base = websocket_base.rstrip("/")
        #: Twilio account auth token, for signature validation.
        self.auth_token = auth_token


def create_voice_app(services: VoiceServices) -> FastAPI:
    app = FastAPI(
        title="AI Thinkers Voice — carrier webhook",
        version="0.1.0",
        # A public endpoint. Its schema describes how to start a call, which is
        # free reconnaissance for anyone who finds it.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.services = services

    @app.post("/voice/incoming")
    async def incoming(  # noqa: PLR0913 - Twilio's form fields, one per parameter
        request: Request,
        To: Annotated[str, Form()],
        From: Annotated[str, Form()] = "",
        CallSid: Annotated[str, Form()] = "",
        x_twilio_signature: Annotated[str | None, Header()] = None,
    ) -> Response:
        """A call has arrived. Answer with where to stream it.

        `To` is the clinic's number and the only thing that says which tenant
        this call belongs to. `From` is the caller's number, which C-R2 makes
        PHI — it is wrapped immediately and never logged.
        """
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
        if not validate_twilio_signature(
            url=str(request.url),
            params=params,
            signature=x_twilio_signature,
            auth_token=services.auth_token,
        ):
            # 403 with no detail. Saying which part failed helps somebody
            # iterate towards a valid forgery.
            log.warning("rejected an unsigned or missigned voice webhook")
            raise HTTPException(status_code=403, detail="forbidden")

        caller = PHI(From) if From else None
        try:
            tenant = await services.tenants.resolve_number(To)
        except (TenantNotFoundError, ValueError):
            # Deliberately not a 500 and deliberately not a default clinic:
            # answering as the wrong clinic is worse than not answering. Twilio
            # plays its own failure treatment on a 4xx.
            log.warning("no clinic answers the dialled number")
            raise HTTPException(status_code=404, detail="no clinic answers this number") from None

        config = await services.tenants.get(tenant.tenant_id)
        call_sid = CallSid or f"local-{uuid.uuid4().hex[:12]}"
        token = mint_relay_token(tenant.tenant_id, call_sid)

        await services.audit.record(
            tenant,
            AuditEvent.CALL_STARTED,
            call_id=call_sid,
            # Counts and codes only — the caller's number goes nowhere near this.
            inbound=True,
        )
        del caller  # Carried into the session by Twilio, not by us.

        relay_config = RelayConfig(
            websocket_url=f"{services.websocket_base}/voice/relay?token={token}",
            language=config.languages[0] if config.languages else "en-US",
            welcome_greeting=None,  # The pipeline speaks the disclosure first.
        )
        return Response(content=inbound_twiml(relay_config), media_type="application/xml")

    @app.websocket("/voice/relay")
    async def relay(websocket: WebSocket, token: str = "") -> None:
        """The conversation itself.

        The token is the only thing authorising this connection — Twilio sends
        no credential — so it is checked before the socket is accepted.
        """
        try:
            tenant_id, call_sid = verify_relay_token(token)
        except RelayTokenInvalid:
            # Closed without accepting. An unauthorised connection never
            # reaches a tenant context.
            await websocket.close(code=1008, reason="unauthorised")
            log.warning("rejected a relay socket with an invalid token")
            return

        try:
            tenant = await services.tenants.resolve(tenant_id)
        except TenantNotFoundError:
            await websocket.close(code=1008, reason="unauthorised")
            return

        await websocket.accept()
        try:
            session = services.relay.session_for(_Socket(websocket), tenant)
            result = await services.pipeline.handle_call(tenant, call_id=call_sid, session=session)
            await record_call(tenant, result, services.calls, audit=services.audit)
        except Exception:
            # Logged without detail: an exception message on this path can
            # carry what the caller said.
            log.exception("relay session failed", extra={"call_id": call_sid})
            raise
        finally:
            await _close_quietly(websocket)

    @app.get("/voice/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


class _Socket:
    """Adapts a FastAPI WebSocket to the `WebSocketLike` the providers expect.

    The quarantine works in both directions: the provider boundary keeps vendor
    SDKs out of the domain, and this keeps a web framework's socket type out of
    the providers.
    """

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def send(self, message: str) -> None:
        await self._websocket.send_text(message)

    async def recv(self) -> str:
        return await self._websocket.receive_text()

    async def close(self) -> None:
        await _close_quietly(self._websocket)

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> str:
        try:
            return await self._websocket.receive_text()
        except Exception as exc:  # noqa: BLE001 - any disconnect ends the stream
            raise StopAsyncIteration from exc


async def _close_quietly(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception:  # noqa: BLE001, S110 - already closed is the common case
        pass
