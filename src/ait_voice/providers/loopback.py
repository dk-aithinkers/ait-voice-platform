"""A caller made of synthesised audio, for exercising the live chain.

D-03 wants the orchestration validated end to end; D-02 wants Indic accuracy
measured. Both normally need a phone call, which needs a provisioned number and
a person to dial it. This module removes the phone call from the first of those
two — not from the second.

The caller's lines are rendered to audio by the real TTS **before the call
starts**, then played into the real STT at telephony pace. What that measures is
real: real recognition latency, real model round-trips, real synthesis. What it
does not measure is **accuracy against human speech**. Synthesised audio is
clean, evenly paced, and free of the accent, noise and code-switching that make
Indic recognition hard. A good result here is therefore evidence that the
*chain works*, and no evidence at all about R-01. D-02 still needs real
recordings from real speakers, held in the PHI environment defined for them —
never in this repository.

Pre-rendering matters for the numbers. If the caller's audio were synthesised
lazily inside the STT read loop, the TTS round-trip would land inside the
measured recognition window and the latency table would be reporting our own
synthesis time as the vendor's.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from ait_voice.core.types import PHI, TenantContext, Utterance
from ait_voice.providers.base import AudioSink, TTSProvider

#: 8 kHz, 8-bit μ-law: one byte per sample, so 8000 bytes is one second.
BYTES_PER_SECOND = 8000
#: 20 ms frames, which is what a carrier delivers.
FRAME_BYTES = 160
#: μ-law digital silence. Not zero — 0x00 is full-scale negative in μ-law, and
#: feeding a stream of it to an STT is feeding it a loud tone.
SILENCE_BYTE = b"\xff"


async def render_caller_audio(
    tts: TTSProvider,
    tenant: TenantContext,
    script: list[str],
) -> list[bytes]:
    """Synthesise each caller line up front. One audio blob per line."""
    rendered: list[bytes] = []
    for line in script:
        chunks = [
            chunk
            async for chunk in tts.synthesize(tenant, Utterance(text=PHI(line)))
        ]
        rendered.append(b"".join(chunks))
    return rendered


class LoopbackTelephony:
    """A call leg whose caller is pre-rendered audio, played at real time.

    Pacing is deliberate. Audio pushed faster than real time produces
    recognition latencies no live call could ever achieve, and a latency table
    that flatters the system is worse than no table.
    """

    name = "loopback-telephony"

    def __init__(
        self,
        audio: list[bytes],
        *,
        gap_seconds: float = 0.8,
        realtime: bool = True,
    ) -> None:
        """
        Args:
            gap_seconds: Silence played after each line. Must exceed the STT's
                endpointing window or the utterances run together into one.
        """
        self._audio = audio
        self._gap_seconds = gap_seconds
        self._realtime = realtime

    async def stream(
        self,
        tenant: TenantContext,
        call_id: str,
    ) -> tuple[AsyncIterator[bytes], AudioSink]:
        return self._inbound(), CountingSink()

    async def _inbound(self) -> AsyncIterator[bytes]:
        for blob in self._audio:
            async for frame in self._paced(blob):
                yield frame
            gap = SILENCE_BYTE * int(BYTES_PER_SECOND * self._gap_seconds)
            async for frame in self._paced(gap):
                yield frame
        # Trailing silence, so the last utterance endpoints rather than
        # hanging on an abruptly closed stream.
        async for frame in self._paced(SILENCE_BYTE * BYTES_PER_SECOND):
            yield frame

    async def _paced(self, blob: bytes) -> AsyncIterator[bytes]:
        for offset in range(0, len(blob), FRAME_BYTES):
            if self._realtime:
                await asyncio.sleep(FRAME_BYTES / BYTES_PER_SECOND)
            yield blob[offset : offset + FRAME_BYTES]


class CountingSink:
    """Outbound audio sink that counts rather than keeping.

    Keeping it would mean holding synthesised PHI in memory for the length of
    the call with nothing reading it.
    """

    def __init__(self) -> None:
        self.total_bytes = 0
        self.writes = 0
        self.closed = False

    async def write(self, chunk: bytes) -> None:
        self.total_bytes += len(chunk)
        self.writes += 1

    async def clear(self) -> None:
        """Barge-in. Nothing buffered here, so there is nothing to drop."""

    async def close(self) -> None:
        self.closed = True
