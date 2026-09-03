#!/usr/bin/env python3
"""IaC gate — the compliance properties of the deployed infrastructure.

`project.md`, on the audit log and the content store:

    The two log classes carry different retention policies and are enforced as
    separate infrastructure (separate sinks, separate IaC-defined retention),
    not merely as a written convention, so the separation is machine-checkable
    rather than memorized.

This is the machine doing the checking. It reads the synthesised CloudFormation
and asserts the properties that carry regulatory weight — not that the stack
deploys, which `cdk deploy` will tell you, but that what deploys still has the
guarantees the constraints were signed off against.

    cd infra && python app.py          # synthesise
    python scripts/check_infra.py      # assert

Every check here maps to something someone affirmed, and the reason is stated
in the failure rather than left to a reader with the constraint register open.
An IaC scan that only checked syntax would pass a template that had quietly
lost Object Lock.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "infra" / "cdk.out"

PLATFORM = "AitVoice-Platform-US.template.json"
SERVICE = "AitVoice-Service-US.template.json"

#: C-R7. Security logs retained at least a year.
MIN_AUDIT_RETENTION_DAYS = 365

#: A ConversationRelay socket is held for the length of a call. The AWS default
#: is 60 seconds, which would cut every conversation past a minute — and cut it
#: mid-sentence, on a live call, with a patient on the line.
MIN_VOICE_IDLE_TIMEOUT_SECONDS = 600

#: Credentials that must arrive from Secrets Manager. A plaintext value in a
#: task definition is readable by anyone with console access and shows up in
#: `describe-task-definition`, which is not where a Twilio auth token or the
#: relay signing key belongs.
MUST_BE_SECRETS = ("AIT_DB_PASSWORD", "AIT_RELAY_TOKEN_SECRET", "TWILIO_AUTH_TOKEN")

#: TLS policies that still permit 1.0 or 1.1. AWS keeps offering them and CDK
#: still defaults to one, so the version has to be asserted rather than assumed.
WEAK_TLS_POLICIES = (
    "ELBSecurityPolicy-2016-08",
    "ELBSecurityPolicy-TLS-1-0-2015-04",
    "ELBSecurityPolicy-TLS-1-1-2017-01",
    "ELBSecurityPolicy-FS-2018-06",
    "ELBSecurityPolicy-FS-1-1-2019-08",
)


class Failure(Exception):
    pass


def _load(name: str) -> dict:
    path = OUT / name
    if not path.exists():
        raise Failure(
            f"{path.relative_to(REPO)} not found. Synthesise first:\n    cd infra && python app.py"
        )
    return json.loads(path.read_text())


def _resources(template: dict, kind: str) -> dict:
    return {k: v for k, v in template["Resources"].items() if v["Type"] == kind}


def check_buckets(platform: dict) -> list[str]:
    notes = []
    buckets = _resources(platform, "AWS::S3::Bucket")
    locked = {k: v for k, v in buckets.items() if v["Properties"].get("ObjectLockEnabled")}
    unlocked = {k: v for k, v in buckets.items() if not v["Properties"].get("ObjectLockEnabled")}

    if len(locked) != 1:
        raise Failure(
            f"expected exactly one Object Lock bucket (the audit log), found {len(locked)}. "
            "C-R7 and C-R8 only both hold if retained and erasable data are in "
            "different places."
        )
    if not unlocked:
        raise Failure(
            "no erasable bucket found. Content under Object Lock cannot be erased "
            "on request, which fails C-R8 in the other direction."
        )

    ((audit_name, audit),) = locked.items()
    props = audit["Properties"]
    retention = props["ObjectLockConfiguration"]["Rule"]["DefaultRetention"]
    if retention.get("Mode") != "COMPLIANCE":
        raise Failure(
            f"audit bucket Object Lock is {retention.get('Mode')!r}, not COMPLIANCE. "
            "GOVERNANCE mode can be bypassed by any principal holding "
            "s3:BypassGovernanceRetention, which makes immutability a policy "
            "rather than a property."
        )
    if int(retention.get("Days", 0)) < MIN_AUDIT_RETENTION_DAYS:
        raise Failure(
            f"audit retention is {retention.get('Days')} days; C-R7 requires at "
            f"least {MIN_AUDIT_RETENTION_DAYS}."
        )
    if props.get("VersioningConfiguration", {}).get("Status") != "Enabled":
        raise Failure("Object Lock requires versioning; it is not enabled.")
    notes.append(f"audit bucket {audit_name[:14]}: COMPLIANCE / {retention['Days']}d, versioned")

    for name, bucket in unlocked.items():
        p = bucket["Properties"]
        rules = p.get("LifecycleConfiguration", {}).get("Rules", [])
        if not any(r.get("ExpirationInDays") for r in rules):
            raise Failure(
                f"content bucket {name} has no expiration rule. C-R8 requires personal "
                "data erased once its purpose is fulfilled; a bucket that only grows "
                "relies on the application never missing one."
            )
        notes.append(
            f"content bucket {name[:14]}: expires after "
            f"{[r.get('ExpirationInDays') for r in rules if r.get('ExpirationInDays')][0]}d"
        )

    for name, bucket in buckets.items():
        p = bucket["Properties"]
        if not p.get("BucketEncryption"):
            raise Failure(f"{name} is not encrypted at rest; the AWS BAA requires it for PHI.")
        if not p.get("PublicAccessBlockConfiguration"):
            raise Failure(f"{name} does not block public access.")
    notes.append(f"all {len(buckets)} bucket(s): encrypted, public access blocked")
    return notes


def check_database(platform: dict) -> list[str]:
    instances = _resources(platform, "AWS::RDS::DBInstance")
    if not instances:
        raise Failure("no database found in the platform stack.")
    notes = []
    for name, db in instances.items():
        p = db["Properties"]
        if not p.get("StorageEncrypted"):
            raise Failure(
                f"{name} is not encrypted at rest. RDS is HIPAA-eligible under the "
                "AWS BAA only with encryption on, and it cannot be enabled in place."
            )
        if p.get("PubliclyAccessible"):
            raise Failure(f"{name} is publicly accessible.")
        if not p.get("DeletionProtection"):
            raise Failure(f"{name} has no deletion protection.")
        notes.append(f"database {name[:14]}: encrypted, private, deletion-protected")
    return notes


def check_task_role(service: dict) -> list[str]:
    """The running container must not be able to ask to delete an audit entry."""
    required = {
        "s3:DeleteObject",
        "s3:DeleteObjectVersion",
        "s3:PutObjectRetention",
        "s3:BypassGovernanceRetention",
    }
    for policy in _resources(service, "AWS::IAM::Policy").values():
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            if statement.get("Effect") != "Deny":
                continue
            actions = statement.get("Action")
            actions = set(actions if isinstance(actions, list) else [actions])
            resource = json.dumps(statement.get("Resource"))
            if required <= actions and "Audit" in resource:
                return ["task role: explicitly denied deletion on the audit bucket"]
    raise Failure(
        "no explicit Deny on audit-bucket deletion was found in the task role.\n"
        "  Object Lock refuses anyway, so this is defence in depth — but it is the "
        "layer that does not depend on one bucket property staying correct."
    )


def check_listeners(service: dict, *, allow_insecure: bool = False) -> list[str]:
    """Nothing public may forward plaintext, and TLS must be 1.2 or better.

    A general rule rather than a per-service one, because the failure it guards
    against is a new service being added without anyone thinking about it. The
    operator console serves transcripts and intake details; the voice socket
    carries the conversation itself. Both are PHI in transit, and neither has a
    version of this that is acceptable in clear.

    A redirect listener on port 80 is fine and expected — it is how a caller
    reaching http:// gets moved to https://. What is refused is a listener that
    *forwards* plaintext to a target.
    """
    listeners = _resources(service, "AWS::ElasticLoadBalancingV2::Listener")
    if not listeners:
        raise Failure("no load balancer listeners found; nothing is reachable.")

    plaintext, weak = [], []
    for name, listener in listeners.items():
        props = listener["Properties"]
        actions = props.get("DefaultActions") or [{}]
        forwards = any(a.get("Type") == "forward" for a in actions)
        if props.get("Protocol") == "HTTP" and forwards:
            plaintext.append(name)
        policy = props.get("SslPolicy")
        if policy and policy in WEAK_TLS_POLICIES:
            weak.append(f"{name} ({policy})")

    if plaintext and not allow_insecure:
        raise Failure(
            f"{len(plaintext)} listener(s) forward plaintext HTTP: {', '.join(plaintext)}.\n"
            "  These serve transcripts, intake details and caller numbers — PHI on "
            "the public internet in clear. Supply a certificate, or deploy with "
            "allowInsecureApi for an environment that will never hold real data."
        )
    if weak:
        raise Failure(
            f"listener(s) permit TLS below 1.2: {', '.join(weak)}. "
            "The CDK default policy still allows TLS 1.0."
        )

    secure = [n for n, v in listeners.items() if v["Properties"].get("Protocol") == "HTTPS"]
    if plaintext:
        return [
            f"listeners: {len(plaintext)} PLAINTEXT (insecure mode) — no real data may reach these"
        ]
    return [f"listeners: {len(secure)} HTTPS, TLS 1.2+, plaintext redirected"]


def check_voice_service(service: dict, *, required: bool = False) -> list[str]:
    """The carrier-facing service, when a certificate made it materialise.

    Skips loudly rather than silently: a gate that quietly checks half a stack
    reports green on the half nobody looked at.
    """
    task_defs = _resources(service, "AWS::ECS::TaskDefinition")
    voice = None
    for td in task_defs.values():
        for container in td["Properties"]["ContainerDefinitions"]:
            command = container.get("Command") or []
            if any("voice_main" in str(part) for part in command):
                voice = container
    if voice is None:
        if required:
            raise Failure(
                "the voice service was not synthesised, so none of its checks ran.\n"
                "  Set AIT_VOICE_DOMAIN and AIT_VOICE_CERT_ARN before synthesising. "
                "A gate that quietly checks half a stack reports green on the half "
                "nobody looked at."
            )
        return [
            "voice service: NOT SYNTHESISED — its checks did not run. Set "
            "AIT_VOICE_DOMAIN and AIT_VOICE_CERT_ARN to include it."
        ]

    notes = []
    env = {e["Name"]: e.get("Value") for e in voice.get("Environment", [])}
    secrets = {s["Name"] for s in voice.get("Secrets", [])}

    relay = str(env.get("AIT_RELAY_WS_URL", ""))
    if not relay.startswith("wss://"):
        raise Failure(
            f"the voice service would advertise {relay!r} in its TwiML. A plain "
            "ws:// socket carries the transcript in clear text, and C-R2 makes "
            "that PHI."
        )

    plaintext = [name for name in MUST_BE_SECRETS if name in env]
    if plaintext:
        raise Failure(
            f"{', '.join(plaintext)} appear as plaintext environment values in the "
            "voice task definition. They must come from Secrets Manager — a task "
            "definition is readable by anyone with console access."
        )
    missing = [name for name in MUST_BE_SECRETS if name not in secrets]
    if missing:
        raise Failure(
            f"the voice task definition does not source {', '.join(missing)} from Secrets Manager."
        )

    for root in ("AIT_AUDIT_ROOT", "AIT_CONTENT_ROOT"):
        if env.get(root, None) != "":
            raise Failure(
                f"{root} is {env.get(root)!r} in the voice task definition. It must be "
                "an empty string: that is what makes `build_storage` refuse rather "
                "than fall back to the single-writer filesystem audit log, which "
                "forks the hash chain across tasks."
            )
    notes.append("voice service: wss only, secrets from Secrets Manager, S3 forced")

    # The listener must be HTTPS, and the balancer must not cut a call.
    listeners = _resources(service, "AWS::ElasticLoadBalancingV2::Listener")
    https = [n for n, v in listeners.items() if v["Properties"].get("Certificates")]
    if not https:
        raise Failure("no HTTPS listener with a certificate was found for the voice service.")

    balancers = _resources(service, "AWS::ElasticLoadBalancingV2::LoadBalancer")
    timeouts = {}
    for name, lb in balancers.items():
        attrs = {
            a["Key"]: a.get("Value") for a in lb["Properties"].get("LoadBalancerAttributes", [])
        }
        if "idle_timeout.timeout_seconds" in attrs:
            timeouts[name] = int(attrs["idle_timeout.timeout_seconds"])
    if not timeouts:
        raise Failure(
            "no load balancer sets an idle timeout. The AWS default is 60 seconds, "
            "which cuts every call that runs past a minute — mid-sentence, with a "
            "patient on the line."
        )
    worst = min(timeouts.values())
    if worst < MIN_VOICE_IDLE_TIMEOUT_SECONDS:
        raise Failure(
            f"the voice load balancer's idle timeout is {worst}s; a call needs at "
            f"least {MIN_VOICE_IDLE_TIMEOUT_SECONDS}s."
        )
    notes.append(f"voice load balancer: HTTPS, idle timeout {worst}s")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-insecure",
        action="store_true",
        help="permit plaintext listeners, for a synth of a non-PHI environment",
    )
    parser.add_argument(
        "--require-voice",
        action="store_true",
        help="fail if the voice service was not synthesised, rather than noting it",
    )
    args = parser.parse_args(argv)
    try:
        platform, service = _load(PLATFORM), _load(SERVICE)
        notes = (
            check_buckets(platform)
            + check_database(platform)
            + check_task_role(service)
            + check_listeners(service, allow_insecure=args.allow_insecure)
            + check_voice_service(service, required=args.require_voice)
        )
    except Failure as exc:
        print(f"\nINFRASTRUCTURE GATE FAILED\n\n  {exc}\n", file=sys.stderr)
        return 1
    print("\n  infrastructure compliance")
    print("  " + "-" * 62)
    for note in notes:
        print(f"    {note}")
    print("  " + "-" * 62)
    print(f"\n  {len(notes)} check(s) passed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
