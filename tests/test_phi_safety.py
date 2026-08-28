"""The PHI controls are the reason this project can handle patient calls.

These tests exist because practices discovery established that automation
cannot cover redaction correctness at any tooling budget, and that a PHI
wrapper whose representation redacts is the control that converts the most
likely breach into a build failure. A control nobody tests is a control that
does not exist.
"""

from __future__ import annotations

import logging
from dataclasses import FrozenInstanceError

import pytest

from ait_voice.core.logging import CallLogger, PHILeakError, configure_logging
from ait_voice.core.types import PHI, REDACTED, Region, TenantContext


class TestPHIRedaction:
    def test_str_redacts(self) -> None:
        assert str(PHI("Priya Sharma")) == REDACTED

    def test_repr_redacts(self) -> None:
        assert repr(PHI("Priya Sharma")) == REDACTED

    def test_fstring_redacts(self) -> None:
        name = PHI("Priya Sharma")
        assert "Priya" not in f"caller is {name}"

    def test_format_spec_redacts(self) -> None:
        """f"{phi:>20}" must not bypass __str__ — it would call __format__."""
        name = PHI("Priya Sharma")
        assert "Priya" not in f"{name:>20}"

    def test_percent_formatting_redacts(self) -> None:
        assert "Priya" not in "caller is {}".format(PHI("Priya Sharma"))  # noqa: UP032

    def test_reveal_returns_the_value(self) -> None:
        assert PHI("Priya Sharma").reveal() == "Priya Sharma"

    def test_equality_compares_underlying(self) -> None:
        assert PHI("a") == PHI("a")
        assert PHI("a") != PHI("b")


class TestLoggingFacadeRefusesPHI:
    def test_direct_phi_field_is_refused(self) -> None:
        log = CallLogger("test")
        with pytest.raises(PHILeakError):
            log.info("caller identified", name=PHI("Priya Sharma"))

    def test_phi_nested_in_dict_is_refused(self) -> None:
        log = CallLogger("test")
        with pytest.raises(PHILeakError):
            log.info("intake", data={"dob": PHI("1985-04-12")})

    def test_phi_nested_in_list_is_refused(self) -> None:
        log = CallLogger("test")
        with pytest.raises(PHILeakError):
            log.info("utterances", turns=[PHI("hello"), PHI("goodbye")])

    def test_phi_in_base_fields_is_refused_at_construction(self) -> None:
        with pytest.raises(PHILeakError):
            CallLogger("test", caller=PHI("Priya Sharma"))

    def test_opaque_identifiers_are_allowed(self) -> None:
        log = CallLogger("test")
        log.info("call started", call_id="c-123", turn=1)  # must not raise

    def test_for_call_logs_only_identifiers(self) -> None:
        tenant = TenantContext(tenant_id="clinic-1", region=Region.US)
        log = CallLogger.for_call("test", tenant, "call-9")
        log.info("ok")  # tenant_id, region and call_id are all opaque


class TestThirdPartyLoggersArePinned:
    def test_vendor_loggers_do_not_emit_debug(self) -> None:
        """A vendor SDK debug-logging a request body would log a transcript."""
        configure_logging("DEBUG")
        for name in ("anthropic", "httpx", "deepgram", "twilio"):
            assert logging.getLogger(name).level >= logging.WARNING


class TestTenantContext:
    def test_empty_tenant_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="tenant_id"):
            TenantContext(tenant_id="", region=Region.US)

    def test_us_region_is_a_phi_jurisdiction(self) -> None:
        assert TenantContext(tenant_id="c", region=Region.US).is_phi_jurisdiction

    def test_india_region_is_not_a_hipaa_jurisdiction(self) -> None:
        assert not TenantContext(tenant_id="c", region=Region.INDIA).is_phi_jurisdiction

    def test_outbound_registration_defaults_off(self) -> None:
        """FR4.4 — outbound is blocked until registration is recorded complete."""
        assert TenantContext(tenant_id="c", region=Region.INDIA).outbound_registered is False

    def test_context_is_frozen(self) -> None:
        tenant = TenantContext(tenant_id="c", region=Region.US)
        with pytest.raises(FrozenInstanceError):
            tenant.tenant_id = "other"  # type: ignore[misc]
