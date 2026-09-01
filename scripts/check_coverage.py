#!/usr/bin/env python3
"""Per-package coverage gate.

`team.md`, affirmed at practices-discovery:

    Coverage shape: measured and gated **per package**, not as one
    repository-wide number, so the compliance core cannot hide behind a
    well-covered booking layer's average.

`pytest --cov-fail-under` gates the repository total, which is exactly the
number that rule rejects: a compliance module at 40% passes comfortably if the
UI adapters are at 98%. So this reads `coverage.json` and applies a floor per
package.

The compliance core gates on **branch** coverage rather than line, because
every Hard regulatory constraint here is a branch — BAA gating, jurisdiction
routing, consent expiry. Line coverage reaches those branches without ever
taking them, and 100% line coverage of an untaken `if` proves nothing about the
rule it encodes.

Exclusions carry a replacement obligation. `team.md` permits excluding vendor
transport adapters from the denominator "by an explicit, named list", but only
where a contract or recorded-fixture test stands in — "an exclusion with no
replacement obligation is how a coverage gate becomes decorative". So the list
below names both the exclusion and the test that covers for it, and this script
fails if a named replacement test has gone missing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Floors per package prefix, most specific first.
#: `branch` gates branch coverage; `line` gates line coverage.
FLOORS: tuple[tuple[str, str, int], ...] = (
    # The compliance core — C-R1, C-R2, C-R7, C-R8, C-R9 live here.
    ("src/ait_voice/core/audit.py", "branch", 85),
    ("src/ait_voice/core/consent.py", "branch", 90),
    ("src/ait_voice/core/tenancy.py", "branch", 90),
    ("src/ait_voice/core/handoff.py", "branch", 90),
    ("src/ait_voice/core/intake.py", "branch", 90),
    ("src/ait_voice/core/scheduling.py", "branch", 90),
    # The HTTP tenant boundary is a compliance surface too.
    ("src/ait_voice/api/auth.py", "branch", 85),
    ("src/ait_voice/api/", "line", 85),
    ("src/ait_voice/core/", "line", 85),
    ("src/ait_voice/providers/", "line", 80),
    ("src/ait_voice/", "line", 80),
)

#: Vendor transport excluded from the floor, and the test that stands in for it.
#: Both halves are required; the second is what keeps the first honest.
EXCLUSIONS: dict[str, str] = {
    "src/ait_voice/providers/twilio_telephony.py": "tests/test_provider_contracts.py",
    "src/ait_voice/providers/deepgram_stt.py": "tests/test_deepgram_contract.py",
}


def floor_for(path: str) -> tuple[str, int] | None:
    for prefix, kind, minimum in FLOORS:
        if path.startswith(prefix):
            return kind, minimum
    return None


def percent(covered: int, total: int) -> float:
    """A package with nothing to measure is 100%, not a division by zero."""
    return 100.0 if total == 0 else 100.0 * covered / total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Per-package coverage gate.")
    parser.add_argument(
        "--report",
        type=pathlib.Path,
        default=REPO / "coverage.json",
        help="coverage.json to read (default: the repository's own)",
    )
    args = parser.parse_args(argv)

    report = args.report
    if not report.exists():
        print("coverage.json not found — run pytest --cov --cov-report=json")
        return 2

    data = json.loads(report.read_text())
    failures: list[str] = []
    rows: list[tuple[str, str, float, int, str]] = []

    # An exclusion whose replacement test has vanished is a silent hole.
    for excluded, replacement in EXCLUSIONS.items():
        if not (REPO / replacement).exists():
            failures.append(
                f"{excluded} is excluded from the coverage floor, but its "
                f"replacement test {replacement} does not exist"
            )

    for path, entry in sorted(data["files"].items()):
        normalised = path.replace("\\", "/")
        if normalised in EXCLUSIONS:
            rows.append((normalised, "excluded", 0.0, 0, "contract test"))
            continue
        rule = floor_for(normalised)
        if rule is None:
            continue
        kind, minimum = rule
        summary = entry["summary"]

        if kind == "branch":
            value = percent(summary["covered_branches"], summary["num_branches"])
        else:
            value = percent(summary["covered_lines"], summary["num_statements"])

        verdict = "ok" if value >= minimum else "FAIL"
        rows.append((normalised, kind, value, minimum, verdict))
        if verdict == "FAIL":
            failures.append(
                f"{normalised}: {kind} coverage {value:.1f}% is below the {minimum}% floor"
            )

    width = max(len(row[0]) for row in rows) if rows else 40
    print(f"\n  {'package':<{width}}  {'kind':<9} {'cover':>7}  {'floor':>6}  verdict")
    print("  " + "-" * (width + 34))
    for path, kind, value, minimum, verdict in rows:
        if kind == "excluded":
            print(f"  {path:<{width}}  {'excluded':<9} {'—':>7}  {'—':>6}  {verdict}")
        else:
            print(f"  {path:<{width}}  {kind:<9} {value:>6.1f}%  {minimum:>5}%  {verdict}")
    print()

    if failures:
        print("Coverage gate FAILED:\n")
        for failure in failures:
            print(f"  - {failure}")
        print()
        return 1

    print(f"Coverage gate passed: {len(rows)} package(s) at or above their floor.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
