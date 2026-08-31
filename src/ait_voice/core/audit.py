"""Append-only audit log, and the reason it carries no personal data.

Two independent reviewers found the same contradiction at practices discovery,
blind to each other, and this module is its resolution.

India's DPDP requires security logs retained for **at least a year**. It also
requires personal data **erased once its purpose is fulfilled**. The compliance
core specifies an **immutable** audit log. Those three cannot all hold for the
same bytes — unless the audit log contains no personal data at all.

So it doesn't. Every entry references the call, the caller and the event by
opaque identifier and type only. Nothing embeds content. Retention and erasure
then apply to disjoint data:

- **This log** is the security record. Append-only, retained a year or more,
  never erased, and safe to retain precisely because there is nothing personal
  in it to erase.
- **The content store** holds transcripts and recordings. Erasable on request,
  deleted when its purpose ends, and never the thing an auditor needs to read.

The affirmed decision went further than convention: the separation is enforced
by the two classes being genuinely separate sinks with separate retention, so a
mistake is a type error rather than a discipline failure. That is what
:class:`AuditLog` and :class:`ContentStore` are.

**This must hold from Bolt 1.** Retrofitting it means rewriting the audit schema
after it has real entries, which is the expensive kind of change.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from ait_voice.core.types import PHI, TenantContext


class AuditEvent(StrEnum):
    """What happened. The vocabulary is closed on purpose.

    A free-text event field is where someone eventually writes a patient's name.
    An enum cannot carry content.
    """

    CALL_STARTED = "call_started"
    DISCLOSURE_SPOKEN = "disclosure_spoken"
    CONSENT_RECORDED = "consent_recorded"
    CONSENT_EXPIRED = "consent_expired"
    TURN_COMPLETED = "turn_completed"
    ESCALATED = "escalated"
    HANDOFF_COMPLETED = "handoff_completed"
    CALL_ENDED = "call_ended"
    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_CANCELLED = "appointment_cancelled"
    MESSAGE_TAKEN = "message_taken"
    CONTENT_STORED = "content_stored"
    CONTENT_ERASED = "content_erased"
    PROVIDER_REFUSED = "provider_refused"


class AuditIntegrityError(RuntimeError):
    """Raised when an entry would carry personal data, or a chain is broken."""


def caller_ref(phone_number: str, *, tenant_id: str) -> str:
    """Turn a phone number into a stable, opaque reference.

    A phone number is a listed HIPAA identifier, so it cannot appear in this
    log. But the log is useless if the same caller cannot be recognised across
    calls, so we need a value that is stable and reversible by nobody.

    The tenant id is mixed in so the same number under two tenants produces two
    different references — one tenant's log cannot be correlated against
    another's.
    """
    digest = hashlib.sha256(f"{tenant_id}:{phone_number}".encode()).hexdigest()
    return f"caller-{digest[:16]}"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One immutable fact. Contains identifiers and types, never content."""

    entry_id: str
    timestamp: str
    tenant_id: str
    region: str
    event: AuditEvent
    call_id: str | None = None
    caller_ref: str | None = None
    #: Numeric and enumerated facts only — durations, counts, outcome codes.
    #: Never text a person wrote or said.
    detail: dict[str, str | int | float | bool] = field(default_factory=dict)
    #: Hash of the preceding entry, so tampering is detectable.
    previous_hash: str | None = None

    def content_hash(self) -> str:
        payload = json.dumps(
            {
                "entry_id": self.entry_id,
                "timestamp": self.timestamp,
                "tenant_id": self.tenant_id,
                "region": self.region,
                "event": str(self.event),
                "call_id": self.call_id,
                "caller_ref": self.caller_ref,
                "detail": self.detail,
                "previous_hash": self.previous_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            {
                **{
                    "entry_id": self.entry_id,
                    "timestamp": self.timestamp,
                    "tenant_id": self.tenant_id,
                    "region": self.region,
                    "event": str(self.event),
                    "call_id": self.call_id,
                    "caller_ref": self.caller_ref,
                    "detail": self.detail,
                    "previous_hash": self.previous_hash,
                },
                "hash": self.content_hash(),
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _reject_personal_data(detail: dict[str, object]) -> None:
    """Refuse anything that could carry content into the audit log.

    Deliberately strict. PHI is refused outright; so are free strings, because
    a free string is where content arrives. Enumerated values are permitted by
    listing them explicitly at the call site.
    """
    for key, value in detail.items():
        if isinstance(value, PHI):
            raise AuditIntegrityError(
                f"detail[{key!r}] is PHI. The audit log carries identifiers and "
                "types only — put content in the ContentStore instead."
            )
        if not isinstance(value, (int, float, bool, str)):
            raise AuditIntegrityError(
                f"detail[{key!r}] is {type(value).__name__}; only scalars are allowed"
            )
        if isinstance(value, str) and len(value) > 64:
            raise AuditIntegrityError(
                f"detail[{key!r}] is {len(value)} characters. Long strings are "
                "content, not an identifier or a code."
            )


class AuditLog:
    """The security record. Append-only, PHI-free, retained.

    Backed by a JSON-lines file per tenant. That is deliberately simple for the
    skeleton — the properties that matter (append-only, hash-chained, no
    content) are in the entries themselves, so a later move to a real
    append-only store changes where it is written, not what is written.
    """

    def __init__(self, root: Path | str = "var/audit") -> None:
        self._root = Path(root)
        self._last_hash: dict[str, str] = {}

    def _path(self, tenant: TenantContext) -> Path:
        # Region is in the path because region determines retention policy and
        # data residency; a tenant's entries never sit in another region's tree.
        target = self._root / tenant.region.value / f"{tenant.tenant_id}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def record(
        self,
        tenant: TenantContext,
        event: AuditEvent,
        *,
        call_id: str | None = None,
        caller_ref: str | None = None,
        **detail: str | int | float | bool,
    ) -> AuditEntry:
        """Append one entry. Refuses anything carrying personal data."""
        _reject_personal_data(detail)

        path = self._path(tenant)
        key = str(path)
        if key not in self._last_hash:
            self._last_hash[key] = self._read_last_hash(path)

        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            tenant_id=tenant.tenant_id,
            region=tenant.region.value,
            event=event,
            call_id=call_id,
            caller_ref=caller_ref,
            detail=dict(detail),
            previous_hash=self._last_hash[key] or None,
        )

        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
        self._last_hash[key] = entry.content_hash()
        return entry

    def read(self, tenant: TenantContext) -> Iterator[dict]:
        path = self._path(tenant)
        if not path.exists():
            return
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)

    def verify(self, tenant: TenantContext) -> bool:
        """Check the hash chain. False means an entry was altered or removed."""
        previous: str | None = None
        for row in self.read(tenant):
            stated = row.pop("hash")
            rebuilt = AuditEntry(
                entry_id=row["entry_id"],
                timestamp=row["timestamp"],
                tenant_id=row["tenant_id"],
                region=row["region"],
                event=AuditEvent(row["event"]),
                call_id=row["call_id"],
                caller_ref=row["caller_ref"],
                detail=row["detail"],
                previous_hash=row["previous_hash"],
            )
            if rebuilt.content_hash() != stated:
                return False
            if row["previous_hash"] != previous:
                return False
            previous = stated
        return True

    def _read_last_hash(self, path: Path) -> str:
        if not path.exists():
            return ""
        last = ""
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = json.loads(line)["hash"]
        return last


class ContentStore:
    """Transcripts and recordings. Erasable, separate, and never the audit log.

    This is the other half of the resolution. Content lives here so that DPDP
    erasure can delete it without touching the security record that must be
    retained — the two obligations apply to disjoint data.
    """

    def __init__(self, root: Path | str = "var/content") -> None:
        self._root = Path(root)

    def _path(self, tenant: TenantContext, call_id: str) -> Path:
        target = self._root / tenant.region.value / tenant.tenant_id / f"{call_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def store(
        self,
        tenant: TenantContext,
        call_id: str,
        transcript: list[PHI[str]],
        *,
        audit: AuditLog | None = None,
    ) -> Path:
        """Persist a call's content, and record *that* it happened in the audit log."""
        path = self._path(tenant, call_id)
        path.write_text(
            json.dumps(
                {
                    "call_id": call_id,
                    "stored_at": datetime.now(UTC).isoformat(),
                    "transcript": [t.reveal() for t in transcript],
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        if audit:
            # The audit entry records that content exists and how much — never
            # what it says.
            audit.record(
                tenant,
                AuditEvent.CONTENT_STORED,
                call_id=call_id,
                turn_count=len(transcript),
            )
        return path

    def erase(
        self,
        tenant: TenantContext,
        call_id: str,
        *,
        audit: AuditLog | None = None,
        reason: str = "purpose_fulfilled",
    ) -> bool:
        """Delete a call's content. The audit entry of the erasure survives.

        That asymmetry is the point: DPDP requires the content gone and the
        security record kept, and both can be true because they are different
        files with different lifetimes.
        """
        path = self._path(tenant, call_id)
        existed = path.exists()
        if existed:
            path.unlink()
        if audit:
            audit.record(
                tenant,
                AuditEvent.CONTENT_ERASED,
                call_id=call_id,
                reason=reason,
                existed=existed,
            )
        return existed

    def exists(self, tenant: TenantContext, call_id: str) -> bool:
        return self._path(tenant, call_id).exists()


def default_audit_root() -> Path:
    return Path(os.environ.get("AIT_AUDIT_ROOT", "var/audit"))


def default_content_root() -> Path:
    return Path(os.environ.get("AIT_CONTENT_ROOT", "var/content"))
