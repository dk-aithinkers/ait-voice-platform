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
    default_audit_root,
    default_content_root,
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
    async def test_phi_in_detail_is_refused(self, audit: AuditLog) -> None:
        with pytest.raises(AuditIntegrityError, match="is PHI"):
            # Deliberately the wrong type — the guard refusing it is the test.
            await audit.record(
                _us(),
                AuditEvent.CALL_STARTED,
                patient=PHI("Priya Sharma"),  # type: ignore[arg-type]
            )

    async def test_long_strings_are_refused_as_content(self, audit: AuditLog) -> None:
        """A long string is content, whatever it is called."""
        with pytest.raises(AuditIntegrityError, match="content"):
            await audit.record(
                _us(),
                AuditEvent.TURN_COMPLETED,
                note="the caller said they had been experiencing symptoms since Tuesday",
            )

    async def test_non_scalar_detail_is_refused(self, audit: AuditLog) -> None:
        with pytest.raises(AuditIntegrityError, match="only scalars"):
            # A non-scalar, refused by design.
            await audit.record(_us(), AuditEvent.CALL_STARTED, turns=[1, 2, 3])  # type: ignore[arg-type]

    async def test_identifiers_and_codes_are_accepted(self, audit: AuditLog) -> None:
        entry = await audit.record(
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

    async def test_a_written_log_contains_no_patient_data(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        """The property that matters, asserted against the bytes on disk."""
        tenant = _us()
        ref = caller_ref("+15551234567", tenant_id=tenant.tenant_id)

        await audit.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1", caller_ref=ref)
        await audit.record(tenant, AuditEvent.ESCALATED, call_id="c-1", reason="clinical")

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
    async def test_chain_verifies_when_untouched(self, audit: AuditLog) -> None:
        tenant = _us()
        for i in range(4):
            await audit.record(tenant, AuditEvent.TURN_COMPLETED, call_id="c-1", turn=i)

        assert await audit.verify(tenant) is True

    async def test_tampering_with_an_entry_is_detected(
        self, audit: AuditLog, tmp_path: Path
    ) -> None:
        tenant = _us()
        await audit.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1")
        await audit.record(tenant, AuditEvent.CALL_ENDED, call_id="c-1", turns=3)

        path = tmp_path / "audit" / "us" / "clinic-us.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["detail"]["turns"] = 99
        path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")

        assert await audit.verify(tenant) is False

    async def test_removing_an_entry_is_detected(self, audit: AuditLog, tmp_path: Path) -> None:
        """Append-only means a deletion must not go unnoticed."""
        tenant = _us()
        for i in range(3):
            await audit.record(tenant, AuditEvent.TURN_COMPLETED, call_id="c-1", turn=i)

        path = tmp_path / "audit" / "us" / "clinic-us.jsonl"
        lines = path.read_text().splitlines()
        path.write_text("\n".join([lines[0], lines[2]]) + "\n")

        assert await audit.verify(tenant) is False

    async def test_entries_are_region_partitioned(self, audit: AuditLog, tmp_path: Path) -> None:
        """Region determines retention and residency; trees never mix."""
        await audit.record(_us(), AuditEvent.CALL_STARTED)
        await audit.record(_india(), AuditEvent.CALL_STARTED)

        assert (tmp_path / "audit" / "us" / "clinic-us.jsonl").exists()
        assert (tmp_path / "audit" / "india" / "clinic-in.jsonl").exists()


class TestRetentionAndErasureCoexist:
    """The contradiction, resolved.

    India requires security logs kept a year AND personal data erased when its
    purpose ends. Both hold here because they apply to different files.
    """

    async def test_erasing_content_leaves_the_audit_record(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        transcript = [PHI("I'd like to book"), PHI("Tuesday please")]

        await content.store(tenant, "c-1", transcript, audit=audit)
        assert await content.exists(tenant, "c-1")

        await content.erase(tenant, "c-1", audit=audit)

        assert not await content.exists(tenant, "c-1"), "content must be gone"
        events = [row["event"] for row in await audit.read(tenant)]
        assert "content_stored" in events
        assert "content_erased" in events, "the security record must survive erasure"

    async def test_the_audit_entry_of_storage_holds_no_transcript(
        self, audit: AuditLog, content: ContentStore, tmp_path: Path
    ) -> None:
        tenant = _india()
        await content.store(tenant, "c-1", [PHI("my name is Priya Sharma")], audit=audit)

        raw = (tmp_path / "audit" / "india" / "clinic-in.jsonl").read_text()
        assert "Priya" not in raw
        assert "turn_count" in raw, "it records how much, not what"

    async def test_erasing_absent_content_is_recorded_honestly(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        assert await content.erase(tenant, "never-existed", audit=audit) is False

        entry = next(r for r in await audit.read(tenant) if r["event"] == "content_erased")
        assert entry["detail"]["existed"] is False

    async def test_chain_still_verifies_after_erasure(
        self, audit: AuditLog, content: ContentStore
    ) -> None:
        tenant = _india()
        await content.store(tenant, "c-1", [PHI("hello")], audit=audit)
        await content.erase(tenant, "c-1", audit=audit)

        assert await audit.verify(tenant) is True


class TestConsentExpiry:
    def test_india_consent_expires_after_seven_days(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        granted = datetime(2026, 1, 1, tzinfo=UTC)

        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted)

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

        consent = ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted)

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
        consent = ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted)

        assert consent.remaining(now=granted + timedelta(days=2)) == timedelta(days=5)
        assert consent.remaining(now=granted + timedelta(days=99)) == timedelta(0)


class TestOutboundGate:
    def test_unregistered_india_tenant_cannot_call_even_with_consent(self) -> None:
        """Registration is a precondition, not a task. Consent does not substitute."""
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=False)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        with pytest.raises(ConsentDenied, match="DLT registration"):
            may_place_outbound_call(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger)

    def test_registered_india_tenant_with_fresh_consent_may_call(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        may_place_outbound_call(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger)

    def test_expired_consent_blocks_the_call(self) -> None:
        ledger = ConsentLedger()
        tenant = _india(outbound_registered=True)
        granted = datetime(2026, 1, 1, tzinfo=UTC)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, at=granted)

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
            may_place_outbound_call(_us(), "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger)

    def test_us_tenant_is_not_gated_on_dlt_registration(self) -> None:
        """DLT is an Indian obligation. It must not leak into the US path."""
        ledger = ConsentLedger()
        tenant = _us(outbound_registered=False)
        ledger.grant(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER)

        may_place_outbound_call(tenant, "caller-1", ConsentPurpose.APPOINTMENT_REMINDER, ledger)


class TestAuditChainSurvivesRestart:
    """The branch the per-package gate found: appending to an existing log.

    Every audit test until now built a fresh log in a fresh directory, so the
    resumption path — read the last hash off disk, chain onto it — had line
    coverage from `_read_last_hash`'s early return and no branch coverage at
    all. If it were broken, the chain would silently restart on every deploy,
    and an audit log whose chain restarts is not tamper-evident.
    """

    async def test_a_second_process_chains_onto_the_existing_log(self, tmp_path) -> None:  # noqa: ANN001
        tenant = TenantContext(tenant_id="northside", region=Region.US)

        first = AuditLog(root=tmp_path)
        await first.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1")
        await first.record(tenant, AuditEvent.CALL_ENDED, call_id="c-1")

        # A fresh instance, as after a restart — no in-memory hash to carry.
        second = AuditLog(root=tmp_path)
        await second.record(tenant, AuditEvent.CALL_STARTED, call_id="c-2")

        assert await second.verify(tenant), "the chain broke across a restart"
        assert len(await second.read(tenant)) == 3

    async def test_the_chain_links_across_the_restart_boundary(self, tmp_path) -> None:  # noqa: ANN001
        tenant = TenantContext(tenant_id="northside", region=Region.US)
        first = AuditLog(root=tmp_path)
        await first.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1")

        second = AuditLog(root=tmp_path)
        await second.record(tenant, AuditEvent.CALL_ENDED, call_id="c-1")

        entries = await second.read(tenant)
        assert entries[1]["previous_hash"] == entries[0]["hash"]

    async def test_a_blank_line_in_the_log_does_not_break_resumption(self, tmp_path) -> None:  # noqa: ANN001
        """Files acquire trailing newlines; that must not restart the chain."""
        tenant = TenantContext(tenant_id="northside", region=Region.US)
        first = AuditLog(root=tmp_path)
        await first.record(tenant, AuditEvent.CALL_STARTED, call_id="c-1")

        path = tmp_path / "us" / "northside.jsonl"
        path.write_text(path.read_text() + "\n")

        await AuditLog(root=tmp_path).record(tenant, AuditEvent.CALL_ENDED, call_id="c-1")

        assert await AuditLog(root=tmp_path).verify(tenant)

    async def test_reading_a_tenant_with_no_log_yields_nothing(self, tmp_path) -> None:  # noqa: ANN001
        """A clinic that has taken no calls is not an error."""
        tenant = TenantContext(tenant_id="brand-new", region=Region.US)

        assert await AuditLog(root=tmp_path).read(tenant) == []
        assert await AuditLog(root=tmp_path).verify(tenant) is True


class TestContentStoreWithoutAudit:
    """The audit log is optional on the content store, and both paths matter."""

    async def test_content_can_be_stored_without_an_audit_log(self, tmp_path) -> None:  # noqa: ANN001
        tenant = TenantContext(tenant_id="northside", region=Region.US)
        store = ContentStore(root=tmp_path)

        locator = await store.store(tenant, "c-1", [PHI("hello")])

        # A locator string, not a Path: the S3 store returns a URI, and a test
        # that could call .exists() on the result would pass against one
        # backend and not the other.
        # ASYNC240 wants an async path API. This is a test asserting on a
        # local temp file, not I/O on the request path.
        assert Path(locator).exists()  # noqa: ASYNC240
        assert await store.exists(tenant, "c-1")

    async def test_content_can_be_erased_without_an_audit_log(self, tmp_path) -> None:  # noqa: ANN001
        tenant = TenantContext(tenant_id="northside", region=Region.US)
        store = ContentStore(root=tmp_path)
        await store.store(tenant, "c-1", [PHI("hello")])

        assert await store.erase(tenant, "c-1") is True
        assert not await store.exists(tenant, "c-1")

    async def test_erasing_absent_content_reports_it_did_not_exist(self, tmp_path) -> None:  # noqa: ANN001
        """Recorded rather than swallowed: an erasure request for content that
        was already gone is a different fact from one that deleted something."""
        tenant = TenantContext(tenant_id="northside", region=Region.US)

        assert await ContentStore(root=tmp_path).erase(tenant, "never-existed") is False


class TestStorageRoots:
    def test_the_roots_default_to_var(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.delenv("AIT_AUDIT_ROOT", raising=False)
        monkeypatch.delenv("AIT_CONTENT_ROOT", raising=False)

        assert str(default_audit_root()) == "var/audit"
        assert str(default_content_root()) == "var/content"

    def test_the_roots_are_separately_overridable(self, monkeypatch) -> None:  # noqa: ANN001
        """They are two variables because their retention obligations are
        opposite; pointing both at one path collapses C-R7 against C-R8."""
        monkeypatch.setenv("AIT_AUDIT_ROOT", "/srv/audit")
        monkeypatch.setenv("AIT_CONTENT_ROOT", "/srv/content")

        assert str(default_audit_root()) == "/srv/audit"
        assert str(default_content_root()) == "/srv/content"
