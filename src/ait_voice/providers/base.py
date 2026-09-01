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
class WebSocketLike(Protocol):
    """The slice of a WebSocket the telephony adapters use.

    Narrow on purpose: it keeps the transports testable without a live carrier,
    and keeps a vendor's socket type out of our signatures per the quarantine
    convention. Both the Twilio media-stream adapter and ConversationRelay
    speak exactly this much.
    """

    async def send(self, message: str) -> None: ...

    def __aiter__(self) -> AsyncIterator[str]: ...


@runtime_checkable
class STTProvider(Protocol):
    """Speech to text.

    Implementations stream audio in and yield utterances as they are recognised.
    Interim results carry ``is_final=False``; the pipeline uses the final one for
    the dialog turn and the interim ones for barge-in detection.
    """

    name: str

    def transcribe(
        self,
        tenant: TenantContext,
        audio: AsyncIterator[bytes],
        *,
        language: str | None = None,
    ) -> AsyncIterator[Utterance]:
        """Yield utterances recognised from an audio stream.

        Declared ``def`` rather than ``async def`` deliberately. An
        ``async def`` whose body is ``...`` is a *coroutine* returning an
        iterator — callers would have to ``await`` it first. Every
        implementation here uses ``yield``, which makes it an async generator
        that callers iterate directly, and that is what the pipeline does.
        Declaring it ``async def`` made this protocol describe a contract no
        implementation honoured, and ``@runtime_checkable`` hid it by checking
        only that the method name exists.
        """
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

    def synthesize(
        self,
        tenant: TenantContext,
        utterance: Utterance,
        *,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield audio chunks for an utterance.

        ``def``, not ``async def`` — see :meth:`STTProvider.transcribe`.
        """
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
class SpeechTiming:
    """How long it took to say something, and whether we could actually tell.

    The distinction is why this is a type rather than a float. NFR1.1 measures
    to the first *audio* of the reply. On a cascaded chain we synthesise
    ourselves and observe that moment directly. On a bundled transport we hand
    text to the carrier and it synthesises downstream, so the only thing we can
    time is the handoff — the audio happens after our last measurement point.

    Reporting both as one number would make a bundled transport look faster
    than a cascaded one purely by measuring less of the same journey.
    ``observed_audio`` keeps that comparison honest.
    """

    elapsed_ms: float
    observed_audio: bool = True


@runtime_checkable
class DialogSession(Protocol):
    """One call's two-way conversation, however it is carried.

    This is the seam that lets a bundled vendor and a three-vendor cascade sit
    under the same dialog policy. Everything above it — the disclosure,
    escalation, turn limits, timing — stays identical either way, which matters
    most for escalation: it is safety-critical, and a second copy of it is a
    second thing to get wrong.
    """

    def listen(self) -> AsyncIterator[Utterance]:
        """Yield the caller's final utterances, as text."""
        ...

    async def speak(self, utterance: Utterance) -> SpeechTiming:
        """Say something to the caller."""
        ...

    async def close(self) -> None:
        """End the call leg."""
        ...


@runtime_checkable
class DialogTransport(Protocol):
    """Opens a :class:`DialogSession` for a call.

    Two shapes implement this. A cascaded transport composes separate STT, TTS
    and telephony vendors, keeping each independently BAA-able and swappable
    per C-T1. A bundled transport — Twilio ConversationRelay is the first —
    collapses all three into one vendor that returns text rather than audio.

    A bundle trades C-T1 replaceability for a large amount of deleted code.
    That trade is a per-region deployment decision rather than an architectural
    one, which is exactly why it belongs behind this protocol.
    """

    name: str
    #: Whether this transport can observe time to first audio. See SpeechTiming.
    observes_audio: bool

    async def open(self, tenant: TenantContext, call_id: str) -> DialogSession:
        """Begin a call leg."""
        ...


@dataclass(frozen=True, slots=True)
class ProviderSet:
    """The providers serving one region.

    ``dialog`` is the escape hatch for a bundled vendor. When it is set the
    speech legs are unused: a bundle owns recognition, synthesis and the
    carrier together, and pretending otherwise by routing dummy audio through
    the cascaded protocols would make this boundary decorative.
    """

    stt: STTProvider
    llm: LLMProvider
    tts: TTSProvider
    telephony: TelephonyProvider
    dialog: DialogTransport | None = None

    @property
    def is_bundled(self) -> bool:
        return self.dialog is not None

    def describe(self) -> dict[str, str]:
        """Names only — safe to log, and useful for proving which chain ran."""
        if self.dialog is not None:
            # Naming the unused legs here would be a lie in the one record that
            # exists to prove which vendors actually touched the call.
            return {"dialog": self.dialog.name, "llm": self.llm.name}
        return {
            "stt": self.stt.name,
            "llm": self.llm.name,
            "tts": self.tts.name,
            "telephony": self.telephony.name,
        }


class BAANotConfirmedError(RuntimeError):
    """Raised when a vendor would receive PHI without an executed BAA.

    Lives here rather than in a vendor module because every leg raises it and
    no leg owns it. C-R1 is the rule it enforces: a BAA does not flow down to
    subcontractors, so each vendor in the chain needs its own, and a vendor
    without one must not receive call audio, transcripts, or caller identity.
    """


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
    "DialogSession",
    "DialogTransport",
    "LLMProvider",
    "ProviderRegistry",
    "SpeechTiming",
    "WebSocketLike",
    "ProviderSet",
    "STTProvider",
    "TTSProvider",
    "TelephonyProvider",
    "UnregisteredRegionError",
]
