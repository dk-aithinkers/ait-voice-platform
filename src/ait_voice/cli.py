"""Run a call through the pipeline and report what it cost.

    uv run ait-voice                      # offline providers, US tenant
    uv run ait-voice --region india
    uv run ait-voice --turns 12
    uv run ait-voice --doctor             # what is wired, and what will refuse
    uv run ait-voice --live --region india    # real vendors, real latency

With no credentials configured this runs the offline provider set, which
exercises the real code path with no network and no PHI leaving the machine.

``--live`` calls the configured vendors for real, and costs real money. The
caller's side is synthesised up front and played into the real STT at telephony
pace, so no phone number is needed — see ``providers/loopback.py`` for what that
does and does not measure.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from ait_voice.config import build_registry, load_baa_register, load_dotenv_if_present
from ait_voice.core.logging import configure_logging
from ait_voice.core.pipeline import CallResult, VoicePipeline
from ait_voice.core.types import Region, TenantContext
from ait_voice.providers.base import BAANotConfirmedError, ProviderRegistry, ProviderSet
from ait_voice.providers.loopback import LoopbackTelephony, render_caller_audio
from ait_voice.providers.offline import offline_provider_set
from ait_voice.providers.reachability import verify_all

DEMO_SCRIPT = [
    "Hi, I need to book an appointment.",
    "Tuesday morning if you have anything.",
    "Actually, can I speak to someone please?",
]


def _report(result: CallResult) -> None:
    print()
    print(f"  call        {result.call_id}")
    print(f"  tenant      {result.tenant_id} ({result.region})")
    print(f"  providers   {', '.join(f'{k}={v}' for k, v in result.providers.items())}")
    print(f"  turns       {result.turns}")
    if result.escalated:
        print(f"  escalated   yes — {result.escalation_reason}")
    else:
        print("  escalated   no")

    print()
    if not result.timings:
        print("  no turns measured")
        return

    print("  turn latency (ms)")
    print("  ---------------------------------------------")
    print("   #      stt      llm      tts    total   target")
    for i, t in enumerate(result.timings, 1):
        mark = "ok" if t.meets_target else "OVER"
        print(
            f"  {i:>2}  {t.stt_ms:>7.0f}  {t.llm_ms:>7.0f}  "
            f"{t.tts_first_audio_ms:>7.0f}  {t.total_ms:>7.0f}   {mark}"
        )
    print("  ---------------------------------------------")

    p95 = result.p95_ms
    verdict = "MEETS" if result.meets_latency_target else "MISSES"
    print(f"  p95 {p95:.0f}ms — {verdict} the NFR1.1 target of 1500ms")
    print()


def _verify_credentials() -> bool:
    """Ask each vendor whether its credential works. Returns True if all do."""
    results = asyncio.run(verify_all())
    print("  credential check (one authenticated request per vendor)")
    print("  ------------------------------------------------------------------")
    for r in sorted(results, key=lambda r: r.provider):
        print(f"  {r.provider:<20} {r.verdict:<16} {r.detail}")
    print("  ------------------------------------------------------------------")
    bad = [r for r in results if not r.reachable]
    if bad:
        print(f"  {len(bad)} of {len(results)} credential(s) will not authenticate.")
        print("  A key being present is not the same as a key that works — until")
        print("  these pass, a live call fails at the vendor, not at our gate.")
    else:
        print("  All credentials authenticate.")
    print()
    return not bad


def _doctor(verify: bool = False) -> int:
    """Report which provider legs are live and which are offline.

    Answers the question you actually have before a first real call: is this
    thing wired up, and will it refuse to run for a compliance reason?
    """
    loaded = load_dotenv_if_present()
    baa = load_baa_register()
    _, statuses = build_registry(regions=[Region.US, Region.INDIA], baa_register=baa)

    print()
    print(f"  .env               {'loaded' if loaded else 'not found'}")
    print(f"  BAA register       {len(baa)} vendors listed, "
          f"{sum(baa.values())} with a confirmed BAA")
    print()
    print("  provider legs")
    print("  ------------------------------------------------------------------")
    seen: set[tuple[str, str]] = set()
    for st in statuses:
        key = (st.leg, st.provider)
        if key in seen:
            continue
        seen.add(key)
        mark = "LIVE" if st.real else "offline"
        print(f"  {st.leg:<10} {st.provider:<20} {mark:<8} {st.reason}")
    print("  ------------------------------------------------------------------")

    live = sum(1 for st in statuses if st.real)
    if live == 0:
        print("  Nothing is wired yet. Copy .env.example to .env and add keys.")
    else:
        blocked = [st for st in statuses if st.real and "NOT confirmed" in st.reason]
        if blocked:
            print(f"  {len(blocked)} live leg(s) will REFUSE US tenant data until a BAA")
            print("  is recorded in compliance/baa-register.toml. India tenants are")
            print("  unaffected — DPDP rather than HIPAA governs them.")
    print()

    if verify:
        return 0 if _verify_credentials() else 1

    if live:
        print("  LIVE above means a key is SET, not that it works. Run")
        print("  --doctor --verify to ask each vendor whether it authenticates.")
        print()
    return 0


async def _run(region: Region, turns: int) -> CallResult:
    registry = ProviderRegistry()
    registry.register(region, offline_provider_set(script=DEMO_SCRIPT))

    tenant = TenantContext(tenant_id="demo-clinic", region=region)
    pipeline = VoicePipeline(registry, clinic_name="Northside Medical")
    return await pipeline.handle_call(tenant, call_id="demo-001", max_turns=turns)


async def _run_live(region: Region, turns: int, script: list[str]) -> CallResult:
    """Call the real vendors, with a synthesised caller in place of a phone.

    The BAA gate is not bypassed here. A US tenant reaches the same refusal it
    would reach on a real call, which is the point of running this at all.
    """
    load_dotenv_if_present()
    baa = load_baa_register()
    registry, statuses = build_registry(regions=[region], baa_register=baa)
    live = [st for st in statuses if st.real]
    if not live:
        print("  Nothing is wired. Run --doctor to see what is missing.")
        raise SystemExit(1)

    tenant = TenantContext(tenant_id="demo-clinic", region=region)
    configured: ProviderSet = registry.for_tenant(tenant)

    print(f"  rendering {len(script)} caller line(s) with {configured.tts.name} ...")
    audio = await render_caller_audio(configured.tts, tenant, script)
    seconds = sum(len(a) for a in audio) / 8000
    print(f"  rendered {seconds:.1f}s of caller audio; placing the call")

    # Same providers, with the carrier replaced by the pre-rendered caller.
    registry.register(
        region,
        ProviderSet(
            stt=configured.stt,
            llm=configured.llm,
            tts=configured.tts,
            telephony=LoopbackTelephony(audio),
        ),
    )
    pipeline = VoicePipeline(registry, clinic_name="Northside Medical")
    return await pipeline.handle_call(tenant, call_id="live-001", max_turns=turns)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ait-voice", description=__doc__)
    parser.add_argument(
        "--region",
        choices=[r.value for r in Region],
        default=Region.US.value,
        help="tenant region — determines which providers serve the call",
    )
    parser.add_argument("--turns", type=int, default=8, help="maximum conversational turns")
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="report which provider legs are live, and stop",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="with --doctor, ask each vendor whether its credential authenticates",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="call the configured vendors for real (costs money)",
    )
    parser.add_argument(
        "--say",
        action="append",
        default=None,
        help="a caller line; repeatable. Defaults to the demo script.",
    )
    args = parser.parse_args(argv)

    configure_logging(args.log_level)

    if args.doctor:
        return _doctor(verify=args.verify)

    region = Region(args.region)
    if args.live:
        try:
            result = asyncio.run(_run_live(region, args.turns, args.say or DEMO_SCRIPT))
        except BAANotConfirmedError as refusal:
            # An expected outcome, not a crash: the gate did its job. A
            # traceback here would read as a bug and invite someone to
            # "fix" it.
            print()
            print("  REFUSED — no data left this machine.")
            print(f"  {refusal}")
            print()
            print("  This is the BAA gate working. Record the executed BAA in")
            print("  compliance/baa-register.toml, or run against an India tenant,")
            print("  which DPDP rather than HIPAA governs.")
            print()
            return 2
    else:
        result = asyncio.run(_run(region, args.turns))
    _report(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
