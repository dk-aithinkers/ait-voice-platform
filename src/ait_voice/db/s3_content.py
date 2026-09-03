"""Call content in S3 — the erasable half.

Deliberately much simpler than :mod:`ait_voice.db.s3_audit`, and every
difference is a decision rather than an omission.

**No Object Lock.** Content under a compliance-mode lock could not be deleted
on request, and C-R8 requires personal data erased once its purpose is
fulfilled. Locking this bucket would fail the same rule the audit bucket's lock
satisfies, in the other direction.

**No hash chain and no conditional write.** The audit log is a sequence whose
completeness is the guarantee, so it needs an arbitrated append. Content is
keyed by call, each object independent; two writers for one call id are writing
the same call's transcript, and last-write-wins is the correct outcome rather
than a race to detect.

**Delete really deletes.** The bucket is unversioned precisely so that it does:
a delete marker over a retained version would look like erasure and not be one.

The audit entry for a store or an erasure goes to the *other* sink, which is
what keeps the record of what happened when the content itself is gone.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ait_voice.core.audit import AuditEvent
from ait_voice.core.types import PHI, TenantContext

if TYPE_CHECKING:  # pragma: no cover - import-time only
    from mypy_boto3_s3.client import S3Client

    from ait_voice.db.base import AuditSink
else:
    S3Client = Any


class S3ContentStore:
    """Satisfies :class:`~ait_voice.db.base.ContentSink`."""

    def __init__(self, bucket: str, *, client: S3Client, prefix: str = "") -> None:
        self._bucket = bucket
        self._client = client
        self._prefix = prefix.strip("/")

    def _key(self, tenant: TenantContext, call_id: str) -> str:
        # Region leads for the same reason it does in the audit bucket: it
        # decides residency, and a tenant's content never sits under another
        # region's prefix.
        parts = [p for p in (self._prefix, tenant.region.value, tenant.tenant_id) if p]
        return "/".join(parts) + f"/{call_id}.json"

    def locator(self, tenant: TenantContext, call_id: str) -> str:
        return f"s3://{self._bucket}/{self._key(tenant, call_id)}"

    async def store(
        self,
        tenant: TenantContext,
        call_id: str,
        transcript: list[PHI[str]],
        *,
        audit: AuditSink | None = None,
    ) -> str:
        payload = json.dumps(
            {
                "call_id": call_id,
                "stored_at": datetime.now(UTC).isoformat(),
                # Revealed here and nowhere else: this is the store whose whole
                # purpose is holding what the caller said.
                "transcript": [t.reveal() for t in transcript],
            },
            separators=(",", ":"),
        ).encode("utf-8")

        key = self._key(tenant, call_id)

        def _put() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
            )

        await asyncio.to_thread(_put)

        if audit:
            # Counts and codes only. What was said stays in the object above.
            await audit.record(
                tenant,
                AuditEvent.CONTENT_STORED,
                call_id=call_id,
                turn_count=len(transcript),
            )
        return self.locator(tenant, call_id)

    async def erase(
        self,
        tenant: TenantContext,
        call_id: str,
        *,
        audit: AuditSink | None = None,
        reason: str = "purpose_fulfilled",
    ) -> bool:
        key = self._key(tenant, call_id)
        existed = await self.exists(tenant, call_id)

        def _delete() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=key)

        if existed:
            await asyncio.to_thread(_delete)

        if audit:
            # Recorded whether or not anything was there. An erasure request for
            # content that had already gone is a different fact from one that
            # deleted something, and both are worth being able to answer for.
            await audit.record(
                tenant,
                AuditEvent.CONTENT_ERASED,
                call_id=call_id,
                reason=reason,
                existed=existed,
            )
        return existed

    async def exists(self, tenant: TenantContext, call_id: str) -> bool:
        key = self._key(tenant, call_id)

        def _head() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception as exc:  # noqa: BLE001 - narrowed immediately below
                if _is_not_found(exc):
                    return False
                raise

        return await asyncio.to_thread(_head)


def _is_not_found(exc: BaseException) -> bool:
    """Recognise S3's 404 without importing botocore.

    By shape rather than by class, so the one vendor import stays in the
    provider boundary and a MinIO or moto double raising the same coded error
    is treated identically.
    """
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = response.get("Error", {}).get("Code")
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in {"404", "NoSuchKey", "NotFound"} or status == 404
