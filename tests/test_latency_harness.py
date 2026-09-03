"""The latency harness, and the one thing it must never do.

`scripts/measure_latency.py` produces the evidence that decides whether NFR1.1
holds — and, via `--out`, the Bolt 1 acceptance record `team.md` has required
since practices discovery. A harness that reports a comfortable pass from a run
that never contacted a vendor would be worse than having no measurement, because
the record would carry the authority of a number.

The offline providers make that a live risk rather than a theoretical one: they
simulate plausible per-leg delays and total roughly 850ms, which reads as a
comfortable PASS against the 1500ms target and means nothing at all.
"""

from __future__ import annotations

import pytest
from scripts.measure_latency import TARGET_MS, Sample, main, percentile


class TestItRefusesToCertifyOfflineNumbers:
    def test_out_is_refused_without_live(self, tmp_path) -> None:
        record = tmp_path / "record.md"

        with pytest.raises(SystemExit) as exc:
            main(["--dry-run", "--turns", "8", "--out", str(record)])

        assert exc.value.code == 2  # argparse usage error
        assert not record.exists(), "an acceptance record was written from offline data"

    def test_a_mode_must_be_chosen(self) -> None:
        """Defaulting to either one is wrong: silent-offline certifies nothing,
        silent-live spends money."""
        with pytest.raises(SystemExit):
            main([])

    def test_live_and_dry_run_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            main(["--live", "--dry-run"])

    def test_a_dry_run_reports_no_verdict(self, capsys) -> None:
        main(["--dry-run", "--turns", "8"])

        out = capsys.readouterr().out
        assert "NO VERDICT" in out
        assert "MEETS" not in out, "a dry run must never render a verdict"


class TestThePercentile:
    def test_p95_of_a_known_distribution(self) -> None:
        assert percentile([float(n) for n in range(1, 101)], 95) == 96.0

    def test_an_empty_sample_is_zero_not_a_crash(self) -> None:
        assert percentile([], 95) == 0.0

    def test_a_single_sample_is_its_own_percentile(self) -> None:
        assert percentile([42.0], 95) == 42.0


class TestTheTarget:
    def test_it_matches_nfr1_1(self) -> None:
        """1500ms, from requirements.md. A drift here silently moves the bar."""
        assert TARGET_MS == 1500.0

    def test_a_sample_carries_every_leg(self) -> None:
        """Per-leg breakdown is the actionable part: "we miss" is not, "TTS is
        700ms at p95" is."""
        sample = Sample(stt_ms=1.0, llm_ms=2.0, tts_ms=3.0, total_ms=6.0)

        assert (sample.stt_ms, sample.llm_ms, sample.tts_ms) == (1.0, 2.0, 3.0)
