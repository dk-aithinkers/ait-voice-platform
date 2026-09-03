"""The audit log in S3, with immutability the platform enforces.

`project.md` requires the audit log and the content store to be *separate
infrastructure* with separate IaC-defined retention, "machine-checkable rather
than memorized", because C-R7 (retain security logs a year) and C-R8 (erase
personal data when its purpose ends) only both hold if they apply to disjoint
data. A bucket under Object Lock, holding PHI-free entries, is that separation made
real: AWS refuses to destroy a retained *version*, whoever asks and whatever
their IAM policy says. It does not refuse a delete marker or a new version, and
:meth:`S3AuditLog._list_originals` is where that distinction is handled.

That is the difference from :class:`~ait_voice.core.audit.AuditLog`, which is
append-only because nothing in it issues an UPDATE. This one is append-only
because the storage layer will not accept anything else.

**Why the chain needs more than a filename.** The local log keeps the previous
entry's hash in a process-local dict. Two containers each hold their own copy,
both read the same head, and both append an entry claiming it — the chain forks,
and each fork verifies perfectly on its own. Nothing detects that.

S3 has no append and no atomic counter, so the fix uses the one primitive it
does have: a conditional write. Entry *n* is an object at a zero-padded key, and
it is written with ``IfNoneMatch: "*"``, which S3 honours by refusing if the key
already exists. Two writers racing for sequence 42 cannot both win — the loser
gets 412, re-reads the head that actually landed, rebuilds its entry against the
real predecessor and tries 43. No lock, no coordinator, and the chain stays
linear because the storage layer arbitrates.

Zero padding matters: S3 lists keys lexicographically, so ``000000000042``
sorts after ``000000000041`` while ``42`` sorts before ``5``. The padding is
what makes "the last key in the listing" mean "the newest entry".

boto3 is synchronous, so every call goes through ``asyncio.to_thread``. The
alternative is another dependency for a path that writes a few small objects per
call; blocking the event loop mid-conversation would be the real cost.
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ait_voice.core.audit import (
    AuditEntry,
    AuditEvent,
    _reject_personal_data,
    verify_chain,
)
from ait_voice.core.types import TenantContext

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = Any

#: Wide enough that a clinic taking a call a second for a decade does not reach
#: it, and fixed so lexicographic order is numeric order.
SEQUENCE_WIDTH = 12

#: Bounded by time rather than attempts, and the difference is not cosmetic.
#:
#: A hash chain serialises writes: exactly one writer can win each sequence, so
#: with *n* writers racing, the last one to land needs *n* attempts. A fixed
#: budget therefore has a cliff at *n* — twenty concurrent appends against a
#: budget of eight drops twelve entries, which is the one outcome this module
#: must never produce. Found by `tests/test_s3_audit.py`, which raced twenty.
#:
#: So the loop retries until a deadline instead. Throughput per tenant is
#: roughly one entry per round trip either way; what changes is that heavy
#: contention costs latency rather than data.
CONTENTION_DEADLINE_SECONDS = 20.0

#: A backstop against a pathological loop, high enough not to be the binding
#: limit in any realistic contention.
MAX_CONTENTION_RETRIES = 256

#: Jittered so writers that collided do not retry in lockstep and collide again.
_RETRY_BACKOFF_SECONDS = 0.005


class AuditWriteContention(RuntimeError):
    """Too many writers raced for the same chain position.

    Never silently swallowed: a dropped audit entry is the failure this whole
    module exists to prevent.
    """


class S3AuditLog:
    """Satisfies :class:`~ait_voice.db.base.AuditSink`, backed by Object Lock."""

    def __init__(self, bucket: str, *, client: S3Client, prefix: str = "") -> None:
        self._bucket = bucket
        self._client = client
        self._prefix = prefix.strip("/")
        #: Per-tenant (sequence, hash) of the last entry this process wrote.
        #: An optimisation only — every write revalidates against S3, so a stale
        #: entry costs one retry rather than a broken chain.
        self._head: dict[str, tuple[int, str]] = {}

    # -- keys ------------------------------------------------------------

    def _tenant_prefix(self, tenant: TenantContext) -> str:
        # Region leads, because region decides retention and residency; a
        # tenant's entries never sit under another region's prefix.
        parts = [p for p in (self._prefix, tenant.region.value, tenant.tenant_id) if p]
        return "/".join(parts) + "/"

    def _key(self, tenant: TenantContext, sequence: int) -> str:
        return f"{self._tenant_prefix(tenant)}{sequence:0{SEQUENCE_WIDTH}d}.json"

    # -- reads -----------------------------------------------------------

    async def _list_originals(self, tenant: TenantContext) -> list[tuple[str, str, int]]:
        """Every entry as (key, version_id, version_count), oldest version each.

        Deliberately `list_object_versions` and not `list_objects_v2`, and this
        is the difference between tamper-*evident* and tamper-*proof*.

        Object Lock protects versions, not the current-version view. Verified
        against a real implementation:

        - `DeleteObject` with no version id is **accepted**; it writes a delete
          marker, and the entry vanishes from `list_objects_v2` while the data
          sits retained underneath.
        - `PutObject` on the same key is **accepted**; it adds a version, and
          `get_object` then serves the new bytes.
        - `DeleteObject` *with* a version id is **refused**. Nothing that was
          written can be destroyed.

        So reading current versions would let anyone with PutObject hide or
        replace entries — the hash chain would catch it, but only after the
        fact. Reading the oldest version of each key reads what was actually
        written, and listing versions means a delete marker hides nothing. The
        sink writes each key exactly once with `IfNoneMatch`, so a key with more
        than one version is itself evidence, which is why the count comes back.
        """

        def _list() -> list[tuple[str, str, int]]:
            versions: dict[str, list[dict[str, Any]]] = {}
            prefix = self._tenant_prefix(tenant)
            kwargs: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            while True:
                page = self._client.list_object_versions(**kwargs)
                for item in page.get("Versions", []):
                    versions.setdefault(item["Key"], []).append(item)
                if not page.get("IsTruncated"):
                    break
                kwargs["KeyMarker"] = page.get("NextKeyMarker")
                kwargs["VersionIdMarker"] = page.get("NextVersionIdMarker")

            out = []
            for key, items in versions.items():
                oldest = min(items, key=lambda v: v["LastModified"])
                out.append((key, oldest["VersionId"], len(items)))
            return sorted(out)

        return await asyncio.to_thread(_list)

    async def _get(self, key: str, version_id: str | None = None) -> dict[str, Any]:
        def _fetch() -> dict[str, Any]:
            kwargs: dict[str, Any] = {"Bucket": self._bucket, "Key": key}
            if version_id:
                kwargs["VersionId"] = version_id
            body = self._client.get_object(**kwargs)["Body"].read()
            loaded: dict[str, Any] = json.loads(body)
            return loaded

        return await asyncio.to_thread(_fetch)

    async def _discover_head(self, tenant: TenantContext) -> tuple[int, str | None]:
        """The real chain head in S3: (next sequence, hash of the last entry)."""
        entries = await self._list_originals(tenant)
        if not entries:
            return 0, None
        key, version_id, _ = entries[-1]
        sequence = int(key.rsplit("/", 1)[-1].removesuffix(".json"))
        row = await self._get(key, version_id)
        return sequence + 1, str(row["hash"])

    async def read(self, tenant: TenantContext) -> list[dict[str, Any]]:
        """Every entry as originally written, oldest version of each key."""
        return [
            await self._get(key, version_id)
            for key, version_id, _ in await self._list_originals(tenant)
        ]

    async def overwritten_keys(self, tenant: TenantContext) -> list[str]:
        """Keys carrying more than one version.

        Each key is written once, with `IfNoneMatch`. A second version means
        something tried to replace an audit entry — which Object Lock permits
        (the original survives underneath) and which nothing else would report,
        because :meth:`read` deliberately ignores it.
        """
        return [key for key, _, count in await self._list_originals(tenant) if count > 1]

    async def verify(self, tenant: TenantContext) -> bool:
        """The chain, plus the fact that nobody tried to write over it."""
        if await self.overwritten_keys(tenant):
            return False
        return verify_chain(await self.read(tenant))

    # -- the write ---------------------------------------------------------

    async def record(
        self,
        tenant: TenantContext,
        event: AuditEvent,
        *,
        call_id: str | None = None,
        caller_ref: str | None = None,
        **detail: str | int | float | bool,
    ) -> AuditEntry:
        """Append one entry, arbitrating with any other writer through S3."""
        _reject_personal_data(detail)

        cached = self._head.get(tenant.tenant_id)
        if cached is None:
            sequence, previous = await self._discover_head(tenant)
        else:
            sequence, previous = cached[0] + 1, cached[1]

        deadline = asyncio.get_running_loop().time() + CONTENTION_DEADLINE_SECONDS
        attempts = 0
        while attempts < MAX_CONTENTION_RETRIES:
            attempts += 1
            entry = AuditEntry(
                entry_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                tenant_id=tenant.tenant_id,
                region=tenant.region.value,
                event=event,
                call_id=call_id,
                caller_ref=caller_ref,
                detail=dict(detail),
                previous_hash=previous,
            )
            if await self._put_if_absent(self._key(tenant, sequence), entry):
                self._head[tenant.tenant_id] = (sequence, entry.content_hash())
                return entry
            # Someone else took this slot. Their entry is now the predecessor,
            # so the one we just built is stale in both its sequence and its
            # previous_hash — rebuild rather than retry the same bytes.
            if asyncio.get_running_loop().time() > deadline:
                break
            # Jitter, so writers that just collided do not step on each other
            # again in the same order.
            # S311: this jitter decides who retries first, not who can read
            # anything. Nothing here is a secret, a token or an identifier.
            jitter = random.uniform(0, _RETRY_BACKOFF_SECONDS * attempts)  # noqa: S311
            await asyncio.sleep(jitter)
            sequence, previous = await self._discover_head(tenant)

        raise AuditWriteContention(
            f"gave up appending to the audit log for tenant {tenant.tenant_id!r} "
            f"after {attempts} attempt(s) over {CONTENTION_DEADLINE_SECONDS:.0f}s. "
            "The entry was NOT written."
        )

    async def _put_if_absent(self, key: str, entry: AuditEntry) -> bool:
        """True if we claimed the key, False if another writer already had it."""

        def _put() -> bool:
            try:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=entry.to_json().encode("utf-8"),
                    ContentType="application/json",
                    # The whole concurrency story in one header: S3 refuses if
                    # the key exists, so the race is decided by the storage
                    # layer rather than by us hoping.
                    IfNoneMatch="*",
                )
                return True
            except Exception as exc:  # noqa: BLE001 - narrowed immediately below
                if _is_precondition_failed(exc):
                    return False
                raise

        return await asyncio.to_thread(_put)


def _is_precondition_failed(exc: BaseException) -> bool:
    """Recognise S3's "that key already exists" without importing botocore.

    Checked by shape rather than by class so this module keeps its only vendor
    import in one place, and so a moto or MinIO double raising the same coded
    error is handled identically to real S3.
    """
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    error = response.get("Error", {})
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return error.get("Code") in {"PreconditionFailed", "ConditionalRequestConflict"} or (
        status == 412
    )
