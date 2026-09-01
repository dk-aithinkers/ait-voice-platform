"""Assemble a provider registry from whatever credentials are present.

Every leg degrades independently: a missing key means that one provider falls
back to offline while the rest stay real. So you can wire the dialog model
today, speech next week, and telephony when the number is provisioned, testing
the whole chain at every step.

**The BAA register.** Constraint C-R1 requires an executed BAA from every vendor
touching call audio, transcripts or caller identity, and a BAA does not flow
down to subcontractors — one gap breaks the chain. The security review proposed
making this a gate rather than a memory aid, because ``pip install
<vendor-sdk>`` is a compliance event on this system, not a dependency event.

``compliance/baa-register.yaml`` is that gate in its simplest form. A vendor
absent from it, or present with ``baa: false``, will refuse to process a US
tenant's data — the providers raise rather than proceeding. India tenants are
governed by DPDP rather than HIPAA and are not gated by this file; that is a
separate obligation, not a lesser one.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ait_voice.core.types import Region
from ait_voice.providers.base import (
    LLMProvider,
    ProviderRegistry,
    ProviderSet,
    STTProvider,
    TelephonyProvider,
    TTSProvider,
)
from ait_voice.providers.offline import (
    OfflineLLM,
    OfflineSTT,
    OfflineTelephony,
    OfflineTTS,
)

BAA_REGISTER = Path("compliance/baa-register.toml")


@dataclass(frozen=True, slots=True)
class LegStatus:
    """Whether one provider leg is real or offline, and why."""

    leg: str
    provider: str
    real: bool
    reason: str


def load_baa_register(path: Path | None = None) -> dict[str, bool]:
    """Return ``{vendor: baa_executed}``.

    A missing register is treated as no BAAs confirmed rather than as an error,
    so the safe path is also the default path. Absence of evidence is not
    evidence of a signed agreement.
    """
    target = path or BAA_REGISTER
    if not target.exists():
        return {}
    with target.open("rb") as fh:
        data = tomllib.load(fh)
    return {name: bool(entry.get("baa", False)) for name, entry in data.get("vendor", {}).items()}


def build_registry(
    *,
    regions: list[Region] | None = None,
    baa_register: dict[str, bool] | None = None,
    bundled_regions: list[Region] | None = None,
) -> tuple[ProviderRegistry, list[LegStatus]]:
    """Build a registry, and report which legs are real.

    Returns the registry plus a status list, so the caller can show what is
    actually wired rather than leaving it to be discovered mid-call.

    Args:
        bundled_regions: Regions served by Twilio ConversationRelay instead of
            the cascaded chain. Opt-in per region by design: a bundle trades
            C-T1 replaceability for deleted code, and that trade is worth
            making in one market and not the other.
    """
    baa = baa_register if baa_register is not None else load_baa_register()
    bundled = set(bundled_regions or [])
    registry = ProviderRegistry()
    statuses: list[LegStatus] = []

    for region in regions or [Region.US]:
        providers, region_statuses = _build_set(region, baa)
        if region in bundled:
            providers, region_statuses = _bundle(providers, region, baa)
        registry.register(region, providers)
        statuses.extend(region_statuses)

    return registry, statuses


def _bundle(
    providers: ProviderSet, region: Region, baa: dict[str, bool]
) -> tuple[ProviderSet, list[LegStatus]]:
    """Replace the speech legs with ConversationRelay, keeping our own LLM.

    The dialog stays ours in either shape. ConversationRelay bundles
    recognition, synthesis and the carrier; it does not take the LLM, which is
    why the escalation policy and system prompt are unaffected by this choice.
    """
    from ait_voice.providers.conversation_relay import ConversationRelayTransport

    relay = ConversationRelayTransport(baa_confirmed=baa.get("twilio", False))
    bundled = ProviderSet(
        stt=providers.stt,
        llm=providers.llm,
        tts=providers.tts,
        telephony=providers.telephony,
        dialog=relay,
    )
    llm_status = next((s for s in _build_set(region, baa)[1] if s.leg == "llm"), None)
    statuses = [
        LegStatus("dialog", relay.name, True, _baa_note("twilio", region, baa)),
    ]
    if llm_status:
        statuses.append(llm_status)
    return bundled, statuses


def _build_set(region: Region, baa: dict[str, bool]) -> tuple[ProviderSet, list[LegStatus]]:
    statuses: list[LegStatus] = []

    llm, status = _build_llm(region, baa)
    statuses.append(status)
    stt, status = _build_stt(region, baa)
    statuses.append(status)
    tts, status = _build_tts(region, baa)
    statuses.append(status)
    telephony, status = _build_telephony(region, baa)
    statuses.append(status)

    return ProviderSet(stt=stt, llm=llm, tts=tts, telephony=telephony), statuses


def _build_llm(region: Region, baa: dict[str, bool]) -> tuple[LLMProvider, LegStatus]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return OfflineLLM(), LegStatus("llm", "offline-llm", False, "ANTHROPIC_API_KEY not set")

    from ait_voice.providers.anthropic_llm import AnthropicLLM

    return AnthropicLLM(baa_confirmed=baa.get("anthropic", False)), LegStatus(
        "llm", "anthropic", True, _baa_note("anthropic", region, baa)
    )


def _build_stt(region: Region, baa: dict[str, bool]) -> tuple[STTProvider, LegStatus]:
    if not os.environ.get("DEEPGRAM_API_KEY"):
        return OfflineSTT(), LegStatus("stt", "offline-stt", False, "DEEPGRAM_API_KEY not set")

    from ait_voice.providers.deepgram_stt import DeepgramSTT

    return DeepgramSTT(baa_confirmed=baa.get("deepgram", False)), LegStatus(
        "stt", "deepgram", True, _baa_note("deepgram", region, baa)
    )


def _build_tts(region: Region, baa: dict[str, bool]) -> tuple[TTSProvider, LegStatus]:
    if not os.environ.get("ELEVENLABS_API_KEY"):
        return OfflineTTS(), LegStatus("tts", "offline-tts", False, "ELEVENLABS_API_KEY not set")

    from ait_voice.providers.elevenlabs_tts import ElevenLabsTTS

    return ElevenLabsTTS(baa_confirmed=baa.get("elevenlabs", False)), LegStatus(
        "tts", "elevenlabs", True, _baa_note("elevenlabs", region, baa)
    )


def _build_telephony(region: Region, baa: dict[str, bool]) -> tuple[TelephonyProvider, LegStatus]:
    # Both halves, not just the SID. Twilio authenticates with the pair, so a
    # SID alone produces a leg that reports LIVE and then fails at the vendor —
    # which is the same misleading shape the doctor's LIVE column had.
    missing = [
        var for var in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN") if not os.environ.get(var)
    ]
    if missing:
        return OfflineTelephony(), LegStatus(
            "telephony", "offline-telephony", False, f"{' and '.join(missing)} not set"
        )

    from ait_voice.providers.twilio_telephony import TwilioTelephony

    return TwilioTelephony(baa_confirmed=baa.get("twilio", False)), LegStatus(
        "telephony", "twilio", True, _baa_note("twilio", region, baa)
    )


def _baa_note(vendor: str, region: Region, baa: dict[str, bool]) -> str:
    if region is not Region.US:
        return "DPDP jurisdiction — BAA gate does not apply"
    if baa.get(vendor):
        return "BAA confirmed"
    return "BAA NOT confirmed — will refuse US tenant data"


def load_dotenv_if_present(path: str = ".env") -> bool:
    """Load a local ``.env`` if one exists. Returns whether it did."""
    target = Path(path)
    if not target.exists():
        return False
    from dotenv import load_dotenv

    load_dotenv(target)
    return True
