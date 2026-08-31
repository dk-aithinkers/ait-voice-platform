"""The compliance core is P3, and it must hold from Bolt 1.

The audit-log design here resolves a contradiction two reviewers found
independently at practices discovery: retention and erasure obligations that
cannot both hold for the same bytes, unless the retained log carries no personal
data. These tests exercise that separation as a property, not as a convention.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ait_voice.core.audit import (
    AuditEvent,
    AuditIntegrityError,
    AuditLog,
    ContentStore,
    caller_ref,
)
from ait_voice.core.consent import (
    INDIA_CONSENT_VALIDITY,
    ConsentDenied,
    ConsentLedger,
    ConsentPurpose,
    may_place_outbound_call,
)
from ait_voice.core.types import PHI, Region, TenantContext


def _us(**kw) -> TenantContext:
    return TenantContext(tenant_id="clinic-us", region=Region.US, **kw)


def _india(**kw) -> TenantContext:
    return TenantContext(tenant_id="clinic-in", region=Region.INDIA, **kw)


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(root=tmp_path / "audit")


@pytest.fixture
def content(tmp_path: Path) -> ContentStore:
    return ContentStore(root=tmp_path / "content")


class TestAuditLogCarriesNoPersonalData:
    def test_phi_in_detail_is_refused(self, audit: AuditLog) -> None:
        with pytest.raises(AuditIntegrityError, match="is PHI"):
            audit.record(
                _us(), AuditEvent.CALL_STARTED, patient=PHI("Priya Sharma")
            )

    def test_long_strings_are_refused_as_content(self, audit: AuditLog) -> None:
        """A long string is content, whatever it is called."""
        with pytest.raises(AuditIntegrityError, match="content"):
            audit.record(
                _us(),
                AuditEvent.TURN_COMPLETED,
                note="the caller said they had been experiencing symptoms since Tuesday",
            )

    def test_non_scalar_detail_is_refused(self, audit: AuditLog) -> None:
        with pytest.raises(AuditIntegrityError, match="only scalars"):
            audit.record(_us(), AuditEvent.CALL_STARTED, turns=[1, 2, 3])

    def test_identifiers_and_codes_are_accepted(self, audit: AuditLog) -> None:
        entry = audit.record(
            _us(),
            AuditEvent.TURN_COMPLETED,
            call_id="c-1",
            caller_ref="caller-abc123",
            turn=2,
            latency_ms=880.5,
            met_target=True,
            outcome="booked",
        )
        assert entry.detail["turn"] == 2

    def test_a_written_log_contains_no_patient_data(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        """The property that matters, asserted against the bytes on disk."""
        tenant = _us()
        ref = caller_ref("+15551234567", tenant_id=tenant.tenant_id)

        audit.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1", caller_ref=ref)
        audit.record(tenant, AuditEvent.ESCALATED, call_id="c-1", reason="clinical")

        raw = (tmp_path / "audit" / "us" / "clinic-us.jsonl").read_text()
        assert "+15551234567" not in raw
        assert "5551234567" not in raw
        assert ref in raw


class TestCallerReference:
    def test_is_stable_for_the_same_number(self) -> None:
        a = caller_ref("+15551234567", tenant_id="t1")
        b = caller_ref("+15551234567", tenant_id="t1")
        assert a == b

    def test_does_not_contain_the_number(self) -> None:
        assert "5551234567" not in caller_ref("+15551234567", tenant_id="t1")

    def test_differs_across_tenants(self) -> None:
        """One tenant's log must not be correlatable against another's."""
        assert caller_ref("+15551234567", tenant_id="t1") != caller_ref(
            "+15551234567", tenant_id="t2"
        )


class TestAuditLogIntegrity:
    def test_chain_verifies_when_untouched(self, audit: AuditLog) -> None:
        tenant = _us()
        for i in range(4):
            audit.record(tenant, AuditEvent.TURN_COMPLETED, call_id="c-1", turn=i)

        assert audit.verify(tenant) is True

    def test_tampering_with_an_entry_is_detected(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        tenant = _us()
        audit.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1")
        audit.record(tenant, AuditEvent.CALL_ENDED, call_id="c-1", turns=3)

        path = tmp_path / "audit" / "us" / "clinic-us.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["detail"]["turns"] = 99
        path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")

        assert audit.verify(tenant) is False

    def test_removing_an_entry_is_detected(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        """Append-only means a deletion must not go unnoticed."""
        tenant = _us()
        for i in range(3):
            audit.record(tenant, AuditEvent.TURN_COMPLETED, call_id="c-1", turn=i)

        path = tmp_path / "audit" / "us" / "clinic-us.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join([lines[0], lines[2]]) + "\n")

        assert audit.verify(tenant) is False

    def test_entries_are_region_partitioned(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        """Region determines retention and residency; trees never mix."""
        audit.record(_us(), AuditEvent.CALL_STARTED)
        audit.record(_india(), AuditEvent.CALL_STARTED)

        assert (tmp_path / "audit" / "us" / "clinic-us.jsonl").exists()
        assert (tmp_path / "audit" / "india" / "clinic-in.jsonl").exists()


class TestRetentionAndErasureCoexist:
    """The contradiction, resolved.

    India requires security logs kept a year AND personal data erased when its
    purpose ends. Both hold here because they apply to different files.
    """

    def test_erasing_content_leaves_the_audit_record(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        transcript = [PHI("I'd like to book"), PHI("Tuesday please")]

        content.store(tenant, "c-1", transcript, audit=audit)
        assert content.exists(tenant, "c-1")

        content.erase(tenant, "c-1", audit=audit)

        assert not content.exists(tenant, "c-1"), "content must be gone"
        events = [row["event"] for row in audit.read(tenant)]
        assert "content_stored" in events
        assert "content_erased" in events, "the security record must survive erasure"

    def test_the_audit_entry_of_storage_holds_no_transcript(
        self, audit: AuditLog, content: ContentStore, tmp_path: Path
    ) -> None:
        tenant = _india()
        content.store(tenant, "c-1", [PHI("my name is Priya Sharma")], audit=audit)

        raw = (tmp_path / "audit" / "india" / "clinic-in.jsonl").read_text()
        assert "Priya" not in raw
        assert "turn_count" in raw, "it records how much, not what"

    def test_erasing_absent_content_is_recorded_honestly(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        assert content.erase(tenant, "never-existed", audit=audit) is False

        entry = next(r for r in audit.read(tenant) if r["event"] == "content_erased")
        assert entry["detail"]["existed"] is False

    def test_chain_still_verifies_after_erasure(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        content.store(tenant, "c-1", [PHI("hello")], audit=audit)
        content.erase(tenant, "c-1", audit=audit)

        assert audit.verify(tenant) is True


class TestConsentExpiry:
    def test_india_consent_expires_after_seven_days(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        granted = datetime(2026, 1, 1, tzinfo=UTC)

        ledger.grant(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted
        )

        assert ledger.is_valid(
            tenant,
            "caller-1",
            ConsentPurpose.APPOINTMENT_REMINDER,
            now=granted + timedelta(days=6, hours=23),
        )
        assert not ledger.is_valid(
            tenant,
            "caller-1",
            ConsentPurpose.APPOINTMENT_REMINDER,
            now=granted + timedelta(days=7, seconds=1),
        )

    def test_the_validity_window_is_exactly_seven_days(self) -> None:
        assert INDIA_CONSENT_VALIDITY == timedelta(days=7)

    def test_us_consent_has_no_clock_expiry(self) -> None:
        ledger = ConsentLedger()
        tenant = _us()
        granted = datetime(2020, 1, 1, tzinfo=UTC)

        consent = ledger.grant(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted
        )

        assert consent.expires_at is None
        assert consent.is_valid(now=granted + timedelta(days=3650))

    def test_consent_is_per_purpose(self) -> None:
        """Consent to a reminder is not consent to anything else."""
        ledger = ConsentLedger()
        tenant = _us()
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        assert ledger.is_valid(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)
        assert not ledger.is_valid(tenant, "caller-1", ConsentPurpose.CLINICAL_FOLLOW_UP)

    def test_revocation_is_available_everywhere(self) -> None:
        ledger = ConsentLedger()
        tenant = _us()
        ledger.grant(tenant, "caller-1", ConsentPurpose.CALL_RECORDING)

        assert ledger.revoke(tenant, "caller-1", ConsentPurpose.CALL_RECORDING)
        assert not ledger.is_valid(tenant, "caller-1", ConsentPurpose.CALL_RECORDING)

    def test_remaining_time_is_reported_for_india(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        granted = datetime(2026, 1, 1, tzinfo=UTC)
        consent = ledger.grant(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted
        )

        assert consent.remaining(now=granted + timedelta(days=2)) == timedelta(days=5)
        assert consent.remaining(now=granted + timedelta(days=99)) == timedelta(0)


class TestOutboundGate:
    def test_unregistered_india_tenant_cannot_call_even_with_consent(self) -> None:
        """Registration is a precondition, not a task. Consent does not substitute."""
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=False)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        with pytest.raises(ConsentDenied, match="DLT registration"):
            may_place_outbound_call(
                tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger
            )

    def test_registered_india_tenant_with_fresh_consent_may_call(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        may_place_outbound_call(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger
        )

    def test_expired_consent_blocks_the_call(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        granted = datetime(2026, 1, 1, tzinfo=UTC)
        ledger.grant(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted
        )

        with pytest.raises(ConsentDenied, match="expired"):
            may_place_outbound_call(
                tenant,
                "caller-1",
                ConsentPurpose.APPOINTMENT_REMINDER,
                ledger,
                now=granted + timedelta(days=8),
            )

    def test_absent_consent_blocks_the_call(self) -> None:
        ledger = ConsentLedger()
        with pytest.raises(ConsentDenied, match="no consent recorded"):
            may_place_outbound_call(
                _us(), "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger
            )

    def test_us_tenant_is_not_gated_on_dlt_registration(self) -> None:
        """DLT is an Indian obligation. It must not leak into the US path."""
        ledger = ConsentLedger()
        tenant = _us(outbound_registered=False)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        may_place_outbound_call(
            tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger
        )
