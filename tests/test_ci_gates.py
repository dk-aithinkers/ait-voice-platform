"""The CI gates themselves.

A gate that passes because it is broken is worse than no gate: it reports
green while checking nothing. These tests exist for the same reason `team.md`
requires an excluded module to carry a replacement test — an unverified control
is a decorative one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COVERAGE_GATE = REPO / "scripts" / "check_coverage.py"
BAA_GATE = REPO / "scripts" / "check_baa.py"


def run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


class TestCoverageGate:
    @staticmethod
    def _report(tmp_path: Path, files: dict[str, dict[str, int]]) -> Path:
        report = tmp_path / "coverage.json"
        report.write_text(
            json.dumps({"files": {name: {"summary": s} for name, s in files.items()}})
        )
        return report

    def test_it_fails_a_package_below_its_floor(self, tmp_path: Path) -> None:
        """The gate has to actually fail, or it is a green light with extra steps."""
        report = self._report(
            tmp_path,
            {
                "src/ait_voice/core/consent.py": {
                    "covered_branches": 1,
                    "num_branches": 10,
                    "covered_lines": 10,
                    "num_statements": 10,
                }
            },
        )
        result = run(COVERAGE_GATE, "--report", str(report), cwd=REPO)

        assert result.returncode == 1
        assert "below the" in result.stdout
        assert "consent.py" in result.stdout

    def test_it_passes_a_package_above_its_floor(self, tmp_path: Path) -> None:
        report = self._report(
            tmp_path,
            {
                "src/ait_voice/core/consent.py": {
                    "covered_branches": 10,
                    "num_branches": 10,
                    "covered_lines": 10,
                    "num_statements": 10,
                }
            },
        )
        assert run(COVERAGE_GATE, "--report", str(report), cwd=REPO).returncode == 0

    def test_high_line_coverage_does_not_rescue_low_branch_coverage(self, tmp_path: Path) -> None:
        """The exact gap this gate exists for, and the one it found on its
        first real run: audit.py at 89% line and 73.5% branch."""
        report = self._report(
            tmp_path,
            {
                "src/ait_voice/core/audit.py": {
                    "covered_branches": 5,
                    "num_branches": 10,  # 50% branch
                    "covered_lines": 100,
                    "num_statements": 100,  # 100% line
                }
            },
        )
        result = run(COVERAGE_GATE, "--report", str(report), cwd=REPO)

        assert result.returncode == 1
        assert "branch" in result.stdout

    def test_a_missing_report_is_an_error_not_a_pass(self, tmp_path: Path) -> None:
        """Silently passing when the report is absent is how a gate stops
        checking without anyone noticing."""
        result = run(COVERAGE_GATE, "--report", str(tmp_path / "nope.json"), cwd=REPO)
        assert result.returncode == 2

    def test_it_gates_the_compliance_core_on_branch_coverage(self) -> None:
        """Line coverage reaches a branch without taking it; 100% line coverage
        of an untaken `if` proves nothing about the rule it encodes."""
        source = COVERAGE_GATE.read_text()

        for module in ("audit.py", "consent.py", "tenancy.py", "handoff.py"):
            line = next(line for line in source.splitlines() if module in line and "core/" in line)
            assert '"branch"' in line, f"{module} must gate on branch coverage"

    def test_every_exclusion_names_a_replacement_test(self) -> None:
        """`team.md`: an exclusion with no replacement obligation is how a
        coverage gate becomes decorative."""
        from scripts.check_coverage import EXCLUSIONS

        assert EXCLUSIONS, "the exclusion list should be explicit, even if empty"
        for excluded, replacement in EXCLUSIONS.items():
            assert (REPO / excluded).exists(), f"{excluded} no longer exists"
            assert (REPO / replacement).exists(), (
                f"{excluded} is excluded but its replacement test {replacement} is missing"
            )

    # Deliberately no "the gate passes on this repository" test.
    #
    # `coverage.json` is written when pytest finishes, so a test reading it
    # mid-run sees the *previous* run's numbers. That test can fail without a
    # regression (stale file) and pass while coverage is genuinely broken (stale
    # file from a good run) — it reports on the wrong thing in both directions.
    # CI runs the gate as its own step after pytest, which is correctly ordered
    # and is the check that actually counts.

    def test_a_package_with_no_branches_is_not_a_division_by_zero(self) -> None:
        from scripts.check_coverage import percent

        assert percent(0, 0) == 100.0
        assert percent(1, 2) == 50.0


class TestBAAGate:
    def test_the_register_is_well_formed_today(self) -> None:
        assert run(BAA_GATE, cwd=REPO).returncode == 0

    def test_production_mode_blocks_while_baas_are_unsigned(self) -> None:
        """Expected to fail until D-05 completes. That failure is the control
        working: it is what stops US patient data reaching a vendor with no
        agreement."""
        result = run(BAA_GATE, "--require-signed", cwd=REPO)

        assert result.returncode == 1
        assert "PRODUCTION DEPLOY BLOCKED" in result.stdout
        assert "C-R1" in result.stdout

    def test_every_phi_path_vendor_is_in_the_register(self) -> None:
        import tomllib

        from scripts.check_baa import PHI_PATH_VENDORS

        vendors = tomllib.loads((REPO / "compliance" / "baa-register.toml").read_text())["vendor"]

        for vendor in PHI_PATH_VENDORS:
            assert vendor in vendors, f"{vendor} touches PHI but is not registered"

    def test_the_gate_catches_a_flag_flipped_without_evidence(self, tmp_path: Path) -> None:
        """The failure mode worth catching: someone sets `baa = true` to unblock
        a deploy and records nothing about what was signed."""
        import tomllib

        from scripts.check_baa import PHI_PATH_VENDORS

        register = tomllib.loads((REPO / "compliance" / "baa-register.toml").read_text())["vendor"]
        # Every currently-signed vendor must name its agreement.
        for name, entry in register.items():
            if entry.get("baa"):
                assert entry.get("agreement", "").strip(), (
                    f"{name} is marked signed but names no agreement"
                )
        assert PHI_PATH_VENDORS


class TestThePHIPathListMatchesTheCode:
    """`PHI_PATH_VENDORS` is hand-maintained, and that is how AWS went missing.

    The gate reports on a hardcoded tuple. Nothing connected it to the providers
    `config.py` can actually select, so a vendor added to the wiring would be
    processing US patient data with the gate still printing a clean bill. That
    is the same shape as every other defect this file exists to catch: a check
    that passes because it is incomplete.

    So the tuple is cross-checked against the code rather than trusted.
    """

    def _us_vendors(self, monkeypatch) -> set[str]:
        """Every vendor `config.py` selects for a US tenant with all keys set."""
        from ait_voice.config import build_registry
        from ait_voice.core.types import Region

        for var in (
            "ANTHROPIC_API_KEY",
            "DEEPGRAM_API_KEY",
            "ELEVENLABS_API_KEY",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_PHONE_NUMBER",
        ):
            monkeypatch.setenv(var, "test-value-not-a-real-credential")

        _, statuses = build_registry(regions=[Region.US], baa_register={})
        return {s.provider for s in statuses if s.real}

    def test_every_selectable_us_vendor_is_gated(self, monkeypatch) -> None:
        from scripts.check_baa import PHI_PATH_VENDORS

        ungated = self._us_vendors(monkeypatch) - set(PHI_PATH_VENDORS)

        assert not ungated, (
            f"config.py can route US patient data through {sorted(ungated)}, "
            "which check_baa.py does not gate. Add them to PHI_PATH_VENDORS "
            "and to compliance/baa-register.toml."
        )

    def test_every_gated_vendor_is_declared_in_the_register(self) -> None:
        """The gate already enforces this at runtime; pinning it keeps the two files honest."""
        import tomllib

        from scripts.check_baa import PHI_PATH_VENDORS, REGISTER

        declared = set(tomllib.loads(REGISTER.read_text()).get("vendor", {}))

        assert set(PHI_PATH_VENDORS) <= declared

    def test_aws_is_gated_even_though_no_provider_selects_it(self) -> None:
        """The instance that prompted all of the above.

        RDS holds transcripts and intake. C-R1 does not distinguish between a
        vendor that transcribes PHI and one that stores it, and infrastructure
        is invisible to the provider wiring — so nothing but this test will
        notice if it is dropped.
        """
        from scripts.check_baa import PHI_PATH_VENDORS

        assert "aws" in PHI_PATH_VENDORS
