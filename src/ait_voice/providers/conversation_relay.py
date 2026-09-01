"""Twilio ConversationRelay: one vendor for recognition, synthesis and carrier.

ConversationRelay inverts the media stream. Instead of receiving mu-law frames
and running the speech legs ourselves, Twilio recognises the caller and sends
**text** over the WebSocket; we reply with text and Twilio speaks it. Barge-in,
endpointing and audio framing move to Twilio's side, which deletes the code most
likely to be subtly wrong.

**What it costs us.** C-T1 requires every speech and telephony component to stay
replaceable per region. A bundle makes Twilio structurally load-bearing for
three legs at once: the providers are selectable from Twilio's menu
(`transcriptionProvider`, `ttsProvider`), but Twilio itself is not. That is a
real reduction in replaceability and it is the reason this lives behind
:class:`~ait_voice.providers.base.DialogTransport` as a per-region choice rather
than becoming the default.

**Where it fits.** ConversationRelay became HIPAA-eligible in March 2025, on
Security or Enterprise Edition with an executed BAA, so C-R1 is satisfiable —
but note the shape of that BAA differs from the cascaded case. There we hold
separate agreements with each speech vendor; here Twilio subcontracts them and
carries that responsibility. Both are defensible; they are not the same
arrangement, and which one this project wants is a question for the compliance
counsel engagement, not for this module.

For the India tenant the calculus is worse: the DLT and 1600-series work (C-R6,
D-04) is unchanged, Twilio's menu excludes the Indic-strong vendors, and Twilio
documents accuracy limitations on multi-language transcripts — which is R-01,
the largest unvalidated risk on the project. The default stays cascaded there.

Protocol reference: https://www.twilio.com/docs/voice/conversationrelay
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any

from ait_voice.core.types import PHI, TenantContext, Utterance
from ait_voice.providers.base import (
    BAANotConfirmedError,
    SpeechTiming,
    WebSocketLike,
)

#: Twilio's defaults. Both are the vendors this project selected independently,
#: which is convergence rather than coincidence.
DEFAULT_TRANSCRIPTION_PROVIDER = "Deepgram"
DEFAULT_TTS_PROVIDER = "ElevenLabs"

#: Messages Twilio sends us.
MSG_SETUP = "setup"
MSG_PROMPT = "prompt"
MSG_INTERRUPT = "interrupt"
MSG_DTMF = "dtmf"
MSG_ERROR = "error"


@dataclass(frozen=True, slots=True)
class RelayConfig:
    """The `<ConversationRelay>` attributes that matter to us.

    Rendered into TwiML by :func:`inbound_twiml`. Kept as a value object so a
    tenant's language and voice settings are data rather than a format string
    someone edits under time pressure.
    """

    websocket_url: str
    language: str = "en-US"
    transcription_provider: str = DEFAULT_TRANSCRIPTION_PROVIDER
    tts_provider: str = DEFAULT_TTS_PROVIDER
    voice: str | None = None
    #: `speech` lets the caller cut the agent off mid-sentence, which is what a
    #: real receptionist allows. `none` makes the agent talk over the caller.
    interruptible: str = "speech"
    dtmf_detection: bool = True
    welcome_greeting: str | None = None

    def attributes(self) -> dict[str, str]:
        attrs: dict[str, str] = {
            "url": self.websocket_url,
            "language": self.language,
            "transcriptionProvider": self.transcription_provider,
            "ttsProvider": self.tts_provider,
            "interruptible": self.interruptible,
            "dtmfDetection": "true" if self.dtmf_detection else "false",
        }
        if self.voice:
            attrs["voice"] = self.voice
        if self.welcome_greeting:
            attrs["welcomeGreeting"] = self.welcome_greeting
        return attrs


def _escape(value: str) -> str:
    """Escape a TwiML attribute value.

    Clinic names carry apostrophes and ampersands routinely, and an unescaped
    one produces malformed TwiML that Twilio rejects mid-call.
    """
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def inbound_twiml(config: RelayConfig) -> str:
    """TwiML that hands an inbound call to ConversationRelay.

    The disclosure is deliberately NOT set as `welcomeGreeting` by default.
    C-R3/C-R4 are Firm and the pipeline owns the disclosure so that no
    per-tenant configuration can drop it; putting it in TwiML would move that
    guarantee into a template.
    """
    rendered = " ".join(f'{key}="{_escape(value)}"' for key, value in config.attributes().items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f"<ConversationRelay {rendered} />"
        "</Connect></Response>"
    )


@dataclass
class RelayCallInfo:
    """What Twilio told us about the call in its `setup` message.

    ``from_number`` and ``to_number`` are caller identity, which C-R2 makes PHI,
    so they are wrapped rather than left as bare strings.
    """

    session_id: str = ""
    call_sid: str = ""
    direction: str = ""
    from_number: PHI[str] | None = None
    to_number: PHI[str] | None = None
    custom: dict[str, Any] = field(default_factory=dict)


class ConversationRelaySession:
    """One ConversationRelay call.

    Text in, text out. There is no audio on this socket in either direction,
    which is the entire point and also the reason
    :attr:`ConversationRelayTransport.observes_audio` is False.
    """

    def __init__(self, socket: WebSocketLike, tenant: TenantContext) -> None:
        self._socket = socket
        self._tenant = tenant
        self.info = RelayCallInfo()
        #: Set when the caller talks over the agent. The pipeline does not use
        #: this yet; recording it keeps the signal rather than discarding it.
        self.interruptions: list[float] = []
        self.digits: list[str] = []
        self._closed = False

    async def listen(self) -> AsyncIterator[Utterance]:
        """Yield the caller's completed utterances.

        Twilio streams partial recognitions with ``last: false``. Those are for
        barge-in, which Twilio is already handling, so only completed prompts
        reach the dialog policy — the same contract the cascaded session offers.
        """
        async for raw in self._socket:
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                # A frame we cannot parse is a vendor problem, not a caller
                # utterance. Dropping it beats crashing a live call.
                continue

            kind = message.get("type")
            if kind == MSG_SETUP:
                self._record_setup(message)
            elif kind == MSG_PROMPT:
                if not message.get("last", False):
                    continue
                text = message.get("voicePrompt", "")
                if text:
                    yield Utterance(text=PHI(text), is_final=True)
            elif kind == MSG_INTERRUPT:
                self.interruptions.append(float(message.get("durationUntilInterruptMs", 0.0)))
            elif kind == MSG_DTMF:
                if digit := message.get("digit"):
                    self.digits.append(digit)
            elif kind == MSG_ERROR:
                raise RelayError(message.get("description", "unspecified"))

    def _record_setup(self, message: dict[str, Any]) -> None:
        self.info = RelayCallInfo(
            session_id=message.get("sessionId", ""),
            call_sid=message.get("callSid", ""),
            direction=message.get("direction", ""),
            from_number=PHI(message["from"]) if message.get("from") else None,
            to_number=PHI(message["to"]) if message.get("to") else None,
            custom=message.get("customParameters", {}) or {},
        )

    async def speak(self, utterance: Utterance) -> SpeechTiming:
        """Send text for Twilio to synthesise.

        The returned timing is the handoff, not time to first audio: Twilio
        synthesises after this returns and never tells us when the caller
        actually heard something. Flagged rather than quietly reported as if it
        were the same measurement.
        """
        started = time.perf_counter()
        await self._socket.send(
            json.dumps(
                {
                    "type": "text",
                    "token": utterance.text.reveal(),
                    "last": True,
                    "interruptible": True,
                }
            )
        )
        return SpeechTiming(
            elapsed_ms=(time.perf_counter() - started) * 1000,
            observed_audio=False,
        )

    async def switch_language(
        self, *, tts: str | None = None, transcription: str | None = None
    ) -> None:
        """Change language mid-call.

        Kept because it is the one capability the cascaded path does not have
        cheaply, and the India tenant's code-switching problem is exactly the
        case it addresses — though see this module's docstring on why that is
        not yet evidence for R-01.
        """
        payload: dict[str, str] = {"type": "language"}
        if tts:
            payload["ttsLanguage"] = tts
        if transcription:
            payload["transcriptionLanguage"] = transcription
        await self._socket.send(json.dumps(payload))

    async def send_digits(self, digits: str) -> None:
        await self._socket.send(json.dumps({"type": "sendDigits", "digits": digits}))

    async def close(self, handoff: dict[str, Any] | None = None) -> None:
        """End the session, optionally handing structured data to the next step.

        ``handoffData`` is C-T6's native mechanism, but it crosses a vendor
        boundary — so what goes here is
        :meth:`~ait_voice.core.handoff.HandoffContext.for_vendor`, which
        carries opaque references and enumerated codes and no PHI. The person
        who picks the call up reads the real briefing from our own
        authenticated, tenant-scoped surface.
        """
        if self._closed:
            return
        self._closed = True
        payload: dict[str, Any] = {"type": "end"}
        if handoff:
            payload["handoffData"] = json.dumps(handoff)
        with _suppress_send_errors():
            await self._socket.send(json.dumps(payload))


class RelayError(RuntimeError):
    """Twilio reported an error on the session."""


class NoInboundCallError(TimeoutError):
    """No carrier connected in time.

    ConversationRelay inverts who dials whom: Twilio connects to us when a call
    arrives, so there is nothing to synthesise locally the way the loopback
    harness fakes a caller for the cascaded path. A relayed run needs a real
    inbound call to a provisioned number.
    """


class _suppress_send_errors:
    """Closing a socket the carrier already dropped must not mask the real error."""

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return exc_type is not None and issubclass(exc_type, (OSError, RuntimeError))


class ConversationRelayTransport:
    """Opens ConversationRelay sessions from accepted WebSocket connections.

    The carrier dials us, not the other way round: Twilio connects to our
    WebSocket endpoint when a call arrives. Sockets are handed to
    :meth:`accept` by whatever HTTP server terminates them, so this class stays
    free of a web framework.
    """

    name = "twilio-conversationrelay"
    #: Twilio synthesises downstream; we never see the audio. See SpeechTiming.
    observes_audio = False

    def __init__(self, *, baa_confirmed: bool = False, connect_timeout: float = 30.0) -> None:
        self._baa_confirmed = baa_confirmed
        self._connect_timeout = connect_timeout
        self._pending: asyncio.Queue[WebSocketLike] = asyncio.Queue()

    def _check_baa(self, tenant: TenantContext) -> None:
        # Same gate as every other leg. A bundle touches audio, transcripts and
        # caller identity at once, so if anything needs C-R1 enforcement it is
        # this.
        if tenant.is_phi_jurisdiction and not self._baa_confirmed:
            raise BAANotConfirmedError(
                f"tenant {tenant.tenant_id!r} is in a PHI jurisdiction and no BAA "
                f"is confirmed for provider 'twilio'; refusing to open a "
                f"ConversationRelay session. Note ConversationRelay requires "
                f"Twilio's Security or Enterprise Edition for HIPAA eligibility."
            )

    async def accept(self, socket: WebSocketLike) -> None:
        """Hand a newly connected Twilio socket to the next waiting call."""
        await self._pending.put(socket)

    async def open(self, tenant: TenantContext, call_id: str) -> ConversationRelaySession:
        self._check_baa(tenant)
        try:
            socket = await asyncio.wait_for(self._pending.get(), timeout=self._connect_timeout)
        except TimeoutError:
            # Waiting forever here is the failure mode that wastes an
            # afternoon: the command simply hangs with no output.
            raise NoInboundCallError(
                f"no ConversationRelay connection arrived within "
                f"{self._connect_timeout:.0f}s. Twilio dials us, so this needs a "
                f"real call to a provisioned number pointed at our WebSocket URL "
                f"— the loopback caller cannot stand in for it."
            ) from None
        return ConversationRelaySession(socket, tenant)

    def session_for(self, socket: WebSocketLike, tenant: TenantContext) -> ConversationRelaySession:
        """Build a session directly from a socket, bypassing the queue.

        For a server that already knows which tenant a connection belongs to,
        which is the normal case once tenant resolution happens at the webhook.
        """
        self._check_baa(tenant)
        return ConversationRelaySession(socket, tenant)
