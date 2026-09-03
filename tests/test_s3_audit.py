"""The S3 audit sink, and the fork it exists to prevent.

The local :class:`~ait_voice.core.audit.AuditLog` keeps the previous entry's
hash in a process-local dict. Two containers each hold their own copy, both read
the same head, and both append an entry claiming it. The chain forks — and each
fork verifies perfectly on its own, so nothing detects it. That is the failure
this module was written for, so it is the failure most of these tests are about.

The double below is not a mock. It implements the three S3 operations the sink
uses, including the conditional-write semantics the whole design rests on, and
raises the same error shape real S3 raises. A mock asserting "put_object was
called with IfNoneMatch" would prove we wrote the header, which is not the
question; the question is whether two writers racing produce one linear chain.

It is still a double, so it owes a replacement obligation in the sense
`team.md` means: an integration test against MinIO or real S3, with Object Lock
actually switched on, is still outstanding. What is proven here is the
concurrency protocol, which is the part with the subtle bug in it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ait_voice.core.audit import AuditEvent, AuditIntegrityError, verify_chain
from ait_voice.core.types import PHI, Region, TenantContext
from ait_voice.db import s3_audit
from ait_voice.db.s3_audit import (
    MAX_CONTENTION_RETRIES,
    AuditWriteContention,
    S3AuditLog,
)
from tests.s3_double import FakeS3

NORTH = TenantContext(tenant_id="northside", region=Region.US)
PARK = TenantContext(tenant_id="parkclinic", region=Region.INDIA)


def _sink(s3: FakeS3) -> S3AuditLog:
    return S3AuditLog("ait-audit", client=s3, prefix="audit")


class TestTheChain:
    async def test_a_single_entry_verifies(self) -> None:
        sink = _sink(FakeS3())

        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")

        assert await sink.verify(NORTH) is True

    async def test_entries_link_in_order(self) -> None:
        s3 = FakeS3()
        sink = _sink(s3)

        for i in range(5):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        rows = await sink.read(NORTH)
        assert [r["call_id"] for r in rows] == [f"c-{i}" for i in range(5)]
        assert rows[0]["previous_hash"] is None
        for earlier, later in zip(rows, rows[1:], strict=False):
            assert later["previous_hash"] == earlier["hash"]
        assert await sink.verify(NORTH) is True

    async def test_tenants_do_not_share_a_chain(self) -> None:
        s3 = FakeS3()
        sink = _sink(s3)

        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="n-1")
        await sink.record(PARK, AuditEvent.CALL_STARTED, call_id="p-1")

        assert len(await sink.read(NORTH)) == 1
        assert len(await sink.read(PARK)) == 1
        assert (await sink.read(PARK))[0]["previous_hash"] is None

    async def test_an_overwrite_is_both_ineffective_and_detected(self) -> None:
        """Object Lock permits a *new version*; it protects the old one.

        So an overwrite is accepted by S3 and must fail in two ways here: `read`
        keeps returning what was originally written, and `verify` reports the
        attempt. Found by running against a real implementation — the earlier
        double had no versions and could not express this at all.
        """
        s3 = FakeS3()
        sink = _sink(s3)
        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")
        await sink.record(NORTH, AuditEvent.CALL_ENDED, call_id="c-1")

        key = sorted(s3.objects)[0]
        s3.put_object(Bucket="ait-audit", Key=key, Body=b'{"event":"tampered"}')

        rows = await sink.read(NORTH)
        assert rows[0]["event"] == AuditEvent.CALL_STARTED, "read followed the tampered version"
        assert await sink.overwritten_keys(NORTH) == [key]
        assert await sink.verify(NORTH) is False

    async def test_a_delete_marker_hides_nothing(self) -> None:
        """An unversioned delete is accepted by S3 and writes a marker.

        `list_objects_v2` then stops returning the entry while the data sits
        retained underneath — which is why the read path lists *versions*. A
        sink that read current objects would silently lose an entry here.
        """
        s3 = FakeS3()
        sink = _sink(s3)
        for i in range(3):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        hidden = sorted(s3.objects)[1]
        s3.delete_object(Bucket="ait-audit", Key=hidden)

        assert hidden not in s3.objects, "the double did not model the delete marker"
        assert len(await sink.read(NORTH)) == 3, "an entry was lost to a delete marker"
        assert await sink.verify(NORTH) is True

    async def test_a_versioned_delete_is_refused(self) -> None:
        """The one thing Object Lock genuinely prevents: destroying the data."""
        s3 = FakeS3()
        sink = _sink(s3)
        await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")
        key = sorted(s3.objects)[0]
        version = s3.versions[key][0][0]

        with pytest.raises(Exception, match="pre-conditions"):
            s3.delete_object(Bucket="ait-audit", Key=key, VersionId=version)


class TestConcurrentWriters:
    """The reason this module exists."""

    async def test_two_writers_do_not_fork_the_chain(self) -> None:
        """Two processes, one shared bucket, interleaved appends.

        Separate `S3AuditLog` instances because that is what two containers
        are: separate head caches, no shared memory, arbitration only through
        the storage layer.
        """
        s3 = FakeS3()
        one, two = _sink(s3), _sink(s3)

        await asyncio.gather(
            *(one.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"a-{i}") for i in range(10)),
            *(two.record(NORTH, AuditEvent.CALL_ENDED, call_id=f"b-{i}") for i in range(10)),
        )

        rows = await one.read(NORTH)
        assert len(rows) == 20, "an entry was lost or overwritten"
        assert verify_chain(rows), "the chain forked"
        assert s3.rejected > 0, "no write ever raced; this test proved nothing"

    async def test_every_entry_survives_contention(self) -> None:
        """A rejected write must be retried, never dropped."""
        s3 = FakeS3()
        sinks = [_sink(s3) for _ in range(4)]

        await asyncio.gather(
            *(
                sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"{n}-{i}")
                for n, sink in enumerate(sinks)
                for i in range(5)
            )
        )

        rows = await one_read(sinks[0])
        assert len({r["call_id"] for r in rows}) == 20
        assert verify_chain(rows)

    async def test_a_stale_cached_head_recovers(self) -> None:
        """One writer's cache goes stale the moment another writer commits."""
        s3 = FakeS3()
        one, two = _sink(s3), _sink(s3)

        await one.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")
        # `two` knows nothing yet; `one` now holds a cache that `two` will invalidate.
        await two.record(NORTH, AuditEvent.CALL_ENDED, call_id="c-2")
        await one.record(NORTH, AuditEvent.CONTENT_STORED, call_id="c-3")

        rows = await one.read(NORTH)
        assert [r["call_id"] for r in rows] == ["c-1", "c-2", "c-3"]
        assert verify_chain(rows)

    async def test_giving_up_is_loud(self, monkeypatch) -> None:
        """A dropped audit entry is the one outcome that must never be silent."""
        s3 = FakeS3()
        sink = _sink(s3)

        async def _always_lose(*_a: object, **_k: object) -> bool:
            return False

        monkeypatch.setattr(sink, "_put_if_absent", _always_lose)
        # Shorten the deadline rather than waiting it out: the assertion is
        # about the refusal being loud, not about how patient it is.
        monkeypatch.setattr(s3_audit, "CONTENTION_DEADLINE_SECONDS", 0.05)

        with pytest.raises(AuditWriteContention, match="NOT written"):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id="c-1")


async def one_read(sink: S3AuditLog) -> list[dict[str, Any]]:
    return await sink.read(NORTH)


class TestItStillRefusesPHI:
    async def test_personal_data_is_rejected_before_any_write(self) -> None:
        """The PHI-free guarantee is what makes retention and erasure coexist."""
        s3 = FakeS3()
        sink = _sink(s3)

        # A short string is deliberately allowed — that is how codes and
        # identifiers get in. What must not pass is a PHI value, or a string
        # long enough to be content rather than a label.
        # mypy already refuses this: `record` takes scalars, and PHI is not
        # one. The ignore is deliberate — the runtime guard exists for callers
        # the type checker never sees, and an untested guard is a comment.
        with pytest.raises(AuditIntegrityError, match="PHI"):
            await sink.record(
                NORTH,
                AuditEvent.CALL_STARTED,
                caller=PHI("+15551110041"),  # type: ignore[arg-type]
            )
        with pytest.raises(AuditIntegrityError, match="characters"):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, transcript="x" * 65)

        assert s3.objects == {}, "a rejected entry still reached the bucket"


class TestKeyLayout:
    async def test_keys_are_zero_padded_so_listing_order_is_numeric(self) -> None:
        """Unpadded, "10" sorts before "9" and the newest entry is not the last key."""
        s3 = FakeS3()
        sink = _sink(s3)
        for i in range(11):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        keys = sorted(s3.objects)
        assert keys[-1].endswith("000000000010.json")
        assert [r["call_id"] for r in await sink.read(NORTH)][-1] == "c-10"

    async def test_region_leads_the_prefix(self) -> None:
        """Region decides retention and residency, so it cannot be below tenant."""
        s3 = FakeS3()
        sink = _sink(s3)
        await sink.record(PARK, AuditEvent.CALL_STARTED, call_id="p-1")

        assert next(iter(s3.objects)).startswith("audit/india/parkclinic/")

    async def test_listing_pages(self) -> None:
        """More entries than one page; the sink must not stop at the first."""
        s3 = FakeS3(page_size=3)
        sink = _sink(s3)
        for i in range(7):
            await sink.record(NORTH, AuditEvent.CALL_STARTED, call_id=f"c-{i}")

        assert len(await sink.read(NORTH)) == 7
        assert MAX_CONTENTION_RETRIES > 1
