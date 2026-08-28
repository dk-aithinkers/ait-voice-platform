"""Offline providers — no network, no credentials, no PHI leaving the machine.

These exist so the pipeline is runnable and testable from the first commit, and
so the shape of the system can be proven before a single vendor contract is
signed. They are not mocks in the test-double sense: they implement the real
protocols and are wired through the real registry, so exercising them exercises
the actual code path a vendor provider will take.

They also serve the test-data rule affirmed at practices discovery: synthetic
fixtures only in the repository and CI. Real call recordings never enter the
repo, so the default providers must not need them.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ait_voice.core.types import PHI, TenantContext, Utterance
from ait_voice.providers.base import AudioSink, ProviderSet

#: Rough synthesis rate, so the offline TTS produces a plausible amount of audio
#: rather than an instant empty stream. Nothing depends on the exact value.
_BYTES_PER_CHAR = 320


class OfflineSTT:
    """Echoes scripted caller turns as if recognised from audio."""

    name = "offline-stt"

    def __init__(self, script: list[str] | None = None, latency_ms: float = 250.0) -> None:
        self._script = list(script or [])
        self._latency_ms = latency_ms

    async def transcribe(
        self,
        tenant: TenantContext,
        audio: AsyncIterator[bytes],
        *,
        language: str | None = None,
    ) -> AsyncIterator[Utterance]:
        # Drain the inbound stream so the caller side behaves realistically even
        # though the content is ignored.
        async for _chunk in audio:
            break
        for line in self._script:
            await asyncio.sleep(self._latency_ms / 1000)
            yield Utterance(text=PHI(line), is_final=True, language=language)


class OfflineLLM:
    """A deterministic receptionist good enough to prove the loop.

    Deliberately not clever. Its job is to make the pipeline runnable and the
    latency measurable, not to be the agent — that arrives with a real model
    behind the same protocol.
    """

    name = "offline-llm"

    def __init__(self, latency_ms: float = 400.0) -> None:
        self._latency_ms = latency_ms

    async def respond(
        self,
        tenant: TenantContext,
        history: list[Utterance],
        *,
        system_prompt: str,
    ) -> Utterance:
        await asyncio.sleep(self._latency_ms / 1000)
        last = history[-1].text.reveal().lower() if history else ""

        if any(w in last for w in ("person", "human", "someone", "receptionist")):
            reply = "Of course — let me put you through to someone now."
        elif any(w in last for w in ("pain", "chest", "bleeding", "emergency", "symptom")):
            # FR5.2: clinical content escalates without a recovery attempt, and
            # the agent does not attempt an answer.
            reply = "I'm not able to advise on that. Let me get you to someone who can."
        elif any(w in last for w in ("book", "appointment", "see the doctor")):
            reply = "I can help with that. What day suits you?"
        elif any(w in last for w in ("cancel", "move", "reschedule")):
            reply = "I can change that for you. Which appointment is it?"
        else:
            reply = "I can help with appointments. Would you like to book, change or cancel one?"

        return Utterance(text=PHI(reply), is_final=True)


class OfflineTTS:
    """Produces silence of a plausible length, chunked like real streaming audio."""

    name = "offline-tts"

    def __init__(self, first_audio_ms: float = 200.0, chunk_bytes: int = 3200) -> None:
        self._first_audio_ms = first_audio_ms
        self._chunk_bytes = chunk_bytes

    async def synthesize(
        self,
        tenant: TenantContext,
        utterance: Utterance,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        await asyncio.sleep(self._first_audio_ms / 1000)
        total = max(len(utterance.text.reveal()) * _BYTES_PER_CHAR, self._chunk_bytes)
        emitted = 0
        while emitted < total:
            size = min(self._chunk_bytes, total - emitted)
            yield b"\x00" * size
            emitted += size
            await asyncio.sleep(0.005)


class CollectingSink:
    """An audio sink that keeps what it was given, for assertions."""

    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.closed = False

    async def write(self, chunk: bytes) -> None:
        self.chunks.append(chunk)

    async def close(self) -> None:
        self.closed = True

    @property
    def total_bytes(self) -> int:
        return sum(len(c) for c in self.chunks)


class OfflineTelephony:
    """A call leg with no carrier behind it."""

    name = "offline-telephony"

    def __init__(self, inbound_chunks: int = 3) -> None:
        self._inbound_chunks = inbound_chunks

    async def stream(
        self,
        tenant: TenantContext,
        call_id: str,
    ) -> tuple[AsyncIterator[bytes], AudioSink]:
        async def inbound() -> AsyncIterator[bytes]:
            for _ in range(self._inbound_chunks):
                await asyncio.sleep(0.005)
                yield b"\x00" * 1600

        return inbound(), CollectingSink()


def offline_provider_set(script: list[str] | None = None) -> ProviderSet:
    """A complete provider set that runs anywhere, with no credentials."""
    return ProviderSet(
        stt=OfflineSTT(script=script),
        llm=OfflineLLM(),
        tts=OfflineTTS(),
        telephony=OfflineTelephony(),
    )
