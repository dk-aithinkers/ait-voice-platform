"""The cascaded transport: three vendors composed into one conversation.

This is what the pipeline always did, lifted out into a
:class:`~ait_voice.providers.base.DialogTransport` so that a bundled vendor can
sit beside it under the same dialog policy. Nothing about the behaviour changed
in the lifting; the disclosure, escalation, turn limits and timing all still
live in the pipeline, because those are policy and this is transport.

Cascaded is the default and C-T3 is why: keeping text at every stage means each
vendor is independently BAA-able and auditable, prompts and guardrails work
normally, and — per C-T1 — any leg can be swapped per region without touching
the others.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from ait_voice.core.types import TenantContext, Utterance
from ait_voice.providers.base import (
    AudioSink,
    DialogTransport,
    ProviderSet,
    SpeechTiming,
    STTProvider,
    TTSProvider,
)


class CascadedSession:
    """A call carried by separate STT, TTS and telephony vendors."""

    def __init__(
        self,
        tenant: TenantContext,
        stt: STTProvider,
        tts: TTSProvider,
        inbound: AsyncIterator[bytes],
        sink: AudioSink,
    ) -> None:
        self._tenant = tenant
        self._stt = stt
        self._tts = tts
        self._inbound = inbound
        self._sink = sink

    def listen(self) -> AsyncIterator[Utterance]:
        """Yield final caller utterances.

        Interim results are dropped here rather than in the pipeline. They
        exist for barge-in, which is the transport's concern — the dialog
        policy above has no use for a half-recognised sentence.
        """

        async def finals() -> AsyncIterator[Utterance]:
            async for utterance in self._stt.transcribe(self._tenant, self._inbound):
                if utterance.is_final:
                    yield utterance

        return finals()

    async def speak(self, utterance: Utterance) -> SpeechTiming:
        """Synthesise and play. Time to first audio is directly observable."""
        started = time.perf_counter()
        first_audio_ms = 0.0
        async for chunk in self._tts.synthesize(self._tenant, utterance):
            if first_audio_ms == 0.0:
                first_audio_ms = (time.perf_counter() - started) * 1000
            await self._sink.write(chunk)
        if first_audio_ms == 0.0:
            # No audio came back at all. Report the elapsed time rather than a
            # zero, which would silently improve the p95.
            first_audio_ms = (time.perf_counter() - started) * 1000
        return SpeechTiming(elapsed_ms=first_audio_ms, observed_audio=True)

    async def close(self) -> None:
        await self._sink.close()


class CascadedTransport:
    """Composes a :class:`ProviderSet`'s speech legs into one conversation."""

    observes_audio = True

    def __init__(self, providers: ProviderSet) -> None:
        self._providers = providers
        self.name = (
            f"cascaded({providers.stt.name}+{providers.tts.name}+{providers.telephony.name})"
        )

    async def open(self, tenant: TenantContext, call_id: str) -> CascadedSession:
        inbound, sink = await self._providers.telephony.stream(tenant, call_id)
        return CascadedSession(
            tenant=tenant,
            stt=self._providers.stt,
            tts=self._providers.tts,
            inbound=inbound,
            sink=sink,
        )


def transport_for(providers: ProviderSet) -> DialogTransport:
    """The transport a provider set should use.

    A bundled vendor if one is configured, otherwise the cascade. One place
    makes this decision, so there is one place to audit it.
    """
    return providers.dialog or CascadedTransport(providers)
