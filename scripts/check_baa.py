#!/usr/bin/env python3
"""BAA register gate — C-R1.

`team.md`:

    ALWAYS gate a production deploy on an audited machine check — tests,
    security/dependency/IaC scans, and a BAA-register check for every vendor in
    the live PHI path — passing; self-approval by the sole engineer is not
    treated as a control.

Two modes, because they answer different questions at different moments.

``--audit`` (default, runs on every push): the register is *well formed*. Every
vendor is declared, every entry has the fields it needs, and any vendor marked
``baa = true`` actually names where the executed agreement lives. This can pass
today, with nothing signed, and still be worth running — it catches the failure
where someone flips a flag to unblock themselves and records nothing.

``--require-signed`` (production deploy only): every vendor in the live PHI
path has an executed BAA. This is expected to FAIL until D-05 completes, and
that failure is the control working — it is what stops US patient data reaching
a vendor with no agreement.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tomllib

REPO = pathlib.Path(__file__).resolve().parent.parent
REGISTER = REPO / "compliance" / "baa-register.toml"

#: Vendors that touch call audio, transcripts, or caller identity for a US
#: tenant. India-market vendors are governed by DPDP rather than HIPAA and are
#: not gated here — a separate obligation, not a lesser one.
#:
#: Two kinds of entry, and the second kind is the one that gets forgotten.
#:
#: The speech and telephony vendors are chosen by `config.py`, so they are
#: visible every time someone reads the provider wiring.
#: `tests/test_ci_gates.py` cross-checks this tuple against what `config.py` can
#: actually select for a US tenant, so adding a provider without adding it here
#: fails the build rather than silently leaving it ungated.
#:
#: `aws` is the other kind: infrastructure, selected by nothing, and therefore
#: absent from this list until someone went looking. RDS holds transcripts and
#: intake, CloudWatch holds whatever the logging facade emits, S3 holds the
#: content store. C-R1 does not distinguish between a vendor that transcribes
#: PHI and one that stores it, and a BAA does not flow down — so the gate would
#: otherwise have reported a clean PHI path while every transcript sat in a
#: database held under no agreement at all.
PHI_PATH_VENDORS = ("anthropic", "aws", "deepgram", "elevenlabs", "twilio")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-signed",
        action="store_true",
        help="fail unless every PHI-path vendor has an executed BAA",
    )
    args = parser.parse_args()

    if not REGISTER.exists():
        print(f"BAA register not found at {REGISTER.relative_to(REPO)}")
        return 2

    vendors = tomllib.loads(REGISTER.read_text()).get("vendor", {})
    problems: list[str] = []

    print(f"\n  {'vendor':<16} {'BAA':<12} agreement")
    print("  " + "-" * 58)
    for name in sorted(vendors):
        entry = vendors[name]
        signed = bool(entry.get("baa", False))
        agreement = str(entry.get("agreement", "")).strip()
        print(f"  {name:<16} {'SIGNED' if signed else 'not signed':<12} {agreement or '—'}")

        if "baa" not in entry:
            problems.append(f"{name}: no `baa` field")
        if signed and not agreement:
            # The failure this catches: a flag flipped to unblock a deploy,
            # with nothing recorded about what was actually signed.
            problems.append(f"{name}: marked `baa = true` but names no executed agreement")
        if not signed and not entry.get("how"):
            problems.append(f"{name}: unsigned and no `how` recorded")
    print()

    missing = [v for v in PHI_PATH_VENDORS if v not in vendors]
    if missing:
        problems.append(
            f"vendors in the live PHI path are absent from the register: {', '.join(missing)}"
        )

    if problems:
        print("BAA register is not well formed:\n")
        for problem in problems:
            print(f"  - {problem}")
        print()
        return 1

    if args.require_signed:
        unsigned = [v for v in PHI_PATH_VENDORS if not vendors.get(v, {}).get("baa", False)]
        if unsigned:
            print("PRODUCTION DEPLOY BLOCKED — C-R1\n")
            print(
                f"  {len(unsigned)} vendor(s) in the live PHI path have no executed\n"
                f"  BAA: {', '.join(unsigned)}.\n"
            )
            print(
                "  A BAA does not flow down to subcontractors, so each vendor in\n"
                "  the chain needs its own. This is decision D-05, and it is\n"
                "  external contracting rather than engineering work.\n"
            )
            return 1
        print("Every vendor in the live PHI path has an executed BAA.\n")
        return 0

    print(
        f"Register is well formed: {len(vendors)} vendor(s) declared. "
        f"Run with --require-signed to gate a production deploy.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
