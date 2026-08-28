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

    def test_india_region_selects_that_chain(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--region", "india", "--log-level", "WARNING"]) == 0
        assert "(india)" in capsys.readouterr().out

    def test_turn_limit_is_respected(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--turns", "1", "--log-level", "WARNING"]) == 0
        assert "turns       1" in capsys.readouterr().out

    def test_invalid_region_is_rejected(self) -> None:
        with pytest.raises(SystemExit):
            main(["--region", "atlantis"])


class TestReport:
    def test_report_handles_a_call_with_no_turns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ait_voice.cli import _report

        _report(CallResult(call_id="c", tenant_id="t", region="us"))
        assert "no turns measured" in capsys.readouterr().out

    def test_report_flags_a_turn_over_target(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from ait_voice.cli import _report

        result = CallResult(call_id="c", tenant_id="t", region="us", turns=1)
        result.timings = [TurnTiming(stt_ms=900, llm_ms=900, tts_first_audio_ms=900)]
        _report(result)

        out = capsys.readouterr().out
        assert "OVER" in out
        assert "MISSES" in out

    def test_report_shows_escalation_reason(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
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
