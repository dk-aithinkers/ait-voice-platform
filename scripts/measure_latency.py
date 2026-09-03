#!/usr/bin/env python3
"""Measure turn latency against NFR1.1, over a sample big enough to mean something.

    AC-NFR1.1
    Given a representative sample of at least 100 conversational turns
    When latency is measured from end-of-caller-speech to first agent audio
    Then the 95th percentile is below 1500ms

`ait-voice --live` reports p95 for one call, and a call is five to ten turns —
a p95 over eight samples is the second-slowest turn, which is not a percentile
in any useful sense. This runs calls until the sample is large enough, pools
every turn, and reports the distribution plus a per-leg breakdown, because
"we miss the target" is not actionable and "TTS first-audio is 700ms at p95" is.

    uv run python scripts/measure_latency.py --dry-run          # offline, proves the harness
    uv run python scripts/measure_latency.py --live             # real vendors, real money
    uv run python scripts/measure_latency.py --live --turns 200
    uv run python scripts/measure_latency.py --live --out evidence/bolt-1-live-call.md

**It will not issue a verdict from offline providers.** The offline set returns
canned audio with no network in the path, so it reports single-digit
milliseconds and would "MEET" the target every time. A record saying NFR1.1
passes, produced by a run that never contacted a vendor, is worse than no
record — so `--dry-run` is labelled throughout and `--out` refuses to write.

`--out` writes the evidence `team.md` has required since practices discovery:

    A Bolt whose acceptance criterion is a manual action rather than a test
    (Bolt 1's live call being the clearest case) records that evidence
    explicitly: the call's date, the path exercised, the observed turn latency,
    and the outcome.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypedDict

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from ait_voice.config import build_registry, load_baa_register, load_dotenv_if_present  # noqa: E402
from ait_voice.core.pipeline import VoicePipeline  # noqa: E402
from ait_voice.core.types import Region, TenantContext  # noqa: E402
from ait_voice.providers.base import ProviderRegistry  # noqa: E402
from ait_voice.providers.offline import offline_provider_set  # noqa: E402
from ait_voice.providers.reachability import verify_all  # noqa: E402

TARGET_MS = 1500.0

#: Turns a caller actually takes. Deliberately mundane — a latency sample drawn
#: only from short answers flatters the model, and one drawn only from long ones
#: does the opposite.
SCRIPT = [
    "Hi, I'd like to book an appointment.",
    "Tuesday morning if you have it.",
    "Ten thirty works.",
    "Actually, could we make it the afternoon instead?",
    "Two o'clock is fine.",
    "My name is Alex Reyes.",
    "Fourth of March, nineteen eighty-five.",
    "That's everything, thanks.",
]


#: What a run was: how many calls it took, which vendor served each leg, and
#: which legs never went live. The last one is why this is a type rather than a
#: bare dict — a partial run must not be reported as a full one.
class Meta(TypedDict):
    calls: int
    providers: dict[str, str]
    offline_legs: list[str]


@dataclass
class Sample:
    stt_ms: float
    llm_ms: float
    tts_ms: float
    total_ms: float


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(len(ordered) * pct / 100.0), len(ordered) - 1)
    return ordered[index]


def _describe(name: str, values: list[float]) -> str:
    return (
        f"  {name:<22} {statistics.mean(values):>8.0f} {percentile(values, 50):>8.0f} "
        f"{percentile(values, 95):>8.0f} {percentile(values, 99):>8.0f} {max(values):>8.0f}"
    )


async def collect(*, region: Region, want_turns: int, live: bool) -> tuple[list[Sample], Meta]:
    """Run calls until `want_turns` turns are pooled. Returns samples and metadata."""
    if live:
        load_dotenv_if_present()
        registry, statuses = build_registry(regions=[region], baa_register=load_baa_register())
        real = [s for s in statuses if s.real]
        if not real:
            raise SystemExit(
                "Nothing is wired for a live run. `ait-voice --doctor --verify` will\n"
                "say which credentials are missing or rejected."
            )
        providers = {s.leg: s.provider for s in statuses}
        offline_legs = [s.leg for s in statuses if not s.real]

        # Pre-flight the credentials. Without this a rejected key surfaces as
        # "dependency failure / could not speak apology / no measured turns",
        # which describes what the pipeline did rather than why — and the why
        # is a 401 the vendor answered in the first hundred milliseconds.
        rejected = [
            r for r in await verify_all() if not r.reachable and r.provider in providers.values()
        ]
        if rejected:
            lines = "\n".join(f"    {r.provider:<14} {r.verdict:<16} {r.detail}" for r in rejected)
            raise SystemExit(
                "Credentials will not authenticate, so a live run would measure\n"
                "nothing but error paths:\n\n"
                f"{lines}\n\n"
                "Fix them in .env, confirm with `ait-voice --doctor --verify`,\n"
                "then re-run."
            )
    else:
        registry = ProviderRegistry()
        registry.register(region, offline_provider_set(script=SCRIPT))
        providers = {"all": "offline"}
        offline_legs = ["llm", "stt", "tts", "telephony"]

    tenant = TenantContext(tenant_id="latency-probe", region=region)
    pipeline = VoicePipeline(registry, clinic_name="Northside Medical")

    samples: list[Sample] = []
    calls = 0
    while len(samples) < want_turns:
        calls += 1
        result = await pipeline.handle_call(
            tenant, call_id=f"probe-{calls:04d}", max_turns=len(SCRIPT)
        )
        if not result.latency_observable:
            raise SystemExit(
                "This transport synthesises downstream, so the reply latency stops\n"
                "short of the audio the caller hears. Measure the cascaded chain\n"
                "instead, or read the carrier's own analytics."
            )
        for t in result.timings:
            samples.append(Sample(t.stt_ms, t.llm_ms, t.tts_first_audio_ms, t.total_ms))
        if not result.timings:
            raise SystemExit("The call produced no measured turns; nothing to report.")
        if calls > want_turns:  # pragma: no cover - guards a pathological loop
            break

    return samples, {"calls": calls, "providers": providers, "offline_legs": offline_legs}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="call real vendors (costs money)")
    parser.add_argument("--dry-run", action="store_true", help="offline providers; no verdict")
    parser.add_argument("--region", choices=["us", "india"], default="india")
    parser.add_argument("--turns", type=int, default=100, help="minimum turns to pool")
    parser.add_argument("--out", type=pathlib.Path, help="write the acceptance record here")
    args = parser.parse_args(argv)

    if args.live == args.dry_run:
        parser.error("pass exactly one of --live or --dry-run")
    if args.out and not args.live:
        parser.error(
            "--out refuses a dry run: an acceptance record from offline providers "
            "would certify a target that was never actually tested"
        )

    region = Region(args.region)
    samples, meta = asyncio.run(collect(region=region, want_turns=args.turns, live=args.live))

    totals = [s.total_ms for s in samples]
    p95 = percentile(totals, 95)
    meets = p95 < TARGET_MS

    print()
    print(f"  mode        {'LIVE — real vendors' if args.live else 'DRY RUN — offline providers'}")
    print(f"  region      {region}")
    print(f"  providers   {', '.join(f'{k}={v}' for k, v in meta['providers'].items())}")
    print(f"  calls       {meta['calls']}")
    print(f"  turns       {len(samples)}")
    print()
    print(f"  {'leg':<22} {'mean':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'max':>8}")
    print("  " + "-" * 68)
    print(_describe("stt", [s.stt_ms for s in samples]))
    print(_describe("llm", [s.llm_ms for s in samples]))
    print(_describe("tts first audio", [s.tts_ms for s in samples]))
    print("  " + "-" * 68)
    print(_describe("TOTAL", totals))
    print()

    if not args.live:
        print("  NO VERDICT. Offline providers return canned audio with no network in")
        print("  the path, so these numbers describe the harness, not the product.")
        print("  Re-run with --live once credentials authenticate.")
        print()
        return 0

    if meta["offline_legs"]:
        print(f"  PARTIAL: {', '.join(meta['offline_legs'])} still offline — the total")
        print("  excludes those legs and is a floor, not the figure NFR1.1 asks for.")
        print()

    verdict = "MEETS" if meets else "MISSES"
    print(f"  p95 {p95:.0f}ms — {verdict} the NFR1.1 target of {TARGET_MS:.0f}ms")
    if len(samples) < 100:
        print(f"  NOTE: {len(samples)} turns is below the 100 AC-NFR1.1 asks for.")
    print()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(_record(samples, meta, region, p95, meets))
        print(f"  acceptance record written to {args.out.relative_to(REPO)}\n")

    return 0 if meets else 1


def _row(label: str, values: list[float]) -> str:
    return (
        f"| {label} | {statistics.mean(values):.0f} | {percentile(values, 50):.0f} "
        f"| {percentile(values, 95):.0f} | {percentile(values, 99):.0f} "
        f"| {max(values):.0f} |"
    )


def _record(samples: list[Sample], meta: Meta, region: Region, p95: float, meets: bool) -> str:
    totals = [s.total_ms for s in samples]
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    path = ", ".join(f"{k}={v}" for k, v in meta["providers"].items())
    short = " — BELOW the 100 AC-NFR1.1 requires" if len(samples) < 100 else ""
    partial = (
        "- **Legs still offline**: "
        + ", ".join(meta["offline_legs"])
        + " (the total is a floor, not the full chain)\n"
        if meta["offline_legs"]
        else ""
    )
    rows = "\n".join(
        [
            _row("stt", [s.stt_ms for s in samples]),
            _row("llm", [s.llm_ms for s in samples]),
            _row("tts first audio", [s.tts_ms for s in samples]),
            _row("**total**", totals),
        ]
    )
    return f"""# Bolt 1 — live call acceptance record

`team.md` requires this for a Bolt whose acceptance is a manual action rather
than a test: the call's date, the path exercised, the observed turn latency,
and the outcome.

- **Date**: {when}
- **Region**: {region}
- **Path exercised**: {path}
- **Calls**: {meta["calls"]}
- **Turns pooled**: {len(samples)}{short}
{partial}
## Observed turn latency (ms)

| leg | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
{rows}

## Outcome

**{"MEETS" if meets else "MISSES"} NFR1.1** — p95 {p95:.0f}ms against a 1500ms target.

## What this does not cover

The caller's side is synthesised and played into the real STT rather than
arriving over a phone, so carrier round-trip is excluded. A number and a real
inbound call are needed to close that gap; this figure is the speech chain only.
"""


if __name__ == "__main__":
    raise SystemExit(main())
