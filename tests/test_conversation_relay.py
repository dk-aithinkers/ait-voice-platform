"""Twilio ConversationRelay, and the claim that it is interchangeable.

The load-bearing test in this file is TestPolicyIsIdentical: the same dialog
policy has to produce the same escalation decisions over either transport. If
that ever stops holding, the bundle is not a swappable option — it is a second
implementation of a safety-critical rule.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from ait_voice.core.pipeline import ESCALATE_CALLER_REQUEST, VoicePipeline
from ait_voice.core.types import PHI, Region, TenantContext, Utterance
from ait_voice.providers.base import (
    BAANotConfirmedError,
    DialogSession,
    DialogTransport,
    ProviderRegistry,
    ProviderSet,
)
from ait_voice.providers.conversation_relay import (
    ConversationRelaySession,
    ConversationRelayTransport,
    RelayConfig,
    RelayError,
    inbound_twiml,
)
from ait_voice.providers.offline import OfflineLLM, OfflineSTT, OfflineTelephony, OfflineTTS


def _tenant(region: Region = Region.INDIA) -> TenantContext:
    return TenantContext(tenant_id="clinic-1", region=region)


class FakeSocket:
    """A Twilio WebSocket, scripted."""

    def __init__(self, incoming: list[dict[str, Any]] | None = None) -> None:
        self.incoming = incoming or []
        self.sent: list[dict[str, Any]] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def __aiter__(self) -> AsyncIterator[str]:
        async def gen() -> AsyncIterator[str]:
            for message in self.incoming:
                yield json.dumps(message)

        return gen()


def _prompt(text: str, *, last: bool = True) -> dict[str, Any]:
    return {"type": "prompt", "voicePrompt": text, "lang": "en-US", "last": last}


class TestProtocolConformance:
    def test_the_transport_satisfies_the_protocol(self) -> None:
        assert isinstance(ConversationRelayTransport(), DialogTransport)

    def test_a_session_satisfies_the_protocol(self) -> None:
        session = ConversationRelaySession(FakeSocket(), _tenant())
        assert isinstance(session, DialogSession)


class TestListening:
    async def test_only_completed_prompts_reach_the_dialog(self) -> None:
        """Partials exist for barge-in, which Twilio already handles."""
        socket = FakeSocket(
            [
                _prompt("book", last=False),
                _prompt("book an app", last=False),
                _prompt("book an appointment", last=True),
            ]
        )
        session = ConversationRelaySession(socket, _tenant())

        heard = [u.text.reveal() async for u in session.listen()]

        assert heard == ["book an appointment"]

    async def test_setup_records_the_call_and_wraps_identity_as_phi(self) -> None:
        """C-R2 — a phone number is a listed identifier, not a plain string."""
        socket = FakeSocket(
            [
                {
                    "type": "setup",
                    "sessionId": "VX1",
                    "callSid": "CA1",
                    "direction": "inbound",
                    "from": "+919876543210",
                    "to": "+911140001234",
                    "customParameters": {"tenant": "clinic-1"},
                },
                _prompt("hello"),
            ]
        )
        session = ConversationRelaySession(socket, _tenant())

        _ = [u async for u in session.listen()]

        assert session.info.call_sid == "CA1"
        assert isinstance(session.info.from_number, PHI)
        assert "9876543210" not in repr(session.info.from_number)
        assert session.info.custom["tenant"] == "clinic-1"

    async def test_an_unparseable_frame_does_not_kill_the_call(self) -> None:
        class BadSocket(FakeSocket):
            def __aiter__(self) -> AsyncIterator[str]:
                async def gen() -> AsyncIterator[str]:
                    yield "{not json"
                    yield json.dumps(_prompt("still here"))

                return gen()

        session = ConversationRelaySession(BadSocket(), _tenant())

        heard = [u.text.reveal() async for u in session.listen()]

        assert heard == ["still here"]

    async def test_an_error_frame_raises(self) -> None:
        """It routes to the pipeline's dependency-failure path, not to silence."""
        socket = FakeSocket([{"type": "error", "description": "tts unavailable"}])
        session = ConversationRelaySession(socket, _tenant())

        with pytest.raises(RelayError, match="tts unavailable"):
            _ = [u async for u in session.listen()]

    async def test_interruptions_and_digits_are_kept(self) -> None:
        socket = FakeSocket(
            [
                {
                    "type": "interrupt",
                    "utteranceUntilInterrupt": "Sure, I can",
                    "durationUntilInterruptMs": 420,
                },
                {"type": "dtmf", "digit": "3"},
                _prompt("actually a person please"),
            ]
        )
        session = ConversationRelaySession(socket, _tenant())

        _ = [u async for u in session.listen()]

        assert session.interruptions == [420.0]
        assert session.digits == ["3"]

    async def test_an_empty_prompt_is_not_yielded(self) -> None:
        socket = FakeSocket([_prompt("")])
        session = ConversationRelaySession(socket, _tenant())
        assert [u async for u in session.listen()] == []


class TestSpeaking:
    async def test_text_is_sent_as_a_final_token(self) -> None:
        socket = FakeSocket()
        session = ConversationRelaySession(socket, _tenant())

        await session.speak(Utterance(text=PHI("Of course, what day suits you?")))

        assert socket.sent[0]["type"] == "text"
        assert socket.sent[0]["token"] == "Of course, what day suits you?"
        assert socket.sent[0]["last"] is True
        assert socket.sent[0]["interruptible"] is True

    async def test_timing_declares_that_audio_was_not_observed(self) -> None:
        """The whole reason SpeechTiming is a type and not a float."""
        session = ConversationRelaySession(FakeSocket(), _tenant())

        timing = await session.speak(Utterance(text=PHI("hello")))

        assert timing.observed_audio is False
        assert timing.elapsed_ms >= 0

    async def test_language_can_be_switched_mid_call(self) -> None:
        socket = FakeSocket()
        session = ConversationRelaySession(socket, _tenant())

        await session.switch_language(tts="hi-IN", transcription="hi-IN")

        assert socket.sent[0] == {
            "type": "language",
            "ttsLanguage": "hi-IN",
            "transcriptionLanguage": "hi-IN",
        }

    async def test_closing_can_carry_handoff_data(self) -> None:
        """C-T6 — the receiving human should not have to ask twice."""
        socket = FakeSocket()
        session = ConversationRelaySession(socket, _tenant())

        await session.close(handoff={"reason": "caller_requested_human", "turns": 3})

        assert socket.sent[-1]["type"] == "end"
        assert json.loads(socket.sent[-1]["handoffData"])["turns"] == 3

    async def test_closing_twice_sends_one_end(self) -> None:
        socket = FakeSocket()
        session = ConversationRelaySession(socket, _tenant())

        await session.close()
        await session.close()

        assert [m["type"] for m in socket.sent].count("end") == 1


class TestBAAGate:
    async def test_a_us_tenant_is_refused_without_a_baa(self) -> None:
        """A bundle touches audio, transcripts and identity at once."""
        transport = ConversationRelayTransport(baa_confirmed=False)

        with pytest.raises(BAANotConfirmedError, match="Security or Enterprise"):
            await transport.open(_tenant(Region.US), "c-1")

    async def test_an_india_tenant_is_not_gated_by_baa(self) -> None:
        transport = ConversationRelayTransport(baa_confirmed=False)
        await transport.accept(FakeSocket())

        session = await transport.open(_tenant(Region.INDIA), "c-2")

        assert isinstance(session, ConversationRelaySession)

    def test_session_for_applies_the_same_gate(self) -> None:
        transport = ConversationRelayTransport(baa_confirmed=False)

        with pytest.raises(BAANotConfirmedError):
            transport.session_for(FakeSocket(), _tenant(Region.US))

    def test_a_confirmed_baa_admits_a_us_tenant(self) -> None:
        transport = ConversationRelayTransport(baa_confirmed=True)
        assert transport.session_for(FakeSocket(), _tenant(Region.US))


class TestTwiML:
    def test_it_connects_a_relay_with_the_chosen_vendors(self) -> None:
        twiml = inbound_twiml(RelayConfig(websocket_url="wss://x.test/relay"))

        assert "<Connect>" in twiml
        assert "<ConversationRelay" in twiml
        assert 'transcriptionProvider="Deepgram"' in twiml
        assert 'ttsProvider="ElevenLabs"' in twiml

    def test_barge_in_is_on_by_default(self) -> None:
        """A receptionist a caller cannot interrupt is worse than a menu."""
        assert 'interruptible="speech"' in inbound_twiml(
            RelayConfig(websocket_url="wss://x.test/r")
        )

    def test_a_clinic_name_with_an_ampersand_is_escaped(self) -> None:
        """Unescaped TwiML is rejected mid-call, and clinic names carry these."""
        twiml = inbound_twiml(
            RelayConfig(websocket_url="wss://x.test/r", welcome_greeting="Ross & Sons")
        )
        assert "Ross &amp; Sons" in twiml
        assert "Ross & Sons" not in twiml

    def test_no_disclosure_is_placed_in_the_template(self) -> None:
        """C-R3/C-R4 stay owned by the pipeline, not by per-tenant TwiML."""
        twiml = inbound_twiml(RelayConfig(websocket_url="wss://x.test/r"))
        assert "AI assistant" not in twiml

    def test_language_is_configurable_per_tenant(self) -> None:
        twiml = inbound_twiml(RelayConfig(websocket_url="wss://x.test/r", language="hi-IN"))
        assert 'language="hi-IN"' in twiml


class TestPolicyIsIdentical:
    """The claim that makes this a swappable transport rather than a fork."""

    @staticmethod
    def _cascaded_registry(script: list[str]) -> ProviderRegistry:
        registry = ProviderRegistry()
        registry.register(
            Region.INDIA,
            ProviderSet(
                stt=OfflineSTT(script=script),
                llm=OfflineLLM(),
                tts=OfflineTTS(),
                telephony=OfflineTelephony(),
            ),
        )
        return registry

    @staticmethod
    def _relay_registry(script: list[str]) -> ProviderRegistry:
        transport = ConversationRelayTransport(baa_confirmed=False)
        socket = FakeSocket([_prompt(line) for line in script])
        # Pre-load the socket the transport will hand out.
        transport._pending.put_nowait(socket)  # noqa: SLF001
        registry = ProviderRegistry()
        registry.register(
            Region.INDIA,
            ProviderSet(
                stt=OfflineSTT(script=script),
                llm=OfflineLLM(),
                tts=OfflineTTS(),
                telephony=OfflineTelephony(),
                dialog=transport,
            ),
        )
        return registry

    @pytest.mark.parametrize(
        ("script", "expect_escalation"),
        [
            (["Can I speak to a person please?"], True),
            (["I'd like to book an appointment"], False),
        ],
    )
    async def test_both_transports_reach_the_same_decision(
        self, script: list[str], expect_escalation: bool
    ) -> None:
        cascaded = await VoicePipeline(self._cascaded_registry(script)).handle_call(
            _tenant(), "c-cascaded"
        )
        relayed = await VoicePipeline(self._relay_registry(script)).handle_call(
            _tenant(), "c-relay"
        )

        assert cascaded.escalated is expect_escalation
        assert relayed.escalated is expect_escalation
        assert cascaded.escalation_reason == relayed.escalation_reason

    async def test_escalation_reason_matches_exactly(self) -> None:
        script = ["Can I speak to a person please?"]
        relayed = await VoicePipeline(self._relay_registry(script)).handle_call(
            _tenant(), "c-relay"
        )
        assert relayed.escalation_reason == str(ESCALATE_CALLER_REQUEST)

    async def test_the_disclosure_is_spoken_over_the_relay_too(self) -> None:
        """FR1.3 cannot depend on which transport a region happens to use."""
        transport = ConversationRelayTransport(baa_confirmed=False)
        socket = FakeSocket([_prompt("hello")])
        transport._pending.put_nowait(socket)  # noqa: SLF001
        registry = ProviderRegistry()
        registry.register(
            Region.INDIA,
            ProviderSet(
                stt=OfflineSTT(),
                llm=OfflineLLM(),
                tts=OfflineTTS(),
                telephony=OfflineTelephony(),
                dialog=transport,
            ),
        )

        await VoicePipeline(registry, clinic_name="Northside").handle_call(_tenant(), "c-d")

        first_spoken = socket.sent[0]["token"].lower()
        assert "ai assistant" in first_spoken
        assert "recorded" in first_spoken
        assert "northside" in first_spoken

    async def test_a_relayed_run_is_marked_as_unmeasurable(self) -> None:
        """Without this flag the bundle reads as faster than it is."""
        relayed = await VoicePipeline(self._relay_registry(["hello"])).handle_call(_tenant(), "c-r")
        cascaded = await VoicePipeline(self._cascaded_registry(["hello"])).handle_call(
            _tenant(), "c-c"
        )

        assert relayed.latency_observable is False
        assert cascaded.latency_observable is True

    async def test_the_describe_record_names_the_bundle_not_the_unused_legs(
        self,
    ) -> None:
        """The provenance record must not claim vendors that never ran."""
        relayed = await VoicePipeline(self._relay_registry(["hello"])).handle_call(_tenant(), "c-p")

        assert relayed.providers["dialog"] == "twilio-conversationrelay"
        assert "stt" not in relayed.providers
        assert "tts" not in relayed.providers


class TestNoInboundCall:
    async def test_waiting_for_a_carrier_times_out_with_an_explanation(self) -> None:
        """Hanging with no output is the failure mode that wastes an afternoon."""
        from ait_voice.providers.conversation_relay import NoInboundCallError

        transport = ConversationRelayTransport(connect_timeout=0.01)

        with pytest.raises(NoInboundCallError, match="loopback caller cannot"):
            await transport.open(_tenant(Region.INDIA), "c-timeout")

    async def test_a_connection_that_arrives_is_used(self) -> None:
        transport = ConversationRelayTransport(connect_timeout=1.0)
        await transport.accept(FakeSocket())

        assert await transport.open(_tenant(Region.INDIA), "c-ok")
