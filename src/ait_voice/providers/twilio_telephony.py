"""Twilio Media Streams telephony provider.

This is the leg constraint C-T2 is about: bidirectional media streaming over a
WebSocket. A provider that only does classic IVR or TwiML cannot host a live
agent — the audio has to flow both ways while the call is open. `docs/vendors.md`
records that this requirement alone rules out several established Indian CPaaS
vendors.

**How it fits together.** Twilio does not connect to us; we accept a connection
from Twilio. A call arrives, Twilio fetches TwiML telling it to open a WebSocket
to our server, and audio flows over that socket for the life of the call. So the
provider here is a *server*, and each connection is one call.

Audio is μ-law 8kHz base64-encoded in JSON frames, which is why this module does
format translation — keeping vendor wire formats out of the domain is what the
provider boundary is for.

**Verified for US only.** `docs/vendors.md` records Twilio Media Streams and
ConversationRelay as explicitly HIPAA-eligible, needing Security or Enterprise
Edition, with no India edge — nearest PoP Singapore or Tokyo. The India leg
needs Exotel or Plivo, which is a separate provider behind this same protocol.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import AsyncIterator

from ait_voice.core.logging import CallLogger
from ait_voice.core.types import TenantContext
from ait_voice.providers.base import BAANotConfirmedError


class TwilioAudioSink:
    """Writes agent audio back onto the open call.

    Twilio expects μ-law 8kHz, base64-encoded, in a JSON media frame carrying
    the stream SID it gave us at connect time.
    """

    def __init__(self, websocket, stream_sid: str) -> None:  # noqa: ANN001
        self._ws = websocket
        self._stream_sid = stream_sid
        self._closed = False

    async def write(self, chunk: bytes) -> None:
        if self._closed or not chunk:
            return
        await self._ws.send(
            json.dumps(
                {
                    "event": "media",
                    "streamSid": self._stream_sid,
                    "media": {"payload": base64.b64encode(chunk).decode("ascii")},
                }
            )
        )

    async def clear(self) -> None:
        """Drop audio Twilio has buffered but not yet played.

        This is what makes barge-in possible: when the caller starts speaking
        over the agent, whatever is queued must stop immediately rather than
        finishing the sentence.
        """
        if self._closed:
            return
        await self._ws.send(
            json.dumps({"event": "clear", "streamSid": self._stream_sid})
        )

    async def close(self) -> None:
        self._closed = True


class TwilioTelephony:
    """Accepts Twilio Media Stream connections.

    One instance serves many calls; :meth:`stream` is called once per connected
    call with the WebSocket for that call.
    """

    name = "twilio"

    def __init__(
        self,
        *,
        account_sid: str | None = None,
        auth_token: str | None = None,
        baa_confirmed: bool = False,
    ) -> None:
        self._account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self._auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN")
        self._baa_confirmed = baa_confirmed
        #: Populated by the server as calls connect, keyed by call id.
        self._connections: dict[str, tuple[object, str]] = {}

    def attach(self, call_id: str, websocket, stream_sid: str) -> None:  # noqa: ANN001
        """Register a connected call so :meth:`stream` can find it."""
        self._connections[call_id] = (websocket, stream_sid)

    async def stream(
        self,
        tenant: TenantContext,
        call_id: str,
    ) -> tuple[AsyncIterator[bytes], TwilioAudioSink]:

        if tenant.is_phi_jurisdiction and not self._baa_confirmed:
            raise BAANotConfirmedError(
                f"tenant {tenant.tenant_id!r} is in a PHI jurisdiction and no BAA "
                f"is confirmed for provider {self.name!r}; refusing to carry audio"
            )

        try:
            websocket, stream_sid = self._connections[call_id]
        except KeyError:
            raise RuntimeError(
                f"no connected Twilio stream for call {call_id!r}; "
                "attach() must be called when the WebSocket connects"
            ) from None

        log = CallLogger.for_call(__name__, tenant, call_id)
        sink = TwilioAudioSink(websocket, stream_sid)

        async def inbound() -> AsyncIterator[bytes]:
            async for raw in websocket:
                frame = json.loads(raw)
                event = frame.get("event")

                if event == "media":
                    yield base64.b64decode(frame["media"]["payload"])
                elif event == "stop":
                    log.info("caller hung up")
                    break
                elif event == "mark":
                    log.debug("mark received", mark=frame.get("mark", {}).get("name"))

        return inbound(), sink


def inbound_twiml(websocket_url: str) -> str:
    """TwiML that tells Twilio to open a media stream to us.

    Served in response to Twilio's webhook when a call arrives. The
    ``<Connect><Stream>`` verb is what makes the audio bidirectional; a
    ``<Start><Stream>`` would only give us inbound audio, which is enough to
    transcribe a call and not enough to hold a conversation.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f'<Connect><Stream url="{websocket_url}" /></Connect>'
        "</Response>"
    )


async def serve(  # pragma: no cover - socket binding, see note below
    handler,  # noqa: ANN001 - async callable(call_id, websocket, stream_sid)
    *,
    host: str = "0.0.0.0",  # noqa: S104 - a media server binds publicly by design
    port: int = 8080,
) -> None:
    """Run the WebSocket server Twilio connects to.

    Excluded from the branch-coverage floor because it is socket binding rather
    than translation: it opens a port and hands each connection to the handler.
    The affirmed practice permits excluding transport on condition it carries
    contract tests instead, and the handshake contract this depends on is
    covered in ``tests/test_provider_contracts.py``. What remains unproven here
    is that Twilio connects and streams as documented, which no unit test can
    establish — that is the live spike, D-03.

    Each connection is one call. The ``start`` frame carries the identifiers we
    need before any audio arrives, so the handler is invoked once that lands
    rather than on connect.
    """
    import websockets

    async def on_connection(websocket) -> None:  # noqa: ANN001
        stream_sid: str | None = None
        call_sid: str | None = None

        async for raw in websocket:
            frame = json.loads(raw)
            if frame.get("event") == "start":
                start = frame["start"]
                stream_sid = start["streamSid"]
                call_sid = start["callSid"]
                break

        if not stream_sid or not call_sid:
            await websocket.close()
            return

        await handler(call_sid, websocket, stream_sid)

    async with websockets.serve(on_connection, host, port):
        await asyncio.Future()  # run until cancelled
