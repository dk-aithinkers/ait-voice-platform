"""The synthesised-caller harness.

What matters here is that the harness does not flatter the system: audio is
paced at telephony rate, silence is real μ-law silence, and the caller's lines
are rendered before the clock starts.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import pytest

from ait_voice.core.types import PHI, Region, TenantContext, Utterance
from ait_voice.providers.loopback import (
    BYTES_PER_SECOND,
    FRAME_BYTES,
    SILENCE_BYTE,
    CountingSink,
    LoopbackTelephony,
    render_caller_audio,
)


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="t", region=Region.INDIA)


class FakeTTS:
    name = "fake-tts"

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def synthesize(
        self, tenant: TenantContext, utterance: Utterance, *, voice: str | None = None
    ) -> AsyncIterator[bytes]:
        self.calls.append(utterance.text.reveal())
        yield b"\x01" * 400
        yield b"\x02" * 400


class TestRendering:
    async def test_one_blob_per_line(self) -> None:
        tts = FakeTTS()
        audio = await render_caller_audio(tts, _tenant(), ["one", "two", "three"])

        assert len(audio) == 3
        assert tts.calls == ["one", "two", "three"]

    async def test_chunks_are_joined(self) -> None:
        audio = await render_caller_audio(FakeTTS(), _tenant(), ["hello"])
        assert len(audio[0]) == 800


class TestPacing:
    async def test_audio_is_framed_at_twenty_milliseconds(self) -> None:
        telephony = LoopbackTelephony([b"\x01" * 1600], realtime=False)
        inbound, _ = await telephony.stream(_tenant(), "c-1")

        frames = [f async for f in inbound]

        assert all(len(f) <= FRAME_BYTES for f in frames)
        assert FRAME_BYTES / BYTES_PER_SECOND == pytest.approx(0.02)

    async def test_realtime_pacing_actually_takes_time(self) -> None:
        """Audio pushed faster than real time yields latencies no call achieves."""
        half_second = b"\x01" * (BYTES_PER_SECOND // 2)
        telephony = LoopbackTelephony([half_second], gap_seconds=0.0)
        inbound, _ = await telephony.stream(_tenant(), "c-2")

        started = time.perf_counter()
        async for _ in inbound:
            pass
        elapsed = time.perf_counter() - started

        # 0.5s of speech plus the 1s trailing silence, minus scheduler slack.
        assert elapsed > 1.0

    async def test_gap_is_mulaw_silence_not_zero_bytes(self) -> None:
        """0x00 is full-scale negative in mu-law — a loud tone, not silence."""
        telephony = LoopbackTelephony(
            [b"\x01" * FRAME_BYTES], gap_seconds=0.1, realtime=False
        )
        inbound, _ = await telephony.stream(_tenant(), "c-3")

        payload = b"".join([f async for f in inbound])

        assert SILENCE_BYTE == b"\xff"
        assert b"\xff" * 100 in payload
        assert b"\x00" * 100 not in payload

    async def test_trailing_silence_lets_the_last_utterance_endpoint(self) -> None:
        telephony = LoopbackTelephony(
            [b"\x01" * FRAME_BYTES], gap_seconds=0.0, realtime=False
        )
        inbound, _ = await telephony.stream(_tenant(), "c-4")

        payload = b"".join([f async for f in inbound])

        assert payload.endswith(SILENCE_BYTE * 100)
        assert len(payload) >= FRAME_BYTES + BYTES_PER_SECOND


class TestCountingSink:
    async def test_counts_without_retaining(self) -> None:
        """Retaining would hold synthesised PHI for the length of the call."""
        sink = CountingSink()
        await sink.write(b"\x00" * 10)
        await sink.write(b"\x00" * 5)

        assert sink.total_bytes == 15
        assert sink.writes == 2
        assert not hasattr(sink, "chunks")

    async def test_clear_is_a_no_op_that_exists_for_barge_in(self) -> None:
        sink = CountingSink()
        await sink.clear()
        await sink.close()
        assert sink.closed


class TestEndToEndThroughThePipeline:
    async def test_a_full_call_runs_on_pre_rendered_audio(self) -> None:
        """The harness has to satisfy the real pipeline, not a stub of it."""
        from ait_voice.core.pipeline import VoicePipeline
        from ait_voice.providers.base import ProviderRegistry, ProviderSet
        from ait_voice.providers.offline import OfflineLLM, OfflineSTT, OfflineTTS

        audio = await render_caller_audio(FakeTTS(), _tenant(), ["book me in"])
        registry = ProviderRegistry()
        registry.register(
            Region.INDIA,
            ProviderSet(
                stt=OfflineSTT(script=["book me in"]),
                llm=OfflineLLM(),
                tts=OfflineTTS(),
                telephony=LoopbackTelephony(audio, gap_seconds=0.0, realtime=False),
            ),
        )

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-live")

        assert result.turns >= 1
        assert result.providers["telephony"] == "loopback-telephony"


class TestPHIHandling:
    async def test_rendering_wraps_lines_as_phi(self) -> None:
        """The caller's words are PHI even when we wrote them ourselves."""

        class Checking(FakeTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                assert isinstance(utterance.text, PHI)
                async for c in super().synthesize(tenant, utterance, voice=voice):
                    yield c

        await render_caller_audio(Checking(), _tenant(), ["my name is Priya"])
