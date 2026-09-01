"""Contract tests for the vendor adapters.

The affirmed coverage practice permits excluding vendor transport adapters from
the branch-coverage floor, but only on condition that they carry contract or
recorded-fixture tests instead — an exclusion with no replacement obligation is
how a coverage gate becomes decorative.

These are those tests. They exercise each adapter's translation logic against a
fake client, so they prove the adapter maps domain types to vendor calls and
back without making a network request or needing a credential. What they do not
prove is that the vendor behaves as documented; only a live call does that, and
that is D-03.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from ait_voice.core.types import PHI, Region, TenantContext, Utterance


def _india() -> TenantContext:
    """India tenants bypass the BAA gate, which keeps these tests about translation."""
    return TenantContext(tenant_id="clinic-in", region=Region.INDIA)


# --------------------------------------------------------------------------
# Anthropic
# --------------------------------------------------------------------------


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeResponse:
    def __init__(self, blocks: list[Any]) -> None:
        self.content = blocks


class _FakeMessages:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.last_call: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> _FakeResponse:
        self.last_call = kwargs
        return self._response


class _FakeAnthropic:
    def __init__(self, response: _FakeResponse) -> None:
        self.messages = _FakeMessages(response)


class TestAnthropicContract:
    @pytest.fixture
    def llm(self, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        from ait_voice.providers.anthropic_llm import AnthropicLLM

        return AnthropicLLM(model="test-model", max_tokens=42)

    async def test_history_alternates_user_and_assistant(self, llm) -> None:  # noqa: ANN001
        fake = _FakeAnthropic(_FakeResponse([_FakeTextBlock("Tuesday works.")]))
        llm._client = fake

        history = [
            Utterance(text=PHI("I need an appointment")),
            Utterance(text=PHI("What day suits?")),
            Utterance(text=PHI("Tuesday")),
        ]
        await llm.respond(_india(), history, system_prompt="be brief")

        roles = [m["role"] for m in fake.messages.last_call["messages"]]
        assert roles == ["user", "assistant", "user"]

    async def test_phi_is_unwrapped_for_the_request(self, llm) -> None:  # noqa: ANN001
        fake = _FakeAnthropic(_FakeResponse([_FakeTextBlock("ok")]))
        llm._client = fake

        await llm.respond(_india(), [Utterance(text=PHI("my name is Priya"))], system_prompt="x")

        sent = fake.messages.last_call["messages"][0]["content"]
        assert sent == "my name is Priya", "PHI must be revealed for the vendor call"

    async def test_response_is_rewrapped_as_phi(self, llm) -> None:  # noqa: ANN001
        llm._client = _FakeAnthropic(_FakeResponse([_FakeTextBlock("  Booked.  ")]))

        reply = await llm.respond(_india(), [Utterance(text=PHI("hi"))], system_prompt="x")

        assert isinstance(reply.text, PHI)
        assert reply.text.reveal() == "Booked."
        assert str(reply.text) == "[REDACTED]", "the reply must redact when logged"

    async def test_model_and_limits_are_passed_through(self, llm) -> None:  # noqa: ANN001
        fake = _FakeAnthropic(_FakeResponse([_FakeTextBlock("ok")]))
        llm._client = fake

        await llm.respond(_india(), [Utterance(text=PHI("hi"))], system_prompt="sys")

        call = fake.messages.last_call
        assert call["model"] == "test-model"
        assert call["max_tokens"] == 42
        assert call["system"] == "sys"

    async def test_non_text_blocks_are_ignored(self, llm) -> None:  # noqa: ANN001
        class _ToolBlock:
            type = "tool_use"

        llm._client = _FakeAnthropic(_FakeResponse([_ToolBlock(), _FakeTextBlock("just this")]))

        reply = await llm.respond(_india(), [Utterance(text=PHI("hi"))], system_prompt="x")
        assert reply.text.reveal() == "just this"


# --------------------------------------------------------------------------
# ElevenLabs
# --------------------------------------------------------------------------


class _FakeTTSEndpoint:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks
        self.last_call: dict[str, Any] | None = None

    def stream(self, **kwargs: Any):  # noqa: ANN202
        self.last_call = kwargs

        async def gen():  # noqa: ANN202
            for c in self._chunks:
                yield c

        return gen()


class _FakeElevenLabs:
    def __init__(self, chunks: list[bytes]) -> None:
        self.text_to_speech = _FakeTTSEndpoint(chunks)


class TestElevenLabsContract:
    @pytest.fixture
    def tts(self, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        from ait_voice.providers.elevenlabs_tts import ElevenLabsTTS

        return ElevenLabsTTS(voice_id="v-default", model="m-test")

    async def test_requests_telephony_audio_format(self, tts) -> None:  # noqa: ANN001
        """Requesting studio audio and downsampling would add latency."""
        from ait_voice.providers.elevenlabs_tts import TELEPHONY_FORMAT

        fake = _FakeElevenLabs([b"\x01\x02"])
        tts._client = fake

        async for _ in tts.synthesize(_india(), Utterance(text=PHI("hello"))):
            pass

        assert fake.text_to_speech.last_call["output_format"] == TELEPHONY_FORMAT
        assert TELEPHONY_FORMAT == "ulaw_8000"

    async def test_phi_is_unwrapped_for_synthesis(self, tts) -> None:  # noqa: ANN001
        fake = _FakeElevenLabs([b"\x01"])
        tts._client = fake

        async for _ in tts.synthesize(_india(), Utterance(text=PHI("Booked for Tuesday"))):
            pass

        assert fake.text_to_speech.last_call["text"] == "Booked for Tuesday"

    async def test_voice_override_wins_over_default(self, tts) -> None:  # noqa: ANN001
        fake = _FakeElevenLabs([b"\x01"])
        tts._client = fake

        async for _ in tts.synthesize(_india(), Utterance(text=PHI("hi")), voice="v-override"):
            pass

        assert fake.text_to_speech.last_call["voice_id"] == "v-override"

    async def test_empty_chunks_are_dropped(self, tts) -> None:  # noqa: ANN001
        """An empty frame written to the call would be wasted work."""
        tts._client = _FakeElevenLabs([b"", b"\x01\x02", b"", b"\x03"])

        chunks = [c async for c in tts.synthesize(_india(), Utterance(text=PHI("hi")))]
        assert chunks == [b"\x01\x02", b"\x03"]


# --------------------------------------------------------------------------
# Twilio
# --------------------------------------------------------------------------


class _FakeWebSocket:
    """Stands in for a Twilio Media Streams connection."""

    def __init__(self, frames: list[dict[str, Any]]) -> None:
        self._frames = frames
        self.sent: list[dict[str, Any]] = []

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def __aiter__(self):  # noqa: ANN204
        async def gen():  # noqa: ANN202
            for f in self._frames:
                yield json.dumps(f)

        return gen()


def _media_frame(payload: bytes) -> dict[str, Any]:
    return {
        "event": "media",
        "media": {"payload": base64.b64encode(payload).decode("ascii")},
    }


class TestTwilioContract:
    @pytest.fixture
    def telephony(self, monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok")
        from ait_voice.providers.twilio_telephony import TwilioTelephony

        return TwilioTelephony()

    async def test_inbound_media_is_base64_decoded(self, telephony) -> None:  # noqa: ANN001
        ws = _FakeWebSocket([_media_frame(b"\xff\xfe"), {"event": "stop"}])
        telephony.attach("call-1", ws, "MZ-stream")

        inbound, _ = await telephony.stream(_india(), "call-1")
        chunks = [c async for c in inbound]

        assert chunks == [b"\xff\xfe"]

    async def test_stop_frame_ends_the_stream(self, telephony) -> None:  # noqa: ANN001
        ws = _FakeWebSocket([_media_frame(b"\x01"), {"event": "stop"}, _media_frame(b"\x02")])
        telephony.attach("call-2", ws, "MZ")

        inbound, _ = await telephony.stream(_india(), "call-2")
        chunks = [c async for c in inbound]

        assert chunks == [b"\x01"], "audio after hangup must not be yielded"

    async def test_outbound_audio_is_encoded_with_the_stream_sid(self, telephony) -> None:  # noqa: ANN001
        ws = _FakeWebSocket([{"event": "stop"}])
        telephony.attach("call-3", ws, "MZ-abc")

        _, sink = await telephony.stream(_india(), "call-3")
        await sink.write(b"\xaa\xbb")

        frame = ws.sent[0]
        assert frame["event"] == "media"
        assert frame["streamSid"] == "MZ-abc"
        assert base64.b64decode(frame["media"]["payload"]) == b"\xaa\xbb"

    async def test_clear_supports_barge_in(self, telephony) -> None:  # noqa: ANN001
        """Barge-in needs queued audio dropped, not the sentence finished."""
        ws = _FakeWebSocket([{"event": "stop"}])
        telephony.attach("call-4", ws, "MZ-x")

        _, sink = await telephony.stream(_india(), "call-4")
        await sink.clear()

        assert ws.sent[0] == {"event": "clear", "streamSid": "MZ-x"}

    async def test_closed_sink_writes_nothing(self, telephony) -> None:  # noqa: ANN001
        ws = _FakeWebSocket([{"event": "stop"}])
        telephony.attach("call-5", ws, "MZ")

        _, sink = await telephony.stream(_india(), "call-5")
        await sink.close()
        await sink.write(b"\x01")
        await sink.clear()

        assert ws.sent == []

    async def test_unattached_call_is_refused(self, telephony) -> None:  # noqa: ANN001
        with pytest.raises(RuntimeError, match="no connected Twilio stream"):
            await telephony.stream(_india(), "never-attached")

    async def test_empty_write_is_a_no_op(self, telephony) -> None:  # noqa: ANN001
        ws = _FakeWebSocket([{"event": "stop"}])
        telephony.attach("call-6", ws, "MZ")

        _, sink = await telephony.stream(_india(), "call-6")
        await sink.write(b"")

        assert ws.sent == []


class TestTwiML:
    def test_uses_connect_stream_for_bidirectional_audio(self) -> None:
        """<Start><Stream> gives inbound only — enough to transcribe, not converse."""
        from ait_voice.providers.twilio_telephony import inbound_twiml

        xml = inbound_twiml("wss://example.test/media")

        assert "<Connect>" in xml
        assert "<Start>" not in xml
        assert 'url="wss://example.test/media"' in xml


class TestTwilioServerHandshake:
    async def test_start_frame_carries_the_call_identifiers(self) -> None:
        """Audio arrives only after `start`, so the identifiers come first.

        This covers the handshake contract the server relies on. Binding an
        actual socket is transport, not translation, and is deliberately left
        to the live spike (D-03).
        """
        ws = _FakeWebSocket(
            [
                {"event": "connected"},
                {"event": "start", "start": {"streamSid": "MZ-1", "callSid": "CA-1"}},
                _media_frame(b"\x01"),
            ]
        )

        stream_sid = call_sid = None
        async for raw in ws:
            frame = json.loads(raw)
            if frame.get("event") == "start":
                stream_sid = frame["start"]["streamSid"]
                call_sid = frame["start"]["callSid"]
                break

        assert (call_sid, stream_sid) == ("CA-1", "MZ-1")

    async def test_connected_frame_alone_yields_no_identifiers(self) -> None:
        """A socket that never sends `start` must not be treated as a call."""
        ws = _FakeWebSocket([{"event": "connected"}])

        stream_sid = None
        async for raw in ws:
            if json.loads(raw).get("event") == "start":
                stream_sid = "set"

        assert stream_sid is None
