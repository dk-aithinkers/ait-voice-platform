"""The CLI is how a human runs a call, so it gets tested like anything else.

Included because the affirmed coverage floor is per-package rather than global:
an aggregate floor would let this file sit at zero while other packages carried
the average, which is exactly the concentration risk the per-package choice
exists to prevent.
"""

from __future__ import annotations

import pytest

from ait_voice.cli import main
from ait_voice.core.pipeline import CallResult
from ait_voice.core.types import TurnTiming


class TestCLIRuns:
    def test_default_run_succeeds(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--log-level", "WARNING"]) == 0
        out = capsys.readouterr().out
        assert "demo-clinic" in out
        assert "p95" in out

    def test_india_region_selects_that_chain(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--region", "india", "--log-level", "WARNING"]) == 0
        assert "(india)" in capsys.readouterr().out

    def test_turn_limit_is_respected(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--turns", "1", "--log-level", "WARNING"]) == 0
        assert "turns       1" in capsys.readouterr().out

    def test_invalid_region_is_rejected(self) -> None:
        with pytest.raises(SystemExit):
            main(["--region", "atlantis"])


class TestReport:
    def test_report_handles_a_call_with_no_turns(self, capsys: pytest.CaptureFixture[str]) -> None:
        from ait_voice.cli import _report

        _report(CallResult(call_id="c", tenant_id="t", region="us"))
        assert "no turns measured" in capsys.readouterr().out

    def test_report_flags_a_turn_over_target(self, capsys: pytest.CaptureFixture[str]) -> None:
        from ait_voice.cli import _report

        result = CallResult(call_id="c", tenant_id="t", region="us", turns=1)
        result.timings = [TurnTiming(stt_ms=900, llm_ms=900, tts_first_audio_ms=900)]
        _report(result)

        out = capsys.readouterr().out
        assert "OVER" in out
        assert "MISSES" in out

    def test_report_shows_escalation_reason(self, capsys: pytest.CaptureFixture[str]) -> None:
        from ait_voice.cli import _report

        result = CallResult(
            call_id="c",
            tenant_id="t",
            region="us",
            escalated=True,
            escalation_reason="caller_requested_human",
        )
        _report(result)
        assert "caller_requested_human" in capsys.readouterr().out


CREDENTIAL_VARS = (
    "ANTHROPIC_API_KEY",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
)


class TestDoctor:
    @pytest.fixture(autouse=True)
    def _no_ambient_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Decide what is configured here, not from the developer's .env.

        Without this the doctor loads the real .env mid-test and reports
        whatever that machine happens to have wired — so the suite passed on a
        laptop with no keys and failed on one with keys, which is the wrong
        thing for a test to be sensitive to.
        """
        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)
        for var in CREDENTIAL_VARS:
            monkeypatch.delenv(var, raising=False)

    def test_reports_all_offline_without_credentials(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--doctor", "--log-level", "WARNING"]) == 0

        out = capsys.readouterr().out
        assert "offline" in out
        assert "Nothing is wired yet" in out

    def test_warns_when_a_live_leg_lacks_a_baa(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A live vendor with no confirmed BAA is the case worth shouting about."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        assert main(["--doctor", "--log-level", "WARNING"]) == 0

        out = capsys.readouterr().out
        assert "LIVE" in out
        assert "REFUSE US tenant data" in out

    def test_reports_the_baa_register_contents(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        main(["--doctor", "--log-level", "WARNING"])

        assert "BAA register" in capsys.readouterr().out


class TestDoctorVerify:
    def test_verify_reports_a_rejected_key_and_exits_nonzero(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The whole point: 'set' and 'works' are different claims."""
        from ait_voice.providers.reachability import Reachability

        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

        async def fake_verify(providers=None):  # noqa: ANN001, ANN202
            return [Reachability("anthropic", True, False, "HTTP 401 — rejected")]

        monkeypatch.setattr("ait_voice.cli.verify_all", fake_verify)

        assert main(["--doctor", "--verify", "--log-level", "WARNING"]) == 1

        out = capsys.readouterr().out
        assert "FAILED" in out
        assert "not the same as a key that works" in out

    def test_verify_passes_when_every_credential_authenticates(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ait_voice.providers.reachability import Reachability

        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)

        async def fake_verify(providers=None):  # noqa: ANN001, ANN202
            return [Reachability("anthropic", True, True, "credential accepted")]

        monkeypatch.setattr("ait_voice.cli.verify_all", fake_verify)

        assert main(["--doctor", "--verify", "--log-level", "WARNING"]) == 0
        assert "All credentials authenticate." in capsys.readouterr().out

    def test_plain_doctor_says_live_does_not_mean_working(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without this caveat the LIVE column is the thing that misled."""
        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

        assert main(["--doctor", "--log-level", "WARNING"]) == 0

        out = capsys.readouterr().out
        assert "a key is SET, not that it works" in out


class TestLiveRefusal:
    def test_a_baa_refusal_is_reported_as_an_outcome_not_a_traceback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The gate firing is correct behaviour; a stack trace invites a 'fix'."""
        from ait_voice.providers.base import BAANotConfirmedError

        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)

        async def boom(region, turns, script, *, relay=False):  # noqa: ANN001, ANN202
            raise BAANotConfirmedError("no BAA for 'elevenlabs'")

        monkeypatch.setattr("ait_voice.cli._run_live", boom)

        assert main(["--live", "--region", "us", "--log-level", "WARNING"]) == 2

        out = capsys.readouterr().out
        assert "REFUSED — no data left this machine." in out
        assert "BAA gate working" in out


class TestLiveRun:
    """`_run_live` is the path a real call takes; it should not be the untested one."""

    @pytest.fixture
    def _offline_as_if_live(self, monkeypatch: pytest.MonkeyPatch):
        from ait_voice.config import LegStatus
        from ait_voice.providers.base import ProviderRegistry
        from ait_voice.providers.offline import offline_provider_set

        def build(*, regions=None, baa_register=None, bundled_regions=None):  # noqa: ANN001, ANN202
            registry = ProviderRegistry()
            for region in regions or []:
                registry.register(region, offline_provider_set(script=["book me in"]))
            return registry, [LegStatus(leg="llm", provider="fake", real=True, reason="wired")]

        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)
        monkeypatch.setattr("ait_voice.cli.load_baa_register", dict)
        monkeypatch.setattr("ait_voice.cli.build_registry", build)
        return build

    def test_a_live_run_renders_the_caller_then_places_the_call(
        self, _offline_as_if_live, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert (
            main(["--live", "--region", "india", "--say", "book me in", "--log-level", "WARNING"])
            == 0
        )

        out = capsys.readouterr().out
        assert "rendering 1 caller line(s)" in out
        assert "of caller audio; placing the call" in out
        assert "loopback-telephony" in out

    def test_it_stops_when_nothing_is_wired(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Running the live path on offline providers would measure nothing."""
        from ait_voice.providers.base import ProviderRegistry

        monkeypatch.setattr("ait_voice.cli.load_dotenv_if_present", lambda: False)
        monkeypatch.setattr("ait_voice.cli.load_baa_register", dict)
        monkeypatch.setattr(
            "ait_voice.cli.build_registry",
            lambda **kw: (ProviderRegistry(), []),
        )

        with pytest.raises(SystemExit) as exit_info:
            main(["--live", "--region", "india", "--log-level", "WARNING"])

        assert exit_info.value.code == 1
        assert "Nothing is wired" in capsys.readouterr().out

    def test_the_demo_script_is_used_when_no_lines_are_given(
        self, _offline_as_if_live, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ait_voice.cli import DEMO_SCRIPT

        assert main(["--live", "--region", "india", "--log-level", "WARNING"]) == 0
        assert f"rendering {len(DEMO_SCRIPT)} caller line(s)" in capsys.readouterr().out
