"""Provider protocols and the per-region registry.

This module is the boundary constraint C-T1 requires. `docs/vendors.md`
established that no single vendor serves US healthcare and India adequately —
the US-strong vendors have no India region and often no Indic languages, and the
India-strong vendors have no HIPAA posture at all. Per-region vendor selection
behind a stable internal interface is therefore not an architectural nicety, it
is the only configuration that works.

Two conventions affirmed at practices discovery are enforced by this file's
shape:

- **Vendor SDK imports are quarantined.** Nothing outside ``providers/`` imports
  a vendor package. The protocols below are the whole surface the rest of the
  system sees.
- **No vendor vocabulary in domain types.** The protocols speak in
  :class:`~ait_voice.core.types.Utterance` and bytes, never in a vendor's
  request or response objects.

The boundary is drawn **per capability, never per region**. A per-region source
fork would fracture the shared core that the multi-vertical business case is
priced on — each additional agent pack is meant to be roughly 20% incremental
work on an 80% shared core, and that only holds if the core is genuinely shared.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ait_voice.core.types import PHI, Region, TenantContext, Utterance


@runtime_checkable
class STTProvider(Protocol):
    """Speech to text.

    Implementations stream audio in and yield utterances as they are recognised.
    Interim results carry ``is_final=False``; the pipeline uses the final one for
    the dialog turn and the interim ones for barge-in detection.
    """

    name: str

    async def transcribe(
        self,
        tenant: TenantContext,
        audio: AsyncIterator[bytes],
        *,
        language: str | None = None,
    ) -> AsyncIterator[Utterance]:
        """Yield utterances recognised from an audio stream."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """The dialog turn.

    Takes the conversation so far and returns what the agent should say next.
    """

    name: str

    async def respond(
        self,
        tenant: TenantContext,
        history: list[Utterance],
        *,
        system_prompt: str,
    ) -> Utterance:
        """Produce the agent's next utterance."""
        ...


@runtime_checkable
class TTSProvider(Protocol):
    """Text to speech.

    Implementations stream audio out so the first chunk can play before the
    whole utterance is synthesised — NFR1.1 measures time to *first* audio, not
    time to complete audio.
    """

    name: str

    async def synthesize(
        self,
        tenant: TenantContext,
        utterance: Utterance,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield audio chunks for an utterance."""
        ...


class AudioSink(Protocol):
    """Where agent audio goes."""

    async def write(self, chunk: bytes) -> None: ...
    async def close(self) -> None: ...


@runtime_checkable
class TelephonyProvider(Protocol):
    """The call leg.

    Constraint C-T2: the provider must support bidirectional media streaming
    over a WebSocket. A provider that only does classic IVR or TwiML cannot host
    a live agent, which rules out several established Indian CPaaS vendors.
    """

    name: str

    async def stream(
        self,
        tenant: TenantContext,
        call_id: str,
    ) -> tuple[AsyncIterator[bytes], AudioSink]:
        """Return the inbound audio stream and the outbound sink for a call."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderSet:
    """The four providers serving one region."""

    stt: STTProvider
    llm: LLMProvider
    tts: TTSProvider
    telephony: TelephonyProvider

    def describe(self) -> dict[str, str]:
        """Names only — safe to log, and useful for proving which chain ran."""
        return {
            "stt": self.stt.name,
            "llm": self.llm.name,
            "tts": self.tts.name,
            "telephony": self.telephony.name,
        }


class UnregisteredRegionError(RuntimeError):
    """Raised when a tenant's region has no provider set configured.

    Failing loudly matters more than it looks: silently falling back to another
    region's providers would route a tenant's audio to vendors that may have no
    BAA and no data-residency guarantee for that tenant.
    """


@dataclass
class ProviderRegistry:
    """Selects providers by region.

    Region selection goes through this registry rather than inline conditionals,
    so there is exactly one place where the vendor-per-region decision is made
    and exactly one place to audit.
    """

    _sets: dict[Region, ProviderSet] = field(default_factory=dict)

    def register(self, region: Region, providers: ProviderSet) -> None:
        self._sets[region] = providers

    def for_tenant(self, tenant: TenantContext) -> ProviderSet:
        """Return the provider set for a tenant's region.

        Raises rather than falling back. See :class:`UnregisteredRegionError`.
        """
        try:
            return self._sets[tenant.region]
        except KeyError:
            raise UnregisteredRegionError(
                f"no providers registered for region {tenant.region.value!r}; "
                f"registered: {sorted(r.value for r in self._sets)}"
            ) from None

    @property
    def regions(self) -> list[Region]:
        return sorted(self._sets, key=lambda r: r.value)


__all__ = [
    "PHI",
    "AudioSink",
    "LLMProvider",
    "ProviderRegistry",
    "ProviderSet",
    "STTProvider",
    "TTSProvider",
    "TelephonyProvider",
    "UnregisteredRegionError",
]
