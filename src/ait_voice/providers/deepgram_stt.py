"""Deepgram speech-to-text provider.

Vendor SDK imported inside this module only — the provider boundary.

**On language handling.** `docs/vendors.md` records that Deepgram supports Hindi
in its `multi` code-switching mode but handles other Indic languages as single
language only, and has no Malayalam at all. It also has no India region — EU and
Australia only. So this provider is a reasonable US-tenant choice and a poor
India one, which is precisely why the registry selects providers per region
rather than globally.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from ait_voice.core.types import PHI, TenantContext, Utterance
from ait_voice.providers.base import BAANotConfirmedError


class DeepgramSTT:
    """Streaming transcription via Deepgram's live API."""

    name = "deepgram"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "nova-3",
        sample_rate: int = 8000,
        baa_confirmed: bool = False,
    ) -> None:
        """
        Args:
            sample_rate: 8000 by default because that is what telephony
                actually delivers. Every published accuracy benchmark uses
                clean studio audio; `docs/vendors.md` records that no vendor
                publishes an 8kHz telephony or Indian-accent figure, which is
                the single biggest open risk in vendor selection.
        """
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self._api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is not set")
        self._model = model
        self._sample_rate = sample_rate
        self._baa_confirmed = baa_confirmed

    async def transcribe(
        self,
        tenant: TenantContext,
        audio: AsyncIterator[bytes],
        *,
        language: str | None = None,
    ) -> AsyncIterator[Utterance]:

        if tenant.is_phi_jurisdiction and not self._baa_confirmed:
            raise BAANotConfirmedError(
                f"tenant {tenant.tenant_id!r} is in a PHI jurisdiction and no BAA "
                f"is confirmed for provider {self.name!r}; refusing to send audio"
            )

        from deepgram import AsyncLiveClient, LiveOptions

        options = LiveOptions(
            model=self._model,
            encoding="mulaw",
            sample_rate=self._sample_rate,
            channels=1,
            interim_results=True,
            # Deepgram's own end-of-turn signal. Waiting for it rather than
            # imposing a fixed silence timeout is what keeps the recognition
            # leg of NFR1.1 from dominating the latency budget.
            endpointing=300,
            language=language or "multi",
        )

        client = AsyncLiveClient(self._api_key)
        queue: asyncio.Queue[Utterance | None] = asyncio.Queue()

        async def on_transcript(_self, result, **_kwargs) -> None:  # noqa: ANN001
            alternatives = result.channel.alternatives
            if not alternatives:
                return
            text = alternatives[0].transcript
            if not text:
                return
            await queue.put(
                Utterance(
                    text=PHI(text),
                    is_final=bool(result.is_final),
                    language=language,
                )
            )

        async def on_close(_self, **_kwargs) -> None:  # noqa: ANN001
            await queue.put(None)

        client.on("Results", on_transcript)
        client.on("Close", on_close)

        await client.start(options)

        async def pump() -> None:
            try:
                async for chunk in audio:
                    await client.send(chunk)
            finally:
                await client.finish()

        pump_task = asyncio.create_task(pump())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            pump_task.cancel()
            # Surface a pump failure rather than swallowing it — a dropped
            # audio leg is a silent call, which is the failure mode that
            # matters most on a live line.
            try:
                await pump_task
            except asyncio.CancelledError:
                pass
