"""The S3 content store, and the ways it must differ from the audit sink.

One contract, run against both implementations, because the risk in a backend
swap is not that the new one fails loudly — it is that it behaves *almost* the
same. Where the two genuinely differ the test says so rather than being
weakened to paper over it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ait_voice.core.audit import AuditEvent, AuditLog, ContentStore
from ait_voice.core.types import PHI, Region, TenantContext
from ait_voice.db.s3_content import S3ContentStore
from tests.s3_double import FakeS3

NORTH = TenantContext(tenant_id="northside", region=Region.US)
PARK = TenantContext(tenant_id="parkclinic", region=Region.INDIA)

IMPLEMENTATIONS = ["memory", "s3"]


@pytest.fixture(params=IMPLEMENTATIONS)
def implementation(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def content(implementation: str, tmp_path: Path) -> Any:  # noqa: ANN401
    if implementation == "memory":
        return ContentStore(root=tmp_path / "content")
    return S3ContentStore("ait-content", client=FakeS3(), prefix="content")


class TestTheContract:
    async def test_content_round_trips(self, content: Any) -> None:  # noqa: ANN401
        await content.store(NORTH, "c-1", [PHI("I need an appointment")])

        assert await content.exists(NORTH, "c-1")

    async def test_absent_content_does_not_exist(self, content: Any) -> None:  # noqa: ANN401
        assert await content.exists(NORTH, "never-stored") is False

    async def test_erase_removes_it(self, content: Any) -> None:  # noqa: ANN401
        await content.store(NORTH, "c-1", [PHI("hello")])

        assert await content.erase(NORTH, "c-1") is True
        assert await content.exists(NORTH, "c-1") is False

    async def test_erasing_absent_content_reports_it_did_not_exist(self, content: Any) -> None:  # noqa: ANN401
        """A different fact from an erasure that deleted something, and C-R8
        wants both answerable."""
        assert await content.erase(NORTH, "never-stored") is False

    async def test_one_clinic_cannot_reach_anothers(self, content: Any) -> None:  # noqa: ANN401
        await content.store(NORTH, "shared-id", [PHI("hello")])

        assert await content.exists(NORTH, "shared-id")
        assert await content.exists(PARK, "shared-id") is False

    async def test_the_locator_is_a_string_not_a_path(self, content: Any) -> None:  # noqa: ANN401
        """`Path` is filesystem vocabulary; S3 returns a URI. A caller that
        could treat either as a path would work against one backend only."""
        locator = await content.store(NORTH, "c-1", [PHI("hello")])

        assert isinstance(locator, str)


class TestTheAuditEntries:
    """Storing and erasing content are facts the *other* sink records.

    That asymmetry is the whole C-R7 / C-R8 resolution: the content goes, the
    record that it existed and was erased stays.
    """

    async def test_storing_is_audited_without_the_content(
        self, content: Any, tmp_path: Path
    ) -> None:  # noqa: ANN401
        audit = AuditLog(root=tmp_path / "audit")

        await content.store(NORTH, "c-1", [PHI("I have chest pain")], audit=audit)

        rows = await audit.read(NORTH)
        assert [r["event"] for r in rows] == [AuditEvent.CONTENT_STORED]
        assert rows[0]["detail"]["turn_count"] == 1
        assert "chest pain" not in str(rows)

    async def test_the_erasure_record_outlives_the_content(
        self, content: Any, tmp_path: Path
    ) -> None:  # noqa: ANN401
        audit = AuditLog(root=tmp_path / "audit")
        await content.store(NORTH, "c-1", [PHI("hello")], audit=audit)

        await content.erase(NORTH, "c-1", audit=audit)

        assert await content.exists(NORTH, "c-1") is False
        events = [r["event"] for r in await audit.read(NORTH)]
        assert events == [AuditEvent.CONTENT_STORED, AuditEvent.CONTENT_ERASED]
        assert await audit.verify(NORTH) is True

    async def test_an_erasure_that_found_nothing_is_still_recorded(
        self, content: Any, tmp_path: Path
    ) -> None:  # noqa: ANN401
        audit = AuditLog(root=tmp_path / "audit")

        await content.erase(NORTH, "never-stored", audit=audit)

        rows = await audit.read(NORTH)
        assert rows[0]["detail"]["existed"] is False


class TestWhereTheTwoDiffer:
    """Stated rather than smoothed over."""

    async def test_s3_content_is_not_under_object_lock(self) -> None:
        """The audit sink writes with IfNoneMatch and must never be overwritten.

        Content is the opposite: keyed by call, and re-storing the same call is
        a legitimate overwrite rather than a race to arbitrate. If this ever
        starts refusing, someone has copied the audit sink's write path here and
        made erasure impossible.
        """
        s3 = FakeS3()
        store = S3ContentStore("ait-content", client=s3)

        await store.store(NORTH, "c-1", [PHI("first")])
        await store.store(NORTH, "c-1", [PHI("second")])

        assert s3.rejected == 0, "content was written with a conditional put"
        assert await store.exists(NORTH, "c-1")

    async def test_the_s3_locator_is_a_uri(self) -> None:
        store = S3ContentStore("ait-content", client=FakeS3(), prefix="content")

        locator = await store.store(NORTH, "c-1", [PHI("hello")])

        assert locator == "s3://ait-content/content/us/northside/c-1.json"

    async def test_region_leads_the_key(self) -> None:
        """Region decides residency; a tenant's content never sits under another."""
        s3 = FakeS3()
        store = S3ContentStore("ait-content", client=s3, prefix="content")

        await store.store(PARK, "p-1", [PHI("namaste")])

        assert next(iter(s3.objects)).startswith("content/india/parkclinic/")
