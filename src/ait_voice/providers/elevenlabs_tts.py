"""ElevenLabs text-to-speech provider.

Vendor SDK imported inside this module only — the provider boundary.

**Why this vendor for US and not necessarily India.** `docs/vendors.md` measured
ElevenLabs Flash at 264–288ms time-to-first-audio independently, has an India
region at Enterprise tier, and offers a BAA with Zero Retention Mode. Its
`hinglish_mode` exists but is an Agents-platform feature with language fixed per
call, so it does not deliver the mid-sentence code-switching that is this
product's stated differentiator. Rumik claims that capability and is roughly ten
times cheaper — and has no HIPAA posture whatsoever, with terms that disclaim
clinical use.

That contradiction is not resolvable by choosing better. It is why TTS is
selected per region.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

# The vendor SDK's own types stop at this boundary — which is the point
# of having one. `Any` is confined to this file and its siblings.
from typing import Any

from ait_voice.core.types import TenantContext, Utterance
from ait_voice.providers.base import BAANotConfirmedError

#: μ-law 8kHz — what telephony carriers actually carry. Requesting a studio
#: format and downsampling would add latency to the leg NFR1.1 measures most
#: tightly.
TELEPHONY_FORMAT = "ulaw_8000"


class ElevenLabsTTS:
    """Streaming synthesis via ElevenLabs."""

    name = "elevenlabs"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",
        model: str = "eleven_flash_v2_5",
        baa_confirmed: bool = False,
    ) -> None:
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set")
        self._voice_id = voice_id
        self._model = model
        self._baa_confirmed = baa_confirmed
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import AsyncElevenLabs

            self._client = AsyncElevenLabs(api_key=self._api_key)
        return self._client

    async def synthesize(
        self,
        tenant: TenantContext,
        utterance: Utterance,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:

        # What the agent says can itself carry PHI — reading back an
        # appointment, confirming a name. Synthesis is a PHI processing step,
        # not a neutral rendering step.
        if tenant.is_phi_jurisdiction and not self._baa_confirmed:
            raise BAANotConfirmedError(
                f"tenant {tenant.tenant_id!r} is in a PHI jurisdiction and no BAA "
                f"is confirmed for provider {self.name!r}; refusing to synthesise"
            )

        client = self._get_client()
        stream = client.text_to_speech.stream(
            voice_id=voice or self._voice_id,
            model_id=self._model,
            text=utterance.text.reveal(),
            output_format=TELEPHONY_FORMAT,
        )

        async for chunk in stream:
            if chunk:
                yield chunk
