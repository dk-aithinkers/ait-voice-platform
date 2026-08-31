"""The BAA gate is the enforcement point constraint C-R1 otherwise lacks.

The security review at practices discovery made the point plainly: a Hard
constraint with no build-time check is the weakest form it can take, and
``pip install <vendor-sdk>`` is a compliance event on this system rather than a
dependency event. These tests exercise the gate as a gate — a rule that has
never been shown to refuse anything is a rule nobody should trust.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ait_voice.config import LegStatus, build_registry, load_baa_register
from ait_voice.core.types import PHI, Region, TenantContext, Utterance
from ait_voice.providers.base import BAANotConfirmedError


def _us() -> TenantContext:
    return TenantContext(tenant_id="clinic-us", region=Region.US)


def _india() -> TenantContext:
    return TenantContext(tenant_id="clinic-in", region=Region.INDIA)


class TestBAARegister:
    def test_missing_register_confirms_nothing(self, tmp_path: Path) -> None:
        """Absence of evidence is not evidence of a signed agreement."""
        assert load_baa_register(tmp_path / "nope.toml") == {}

    def test_register_is_parsed(self, tmp_path: Path) -> None:
        target = tmp_path / "baa.toml"
        target.write_text(
            textwrap.dedent(
                """
                [vendor.anthropic]
                baa = true
                [vendor.rumik]
                baa = false
                """
            )
        )
        assert load_baa_register(target) == {"anthropic": True, "rumik": False}

    def test_shipped_register_confirms_no_india_vendor(self) -> None:
        """India-market vendors have no HIPAA posture as a category."""
        register = load_baa_register(Path("compliance/baa-register.toml"))
        assert register.get("rumik") is False
        assert register.get("exotel") is False


class TestBAAGateRefusesUnconfirmedVendors:
    async def test_llm_refuses_us_tenant_without_baa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        from ait_voice.providers.anthropic_llm import AnthropicLLM

        llm = AnthropicLLM(baa_confirmed=False)
        with pytest.raises(BAANotConfirmedError, match="clinic-us"):
            await llm.respond(_us(), [Utterance(text=PHI("hi"))], system_prompt="x")

    async def test_stt_refuses_us_tenant_without_baa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
        from ait_voice.providers.deepgram_stt import DeepgramSTT

        async def audio():
            yield b""

        stt = DeepgramSTT(baa_confirmed=False)
        with pytest.raises(BAANotConfirmedError):
            async for _ in stt.transcribe(_us(), audio()):
                pass

    async def test_tts_refuses_us_tenant_without_baa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """What the agent says can carry PHI too — a name, an appointment."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
        from ait_voice.providers.elevenlabs_tts import ElevenLabsTTS

        tts = ElevenLabsTTS(baa_confirmed=False)
        with pytest.raises(BAANotConfirmedError):
            async for _ in tts.synthesize(_us(), Utterance(text=PHI("hello"))):
                pass

    async def test_telephony_refuses_us_tenant_without_baa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test")
        from ait_voice.providers.twilio_telephony import TwilioTelephony

        with pytest.raises(BAANotConfirmedError):
            await TwilioTelephony(baa_confirmed=False).stream(_us(), "call-1")

    async def test_india_tenant_is_not_gated_by_the_baa_register(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DPDP governs India, not HIPAA. Different obligation, not a lesser one.

        The call fails on the missing stream rather than on the BAA check,
        which is what proves the gate did not fire.
        """
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC-test")
        from ait_voice.providers.twilio_telephony import TwilioTelephony

        with pytest.raises(RuntimeError, match="no connected Twilio stream"):
            await TwilioTelephony(baa_confirmed=False).stream(_india(), "call-1")


class TestRegistryDegradesPerLeg:
    def test_no_credentials_gives_all_offline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for var in (
            "ANTHROPIC_API_KEY",
            "DEEPGRAM_API_KEY",
            "ELEVENLABS_API_KEY",
            "TWILIO_ACCOUNT_SID",
        ):
            monkeypatch.delenv(var, raising=False)

        _, statuses = build_registry(regions=[Region.US], baa_register={})
        assert all(not s.real for s in statuses)
        assert {s.leg for s in statuses} == {"llm", "stt", "tts", "telephony"}

    def test_one_key_wires_one_leg_and_leaves_the_rest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legs degrade independently, so the chain is testable at every step."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        for var in ("DEEPGRAM_API_KEY", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID"):
            monkeypatch.delenv(var, raising=False)

        _, statuses = build_registry(regions=[Region.US], baa_register={})
        by_leg = {s.leg: s for s in statuses}

        assert by_leg["llm"].real
        assert by_leg["llm"].provider == "anthropic"
        assert not by_leg["stt"].real
        assert not by_leg["tts"].real
        assert not by_leg["telephony"].real

    def test_status_warns_when_a_live_leg_lacks_a_baa(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _, statuses = build_registry(regions=[Region.US], baa_register={})
        llm = next(s for s in statuses if s.leg == "llm")
        assert "NOT confirmed" in llm.reason

    def test_confirmed_baa_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _, statuses = build_registry(
            regions=[Region.US], baa_register={"anthropic": True}
        )
        llm = next(s for s in statuses if s.leg == "llm")
        assert llm.reason == "BAA confirmed"

    def test_india_status_notes_the_gate_does_not_apply(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        _, statuses = build_registry(regions=[Region.INDIA], baa_register={})
        llm = next(s for s in statuses if s.leg == "llm")
        assert "DPDP" in llm.reason

    def test_both_regions_get_their_own_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        registry, _ = build_registry(regions=[Region.US, Region.INDIA], baa_register={})
        assert registry.regions == [Region.INDIA, Region.US]


class TestProvidersRefuseWithoutKeys:
    def test_llm_requires_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from ait_voice.providers.anthropic_llm import AnthropicLLM

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            AnthropicLLM()

    def test_stt_requires_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        from ait_voice.providers.deepgram_stt import DeepgramSTT

        with pytest.raises(RuntimeError, match="DEEPGRAM_API_KEY"):
            DeepgramSTT()

    def test_tts_requires_a_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        from ait_voice.providers.elevenlabs_tts import ElevenLabsTTS

        with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
            ElevenLabsTTS()


class TestLegStatus:
    def test_is_a_value_object(self) -> None:
        a = LegStatus("llm", "anthropic", True, "BAA confirmed")
        b = LegStatus("llm", "anthropic", True, "BAA confirmed")
        assert a == b
