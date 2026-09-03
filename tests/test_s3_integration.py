"""The audit sink against a real S3, with Object Lock actually switched on.

`tests/test_s3_audit.py` proves the concurrency protocol against a double. This
proves the double is telling the truth, which is a different claim and the one
that kept being wrong:

- the first version read current objects, so a delete marker would have silently
  dropped an entry;
- the docs claimed Object Lock refuses deletes and overwrites, and it refuses
  neither — it refuses destroying a *version*.

Both were found here rather than in a unit test, because a double can only model
the semantics its author already understands.

Skips unless `AIT_S3_ENDPOINT` is set, the same way the Postgres tests skip —
so a machine without MinIO still runs the suite, and nothing silently reports
green while checking nothing.
"""

from __future__ import annotations

import uuid

import pytest

from ait_voice.core.audit import AuditEvent
from ait_voice.core.types import PHI, Region, TenantContext
from ait_voice.db.s3_audit import S3AuditLog
from ait_voice.db.s3_content import S3ContentStore
from tests.conftest import requires_s3

pytestmark = requires_s3

NORTH = TenantContext(tenant_id="northside", region=Region.US)


@pytest.fixture
def audit_bucket(s3_client) -> str:  # noqa: ANN001
    """A fresh Object Lock bucket per test.

    Fresh because Object Lock cannot be enabled after creation, and because a
    compliance-mode object cannot be cleaned up afterwards — anything written
    here is retained for the full period, so tests must not share a bucket.
    """
    name = f"audit-{uuid.uuid4().hex[:12]}"
    s3_client.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
    s3_client.put_object_lock_configuration(
        Bucket=name,
        ObjectLockConfiguration={
            "ObjectLockEnabled": "Enabled",
            # One day rather than the production 365: the assertion is about
            # the mode holding, and a year of undeletable test objects on a
            # developer's MinIO is a poor trade for testing the same thing.
            "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE", "Days": 1}},
        },
    )
    return name


@pytest.fixture
def content_bucket(s3_client) -> str:  # noqa: ANN001
    name = f"content-{uuid.uuid4().hex[:12]}"
    s3_client.create_bucket(Bucket=name)
    return name


class TestAgainstRealS3:
    async def test_the_chain_round_trips_and_verifies(self, s3_client, audit_bucket) -> None:  # noqa: ANN001
        sink = S3AuditLog(audit_bucket, client=s3_client)

        for i in range(5):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        rows = await sink.read(NORTH)
        assert [r["call_id"] for r in rows] == [f"c-{i}" for i in range(5)]
        assert await sink.verify(NORTH) is True

    async def test_a_versioned_delete_is_refused_by_object_lock(
        self, s3_client, audit_bucket
    ) -> None:  # noqa: ANN001
        """The one guarantee the whole design rests on."""
        import botocore.exceptions

        sink = S3AuditLog(audit_bucket, client=s3_client)
        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")

        versions = s3_client.list_object_versions(Bucket=audit_bucket)["Versions"]
        target = versions[0]

        with pytest.raises(botocore.exceptions.ClientError):
            s3_client.delete_object(
                Bucket=audit_bucket, Key=target["Key"], VersionId=target["VersionId"]
            )

    async def test_a_delete_marker_hides_nothing_from_the_sink(
        self, s3_client, audit_bucket
    ) -> None:  # noqa: ANN001
        """S3 accepts an unversioned delete. The read path must not care."""
        sink = S3AuditLog(audit_bucket, client=s3_client)
        for i in range(3):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        hidden = sorted(
            o["Key"] for o in s3_client.list_objects_v2(Bucket=audit_bucket)["Contents"]
        )[1]
        s3_client.delete_object(Bucket=audit_bucket, Key=hidden)

        assert s3_client.list_objects_v2(Bucket=audit_bucket)["KeyCount"] == 2, (
            "S3 did not create a delete marker; this test is not exercising the case"
        )
        assert len(await sink.read(NORTH)) == 3
        assert await sink.verify(NORTH) is True

    async def test_an_overwrite_is_ineffective_and_detected(self, s3_client, audit_bucket) -> None:  # noqa: ANN001
        sink = S3AuditLog(audit_bucket, client=s3_client)
        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")

        key = s3_client.list_objects_v2(Bucket=audit_bucket)["Contents"][0]["Key"]
        s3_client.put_object(Bucket=audit_bucket, Key=key, Body=b'{"event":"tampered"}')

        rows = await sink.read(NORTH)
        assert rows[0]["event"] == AuditEvent.CALL_STARTED
        assert await sink.overwritten_keys(NORTH) == [key]
        assert await sink.verify(NORTH) is False

    async def test_two_sinks_racing_produce_one_linear_chain(self, s3_client, audit_bucket) -> None:  # noqa: ANN001
        """The concurrency protocol, against real conditional writes."""
        import asyncio

        one = S3AuditLog(audit_bucket, client=s3_client)
        two = S3AuditLog(audit_bucket, client=s3_client)

        await asyncio.gather(
            *(one.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"a-{i}") for i in range(5)),
            *(two.record(NORTH, AuditEvent.CALL_ENDED, call_id=f"b-{i}") for i in range(5)),
        )

        assert len(await one.read(NORTH)) == 10
        assert await one.verify(NORTH) is True

    async def test_content_erasure_actually_erases(
        self, s3_client, audit_bucket, content_bucket
    ) -> None:  # noqa: ANN001
        """C-R8 in the other direction: the content goes, the record stays."""
        audit = S3AuditLog(audit_bucket, client=s3_client)
        content = S3ContentStore(content_bucket, client=s3_client)

        await content.store(NORTH, "c-1", [PHI("I need an appointment")], audit=audit)
        assert await content.exists(NORTH, "c-1") is True

        assert await content.erase(NORTH, "c-1", audit=audit) is True

        assert await content.exists(NORTH, "c-1") is False
        events = [r["event"] for r in await audit.read(NORTH)]
        assert events == [AuditEvent.CONTENT_STORED, AuditEvent.CONTENT_ERASED]
