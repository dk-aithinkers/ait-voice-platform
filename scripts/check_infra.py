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

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "infra" / "cdk.out"

PLATFORM = "AitVoice-Platform-US.template.json"
SERVICE = "AitVoice-Service-US.template.json"

#: C-R7. Security logs retained at least a year.
MIN_AUDIT_RETENTION_DAYS = 365


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


def main() -> int:
    try:
        platform, service = _load(PLATFORM), _load(SERVICE)
        notes = check_buckets(platform) + check_database(platform) + check_task_role(service)
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
