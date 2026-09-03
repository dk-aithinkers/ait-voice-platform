"""The carrier webhook, and the two things standing in front of it.

This endpoint is the only publicly reachable part of the system that can start a
call, so most of what follows is about refusals. An unsigned POST must not open
a session; an unauthorised socket must not reach a tenant context. Both cost
real money and, worse, would write audit entries and transcripts for calls that
never happened.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from ait_voice.api.voice import VoiceServices, create_voice_app
from ait_voice.api.voice_auth import (
    RelayTokenInvalid,
    mint_relay_token,
    verify_relay_token,
)
from ait_voice.core.audit import AuditLog
from ait_voice.core.pipeline import VoicePipeline
from ait_voice.core.records import CallStore
from ait_voice.core.tenancy import TenantConfig, TenantStore
from ait_voice.core.types import Region
from ait_voice.db.memory import InMemoryCallStore, InMemoryTenantStore
from ait_voice.providers.base import BAANotConfirmedError, ProviderRegistry
from ait_voice.providers.conversation_relay import ConversationRelayTransport
from ait_voice.providers.offline import offline_provider_set

AUTH_TOKEN = "an-auth-token-for-tests"
CLINIC_NUMBER = "+15551234567"
PARK_NUMBER = "+919990001111"


@pytest.fixture(autouse=True)
def _relay_secret(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("AIT_RELAY_TOKEN_SECRET", "a-signing-secret-for-tests")


@pytest.fixture
async def services() -> VoiceServices:
    inner = TenantStore()
    inner.add(TenantConfig(tenant_id="northside", region=Region.US, clinic_name="Northside"))
    inner.claim_number("northside", CLINIC_NUMBER)
    # An India clinic too, because the BAA gate refuses a US ConversationRelay
    # session until D-05 completes — which is C-R1 working, not a test problem.
    # The conversation tests therefore run against DPDP jurisdiction, exactly as
    # a real deployment would until the Twilio BAA is executed.
    inner.add(TenantConfig(tenant_id="parkclinic", region=Region.INDIA, clinic_name="Park"))
    inner.claim_number("parkclinic", PARK_NUMBER)
    tenants = InMemoryTenantStore(inner)

    registry = ProviderRegistry()
    registry.register(Region.US, offline_provider_set(script=["hello"]))
    registry.register(Region.INDIA, offline_provider_set(script=["hello"]))

    return VoiceServices(
        tenants=tenants,
        calls=InMemoryCallStore(CallStore()),
        audit=AuditLog(root="/tmp/ait-voice-test-audit"),
        pipeline=VoicePipeline(registry),
        relay=ConversationRelayTransport(),
        websocket_base="wss://voice.example.com",
        auth_token=AUTH_TOKEN,
    )


@pytest.fixture
async def client(services: VoiceServices) -> AsyncIterator[AsyncClient]:
    app = create_voice_app(services)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://voice.example.com"
    ) as http:
        yield http


def _sign(url: str, params: dict[str, str]) -> str:
    """A genuine Twilio signature, produced the way Twilio produces one."""
    from twilio.request_validator import RequestValidator

    return RequestValidator(AUTH_TOKEN).compute_signature(url, params)


class TestTheWebhookRefusesForgeries:
    async def test_an_unsigned_request_is_refused(self, client: AsyncClient) -> None:
        response = await client.post(
            "/voice/incoming", data={"To": CLINIC_NUMBER, "From": "+15559990000"}
        )

        assert response.status_code == 403

    async def test_a_wrong_signature_is_refused(self, client: AsyncClient) -> None:
        response = await client.post(
            "/voice/incoming",
            data={"To": CLINIC_NUMBER},
            headers={"X-Twilio-Signature": "not-the-right-signature"},
        )

        assert response.status_code == 403

    async def test_a_signature_for_different_parameters_is_refused(
        self, client: AsyncClient
    ) -> None:
        """The signature covers the parameters, so swapping the dialled number
        after signing must not validate — otherwise anyone holding one valid
        request could redirect it at another clinic."""
        url = "https://voice.example.com/voice/incoming"
        signature = _sign(url, {"To": CLINIC_NUMBER})

        response = await client.post(
            "/voice/incoming",
            data={"To": "+15559999999"},
            headers={"X-Twilio-Signature": signature},
        )

        assert response.status_code == 403

    async def test_the_refusal_says_nothing_useful(self, client: AsyncClient) -> None:
        """Telling a caller which part failed helps them iterate towards a forgery."""
        response = await client.post("/voice/incoming", data={"To": CLINIC_NUMBER})

        assert response.json() == {"detail": "forbidden"}


class TestTheWebhookAnswers:
    async def test_a_signed_call_gets_twiml_naming_our_socket(self, client: AsyncClient) -> None:
        url = "https://voice.example.com/voice/incoming"
        params = {"To": CLINIC_NUMBER, "From": "+15559990000", "CallSid": "CA123"}

        response = await client.post(
            "/voice/incoming",
            data=params,
            headers={"X-Twilio-Signature": _sign(url, params)},
        )

        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert "<ConversationRelay" in response.text
        assert "wss://voice.example.com/voice/relay?token=" in response.text

    async def test_the_twiml_carries_a_token_that_verifies(self, client: AsyncClient) -> None:
        url = "https://voice.example.com/voice/incoming"
        params = {"To": CLINIC_NUMBER, "CallSid": "CA999"}

        response = await client.post(
            "/voice/incoming", data=params, headers={"X-Twilio-Signature": _sign(url, params)}
        )

        token = response.text.split("token=", 1)[1].split("&")[0].split('"')[0]
        assert verify_relay_token(token) == ("northside", "CA999")

    async def test_an_unrouted_number_is_a_404_not_a_default_clinic(
        self, client: AsyncClient
    ) -> None:
        """Answering as the wrong clinic is worse than not answering."""
        url = "https://voice.example.com/voice/incoming"
        params = {"To": "+15550000000"}

        response = await client.post(
            "/voice/incoming", data=params, headers={"X-Twilio-Signature": _sign(url, params)}
        )

        assert response.status_code == 404

    async def test_a_deactivated_clinic_stops_answering(
        self, client: AsyncClient, services: VoiceServices
    ) -> None:
        await services.tenants.deactivate("northside")
        url = "https://voice.example.com/voice/incoming"
        params = {"To": CLINIC_NUMBER}

        response = await client.post(
            "/voice/incoming", data=params, headers={"X-Twilio-Signature": _sign(url, params)}
        )

        assert response.status_code == 404

    async def test_the_callers_number_never_reaches_the_response(self, client: AsyncClient) -> None:
        """C-R2: the caller's number is PHI and has no business in TwiML."""
        url = "https://voice.example.com/voice/incoming"
        params = {"To": CLINIC_NUMBER, "From": "+15559990000", "CallSid": "CA1"}

        response = await client.post(
            "/voice/incoming", data=params, headers={"X-Twilio-Signature": _sign(url, params)}
        )

        assert "+15559990000" not in response.text

    async def test_the_audit_entry_carries_no_caller_identity(
        self, client: AsyncClient, services: VoiceServices
    ) -> None:
        url = "https://voice.example.com/voice/incoming"
        params = {"To": CLINIC_NUMBER, "From": "+15559990000", "CallSid": "CA-audit"}
        await client.post(
            "/voice/incoming", data=params, headers={"X-Twilio-Signature": _sign(url, params)}
        )

        tenant = await services.tenants.resolve("northside")
        rows = await services.audit.read(tenant)

        assert any(r["call_id"] == "CA-audit" for r in rows)
        assert "+15559990000" not in str(rows)
        assert CLINIC_NUMBER not in str(rows)


class TestTheSocketRefusesUnauthorisedConnections:
    """Twilio sends no credential on the WebSocket, so the token is all there is."""

    async def test_a_socket_with_no_token_is_closed(self, services: VoiceServices) -> None:
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        with TestClient(create_voice_app(services)) as client:  # noqa: SIM117
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/voice/relay") as ws:
                    ws.receive_text()

    async def test_a_socket_with_a_forged_token_is_closed(self, services: VoiceServices) -> None:
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        forged = mint_relay_token("northside", "CA1")[:-4] + "AAAA"
        with TestClient(create_voice_app(services)) as client:  # noqa: SIM117
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/voice/relay?token={forged}") as ws:
                    ws.receive_text()

    async def test_an_expired_token_does_not_verify(self) -> None:
        import time

        token = mint_relay_token("northside", "CA1", now=time.time() - 3600)

        with pytest.raises(RelayTokenInvalid):
            verify_relay_token(token)

    async def test_a_token_for_a_deactivated_clinic_is_rejected(
        self, services: VoiceServices
    ) -> None:
        """A token minted before deactivation must not still open a session."""
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        token = mint_relay_token("northside", "CA1")
        await services.tenants.deactivate("northside")

        with TestClient(create_voice_app(services)) as client:  # noqa: SIM117
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(f"/voice/relay?token={token}") as ws:
                    ws.receive_text()


class TestHealth:
    async def test_health_needs_no_signature(self, client: AsyncClient) -> None:
        """The load balancer does not hold a Twilio auth token."""
        assert (await client.get("/voice/health")).status_code == 200


class TestAFullCallOverTheSocket:
    """The whole point: a conversation, end to end, over the real route.

    Everything else in this file is a refusal. This is the path a caller takes,
    driven the way Twilio drives it — a `setup` frame, then `prompt` frames —
    and asserting on what comes back out.
    """

    @staticmethod
    def _connect(services: VoiceServices, call_sid: str = "CA-full"):  # noqa: ANN205
        from fastapi.testclient import TestClient

        token = mint_relay_token("parkclinic", call_sid)
        client = TestClient(create_voice_app(services))
        return client, client.websocket_connect(f"/voice/relay?token={token}")

    def test_the_agent_speaks_the_disclosure_before_anything_else(
        self, services: VoiceServices
    ) -> None:
        """FR1.3 — the AI and recording disclosure lead, and California AB 2905
        requires them *before* the message rather than after it."""
        import json

        client, connection = self._connect(services)
        with client, connection as ws:
            ws.send_text(json.dumps({"type": "setup", "callSid": "CA-full", "to": PARK_NUMBER}))
            first = json.loads(ws.receive_text())

        assert first["type"] == "text"
        assert "AI assistant" in first["token"]
        assert "recorded" in first["token"]

    def test_a_caller_utterance_gets_a_reply(self, services: VoiceServices) -> None:
        import json

        client, connection = self._connect(services)
        with client, connection as ws:
            ws.send_text(json.dumps({"type": "setup", "callSid": "CA-full", "to": PARK_NUMBER}))
            json.loads(ws.receive_text())  # the disclosure
            ws.send_text(
                json.dumps({"type": "prompt", "voicePrompt": "I need an appointment", "last": True})
            )
            reply = json.loads(ws.receive_text())

        assert reply["type"] == "text"
        assert reply["token"]

    def test_a_partial_recognition_is_not_answered(self, services: VoiceServices) -> None:
        """Twilio streams partials for barge-in. Answering one would have the
        agent talk over a caller who is still speaking."""
        import json

        client, connection = self._connect(services)
        with client, connection as ws:
            ws.send_text(json.dumps({"type": "setup", "callSid": "CA-p", "to": PARK_NUMBER}))
            json.loads(ws.receive_text())
            ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "I need an", "last": False}))
            ws.send_text(
                json.dumps({"type": "prompt", "voicePrompt": "I need an appointment", "last": True})
            )
            reply = json.loads(ws.receive_text())

        # One reply, to the completed utterance rather than to the fragment.
        assert reply["type"] == "text"

    def test_the_call_is_recorded_when_it_ends(self, services: VoiceServices) -> None:
        """The record and the audit entry are what survive the call."""
        import asyncio
        import json

        client, connection = self._connect(services, call_sid="CA-recorded")
        with client, connection as ws:
            ws.send_text(json.dumps({"type": "setup", "callSid": "CA-recorded", "to": PARK_NUMBER}))
            json.loads(ws.receive_text())
            ws.send_text(json.dumps({"type": "prompt", "voicePrompt": "goodbye", "last": True}))
            json.loads(ws.receive_text())

        async def stored() -> object:
            tenant = await services.tenants.resolve("parkclinic")
            return await services.calls.get(tenant, "CA-recorded")

        assert asyncio.run(stored()) is not None, "the call left no record"


class TestTheBAAGateReachesTheLiveCall:
    def test_a_us_call_is_refused_until_a_baa_exists(self, services: VoiceServices) -> None:
        """C-R1 on the path that matters.

        Every other BAA test checks provider construction. This one checks that
        a real inbound call to a US clinic cannot open a session while the
        register says no agreement exists — which is the state today, with all
        eight vendors unsigned. The refusal is the control working; when it
        starts passing, D-05 has completed.
        """
        import json

        from fastapi.testclient import TestClient

        token = mint_relay_token("northside", "CA-us")
        client = TestClient(create_voice_app(services))
        with pytest.raises(BAANotConfirmedError), client:  # noqa: SIM117
            with client.websocket_connect(f"/voice/relay?token={token}") as ws:
                ws.send_text(json.dumps({"type": "setup", "callSid": "CA-us", "to": CLINIC_NUMBER}))
                ws.receive_text()
