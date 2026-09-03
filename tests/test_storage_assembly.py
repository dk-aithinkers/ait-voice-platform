"""`build_storage`, and the misconfiguration it must refuse.

This is the assembly point that did not exist: nothing in `src/` constructed an
audit log or a content store, so the buckets could have been provisioned and
stayed empty while containers wrote to their own filesystems.

Most of these tests are about the refusals rather than the happy path, because
the happy path fails visibly and a bad fallback does not. The specific disaster
is a container quietly choosing the filesystem audit log: it is single-writer,
so two ECS tasks each cache their own chain head, both append claiming it, and
the chain forks — and each fork verifies perfectly on its own.
"""

from __future__ import annotations

import pytest

from ait_voice.core.audit import AuditLog, ContentStore
from ait_voice.db.s3_audit import S3AuditLog
from ait_voice.db.s3_content import S3ContentStore
from ait_voice.db.storage import StorageMisconfigured, build_storage
from tests.s3_double import FakeS3

BUCKET_VARS = ("AIT_AUDIT_BUCKET", "AIT_CONTENT_BUCKET")
ROOT_VARS = ("AIT_AUDIT_ROOT", "AIT_CONTENT_ROOT")


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch) -> None:  # noqa: ANN001
    for name in BUCKET_VARS + ROOT_VARS:
        monkeypatch.delenv(name, raising=False)


class TestTheLocalDefault:
    def test_a_laptop_gets_the_filesystem_stores(self) -> None:
        storage = build_storage()

        assert isinstance(storage.audit, AuditLog)
        assert isinstance(storage.content, ContentStore)
        assert "local disk" in storage.description

    def test_explicit_roots_are_honoured(self, monkeypatch, tmp_path) -> None:  # noqa: ANN001
        monkeypatch.setenv("AIT_AUDIT_ROOT", str(tmp_path / "a"))
        monkeypatch.setenv("AIT_CONTENT_ROOT", str(tmp_path / "c"))

        storage = build_storage()

        assert str(tmp_path / "a") in storage.description


class TestTheBucketPath:
    def test_both_buckets_select_s3(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setenv("AIT_AUDIT_BUCKET", "audit-bucket")
        monkeypatch.setenv("AIT_CONTENT_BUCKET", "content-bucket")

        storage = build_storage(client=FakeS3())

        assert isinstance(storage.audit, S3AuditLog)
        assert isinstance(storage.content, S3ContentStore)
        assert storage.description == "s3: audit=audit-bucket, content=content-bucket"


class TestTheRefusals:
    def test_a_blank_audit_root_without_a_bucket_is_refused(self, monkeypatch) -> None:  # noqa: ANN001
        """The Dockerfile sets AIT_AUDIT_ROOT="" on purpose.

        An empty string is not "unset": it means a container that has lost its
        bucket configuration. Falling back here would fork the audit chain
        across tasks, so this must raise rather than pick a path.
        """
        monkeypatch.setenv("AIT_AUDIT_ROOT", "")

        with pytest.raises(StorageMisconfigured, match="fork the hash"):
            build_storage()

    def test_whitespace_counts_as_blank(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setenv("AIT_AUDIT_ROOT", "   ")

        with pytest.raises(StorageMisconfigured):
            build_storage()

    def test_a_blank_content_root_without_a_bucket_is_refused(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setenv("AIT_CONTENT_ROOT", "")

        with pytest.raises(StorageMisconfigured, match="lost on the next deploy"):
            build_storage()

    def test_an_audit_bucket_alone_is_refused(self, monkeypatch) -> None:  # noqa: ANN001
        """Half-configured is a misconfiguration, not a mode.

        Splitting the two sinks across S3 and local disk would put the retained
        record and the erasable one on storage with different durability, which
        is exactly the separation project.md asks to be enforced.
        """
        monkeypatch.setenv("AIT_AUDIT_BUCKET", "audit-bucket")

        with pytest.raises(StorageMisconfigured, match="AIT_CONTENT_BUCKET is not set"):
            build_storage(client=FakeS3())

    def test_a_content_bucket_alone_is_refused(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.setenv("AIT_CONTENT_BUCKET", "content-bucket")

        with pytest.raises(StorageMisconfigured, match="AIT_AUDIT_BUCKET is not set"):
            build_storage(client=FakeS3())

    def test_a_bucket_set_to_blank_reads_as_unset(self, monkeypatch) -> None:  # noqa: ANN001
        """Not a half-configuration — both blank is just the local default."""
        monkeypatch.setenv("AIT_AUDIT_BUCKET", "  ")
        monkeypatch.setenv("AIT_CONTENT_BUCKET", "")

        assert isinstance(build_storage().audit, AuditLog)


class TestTheContainerCase:
    def test_the_dockerfile_environment_without_buckets_refuses(self, monkeypatch) -> None:  # noqa: ANN001
        """Exactly what the image sets, minus the task definition's buckets.

        If this ever starts returning a filesystem store, the image and this
        module have drifted apart and a deploy will fork the audit chain.
        """
        monkeypatch.setenv("AIT_AUDIT_ROOT", "")
        monkeypatch.setenv("AIT_CONTENT_ROOT", "")

        with pytest.raises(StorageMisconfigured):
            build_storage()

    def test_the_dockerfile_environment_with_buckets_selects_s3(self, monkeypatch) -> None:  # noqa: ANN001
        """The deployed combination: blank roots, buckets from the task definition."""
        monkeypatch.setenv("AIT_AUDIT_ROOT", "")
        monkeypatch.setenv("AIT_CONTENT_ROOT", "")
        monkeypatch.setenv("AIT_AUDIT_BUCKET", "ait-audit-us")
        monkeypatch.setenv("AIT_CONTENT_BUCKET", "ait-content-us")

        storage = build_storage(client=FakeS3())

        assert isinstance(storage.audit, S3AuditLog)
        assert isinstance(storage.content, S3ContentStore)
