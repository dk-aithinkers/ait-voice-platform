"""A faithful in-memory S3, shared by the audit and content sink tests.

Not a mock. It implements the operations both sinks use with the semantics they
actually depend on — conditional writes that refuse an existing key, a 404 shape
for a missing one, and lexicographic paginated listing. A mock asserting
"put_object was called with IfNoneMatch" would prove the header was sent, which
is not the question; the question is whether two writers racing produce one
linear chain, and only real semantics can answer that.

Still a double. An integration test against MinIO or real S3, with Object Lock
switched on, is a separate obligation and is not discharged here.
"""

from __future__ import annotations

from typing import Any


class PreconditionFailed(Exception):
    """Shaped like botocore's ClientError for a 412."""

    def __init__(self) -> None:
        super().__init__("At least one of the pre-conditions you specified did not hold")
        self.response = {
            "Error": {"Code": "PreconditionFailed"},
            "ResponseMetadata": {"HTTPStatusCode": 412},
        }


class NotFound(Exception):
    """Shaped like botocore's ClientError for a 404."""

    def __init__(self) -> None:
        super().__init__("Not Found")
        self.response = {
            "Error": {"Code": "404"},
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }


class FakeS3:
    """Versioned, because the audit sink's guarantees depend on versioning.

    Object Lock protects versions rather than the current-version view, so a
    delete marker hides an entry and an overwrite serves different bytes while
    the original survives underneath. A double without versions cannot express
    either, and both were only found by running against a real implementation.
    """

    def __init__(self, *, page_size: int = 1000) -> None:
        self.objects: dict[str, bytes] = {}
        self.page_size = page_size
        self.rejected = 0
        #: key -> [(version_id, body)], oldest first.
        self.versions: dict[str, list[tuple[str, bytes]]] = {}
        #: keys currently hidden by a delete marker.
        self.delete_markers: set[str] = set()
        self._version_counter = 0

    def put_object(self, **kw: Any) -> dict[str, Any]:
        key = kw["Key"]
        if kw.get("IfNoneMatch") == "*" and key in self.objects:
            self.rejected += 1
            raise PreconditionFailed()
        self._version_counter += 1
        version_id = f"v{self._version_counter:06d}"
        self.versions.setdefault(key, []).append((version_id, kw["Body"]))
        self.delete_markers.discard(key)
        self.objects[key] = kw["Body"]
        return {"VersionId": version_id}

    def get_object(self, **kw: Any) -> dict[str, Any]:  # noqa: C901
        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        key = kw["Key"]
        if version_id := kw.get("VersionId"):
            for stored_id, body in self.versions.get(key, []):
                if stored_id == version_id:
                    return {"Body": _Body(body)}
            raise NotFound()
        if key not in self.objects:
            raise NotFound()
        return {"Body": _Body(self.objects[key])}

    def head_object(self, **kw: Any) -> dict[str, Any]:
        if kw["Key"] not in self.objects:
            raise NotFound()
        return {"ContentLength": len(self.objects[kw["Key"]])}

    def delete_object(self, **kw: Any) -> dict[str, Any]:
        """A delete marker, not a destruction — which is what real S3 does.

        Object Lock refuses a versioned delete; an unversioned one is accepted
        and merely hides the key from `list_objects_v2`.
        """
        key = kw["Key"]
        if kw.get("VersionId"):
            raise PreconditionFailed()  # Object Lock refuses a versioned delete.
        if key in self.objects:
            self.delete_markers.add(key)
            self.objects.pop(key, None)
        return {}

    def list_object_versions(self, **kw: Any) -> dict[str, Any]:
        prefix = kw.get("Prefix", "")
        out = []
        for key, items in sorted(self.versions.items()):
            if not key.startswith(prefix):
                continue
            for order, (version_id, _) in enumerate(items):
                out.append({"Key": key, "VersionId": version_id, "LastModified": order})
        return {"Versions": out, "IsTruncated": False}

    def list_objects_v2(self, **kw: Any) -> dict[str, Any]:
        keys = sorted(k for k in self.objects if k.startswith(kw.get("Prefix", "")))
        start = 0
        if token := kw.get("ContinuationToken"):
            start = keys.index(token)
        page = keys[start : start + self.page_size]
        truncated = start + self.page_size < len(keys)
        out: dict[str, Any] = {
            "Contents": [{"Key": k} for k in page],
            "IsTruncated": truncated,
        }
        if truncated:
            out["NextContinuationToken"] = keys[start + self.page_size]
        return out
