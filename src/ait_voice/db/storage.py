"""Where the audit log and the content store actually come from.

Until now nothing in `src/` constructed either one. The classes existed, the
tests exercised them, and no running process ever held one — which is why the
buckets could have been provisioned and stayed empty while containers wrote to
their own filesystems. This module is the assembly point that was missing.

The choice is made from the environment, and the interesting part is what
happens when the environment is wrong.

    AIT_AUDIT_BUCKET / AIT_CONTENT_BUCKET   set -> S3
    AIT_AUDIT_ROOT   / AIT_CONTENT_ROOT     set -> local disk
    neither                                      -> local disk under var/

**An empty string is not "unset".** The Dockerfile sets `AIT_AUDIT_ROOT=""`
deliberately, so that a container which somehow reaches this code without a
bucket configured raises instead of quietly picking a path. The filesystem
audit log is single-writer: two ECS tasks holding one would each cache their own
chain head and both append claiming it, forking the chain in a way that still
verifies within each fork. Falling back to it in a container is the one outcome
worth crashing to avoid, so the distinction between "unset" (a developer on a
laptop) and "set to empty" (a container that lost its configuration) is
load-bearing rather than pedantic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from ait_voice.core.audit import AuditLog, ContentStore, default_audit_root, default_content_root
from ait_voice.db.base import AuditSink, ContentSink


class StorageMisconfigured(RuntimeError):
    """The environment describes a deployment that must not be served.

    Raised at startup rather than discovered later, on the same argument as
    `Database.connect()` refusing a superuser: the symptom of getting this wrong
    is everything appearing to work.
    """


@dataclass(frozen=True, slots=True)
class Storage:
    """The two sinks, and a line describing where they went."""

    audit: AuditSink
    content: ContentSink
    description: str


def _blank_but_present(name: str) -> bool:
    return name in os.environ and not os.environ[name].strip()


def build_storage(*, client: Any = None) -> Storage:  # noqa: ANN401 - an S3 client or a double
    """Assemble the audit sink and content store from the environment.

    `client` exists so a test or a MinIO integration can pass its own S3 client;
    left None, boto3 is imported only when a bucket is actually configured, so a
    laptop without the `aws` extra installed still runs.
    """
    audit_bucket = os.environ.get("AIT_AUDIT_BUCKET", "").strip()
    content_bucket = os.environ.get("AIT_CONTENT_BUCKET", "").strip()

    if not audit_bucket and _blank_but_present("AIT_AUDIT_ROOT"):
        raise StorageMisconfigured(
            "AIT_AUDIT_ROOT is set to an empty string and AIT_AUDIT_BUCKET is not "
            "set.\n\n"
            "That combination means a container lost its bucket configuration. "
            "Falling back to the filesystem audit log here would be worse than "
            "failing: it is single-writer, so two tasks would fork the hash "
            "chain, and each fork verifies on its own. Set AIT_AUDIT_BUCKET."
        )
    if not content_bucket and _blank_but_present("AIT_CONTENT_ROOT"):
        raise StorageMisconfigured(
            "AIT_CONTENT_ROOT is set to an empty string and AIT_CONTENT_BUCKET is "
            "not set. Content would be written to a container filesystem and lost "
            "on the next deploy. Set AIT_CONTENT_BUCKET."
        )

    if not audit_bucket and not content_bucket:
        return Storage(
            audit=AuditLog(root=default_audit_root()),
            content=ContentStore(root=default_content_root()),
            description=(
                f"local disk: audit={default_audit_root()}, content={default_content_root()}"
            ),
        )

    # A half-configured deployment is a misconfiguration, not a mode. Splitting
    # the two sinks across S3 and local disk would put the retained record and
    # the erasable one on storage with different durability, which is precisely
    # the separation `project.md` asks to be enforced rather than assumed.
    if not audit_bucket or not content_bucket:
        missing = "AIT_AUDIT_BUCKET" if not audit_bucket else "AIT_CONTENT_BUCKET"
        raise StorageMisconfigured(
            f"{missing} is not set while the other bucket is. Configure both or "
            "neither: the audit log and the content store carry opposite "
            "retention obligations and must not sit on storage with different "
            "durability."
        )

    if client is None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise StorageMisconfigured(
                "S3 buckets are configured but boto3 is not installed. Install the `aws` extra."
            ) from exc
        client = boto3.client("s3")

    from ait_voice.db.s3_audit import S3AuditLog
    from ait_voice.db.s3_content import S3ContentStore

    return Storage(
        audit=S3AuditLog(audit_bucket, client=client),
        content=S3ContentStore(content_bucket, client=client),
        description=f"s3: audit={audit_bucket}, content={content_bucket}",
    )
