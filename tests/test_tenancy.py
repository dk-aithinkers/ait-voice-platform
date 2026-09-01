"""Multi-tenancy, and the isolation tests that are the point of it.

With PHI in scope a missing tenant filter is a cross-tenant patient-data
disclosure rather than a wrong answer, so the isolation tests below are written
as adversarially as the API allows: they try to reach another tenant's data and
assert they cannot.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest

from ait_voice.core.tenancy import (
    CrossTenantAccessError,
    OutOfHoursPolicy,
    StaffedHours,
    TenantConfig,
    TenantNotFoundError,
    TenantScoped,
    TenantStore,
    assert_same_tenant,
)
from ait_voice.core.types import PHI, Region


def _config(tenant_id: str = "northside", region: Region = Region.US, **kw) -> TenantConfig:
    return TenantConfig(tenant_id=tenant_id, region=region, clinic_name="Northside Medical", **kw)


class TestTenantIsolation:
    """The property the whole design exists for."""

    def test_one_tenant_cannot_read_another(self) -> None:
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()

        store.put(a, "call-1", "clinic A's data")

        assert store.get(a, "call-1") == "clinic A's data"
        assert store.get(b, "call-1") is None, "clinic B must not see clinic A's record"

    def test_same_key_holds_different_values_per_tenant(self) -> None:
        """Keys collide across tenants constantly — call ids, patient refs."""
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()

        store.put(a, "call-1", "A")
        store.put(b, "call-1", "B")

        assert store.get(a, "call-1") == "A"
        assert store.get(b, "call-1") == "B"

    def test_deleting_in_one_tenant_leaves_the_other(self) -> None:
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()
        store.put(a, "call-1", "A")
        store.put(b, "call-1", "B")

        store.delete(a, "call-1")

        assert store.get(a, "call-1") is None
        assert store.get(b, "call-1") == "B"

    def test_clearing_one_tenant_leaves_the_other(self) -> None:
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()
        store.put(a, "x", "A1")
        store.put(a, "y", "A2")
        store.put(b, "x", "B1")

        removed = store.clear(a)

        assert removed == 2
        assert store.count(a) == 0
        assert store.count(b) == 1

    def test_listing_returns_only_the_callers_tenant(self) -> None:
        """There is deliberately no accessor that returns every tenant's records."""
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()
        store.put(a, "1", "A1")
        store.put(b, "2", "B1")
        store.put(b, "3", "B2")

        assert store.keys(a) == ["1"]
        assert sorted(store.keys(b)) == ["2", "3"]
        assert store.values(a) == ["A1"]

    def test_phi_stays_within_its_tenant(self) -> None:
        store: TenantScoped[PHI[str]] = TenantScoped()
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()

        store.put(a, "patient", PHI("Priya Sharma"))

        assert store.get(b, "patient") is None
        assert store.values(b) == []

    def test_require_names_the_tenant_when_missing(self) -> None:
        store: TenantScoped[str] = TenantScoped()
        a = _config("clinic-a").context()

        with pytest.raises(KeyError, match="clinic-a"):
            store.require(a, "absent")

    def test_guard_rejects_a_mismatched_context(self) -> None:
        a = _config("clinic-a").context()
        b = _config("clinic-b").context()

        with pytest.raises(CrossTenantAccessError, match="clinic-b"):
            assert_same_tenant(a, b)

    def test_guard_permits_a_matching_context(self) -> None:
        a = _config("clinic-a").context()
        assert_same_tenant(a, _config("clinic-a").context())


class TestTenantStore:
    def test_resolve_returns_a_usable_context(self) -> None:
        store = TenantStore()
        store.add(_config("northside", region=Region.INDIA))

        context = store.resolve("northside")

        assert context.tenant_id == "northside"
        assert context.region is Region.INDIA

    def test_unknown_tenant_is_refused(self) -> None:
        with pytest.raises(TenantNotFoundError):
            TenantStore().resolve("nobody")

    def test_deactivated_tenant_stops_answering(self) -> None:
        store = TenantStore()
        store.add(_config("northside"))
        store.deactivate("northside")

        with pytest.raises(TenantNotFoundError, match="not active"):
            store.resolve("northside")

    def test_deactivation_does_not_delete(self) -> None:
        """Deleting a tenant would take its audit log with it."""
        store = TenantStore()
        store.add(_config("northside"))
        store.deactivate("northside")

        assert store.get("northside").active is False
        assert len(store) == 1

    def test_update_produces_a_new_config(self) -> None:
        store = TenantStore()
        original = store.add(_config("northside"))

        updated = store.update("northside", greeting="Good morning.")

        assert updated.greeting == "Good morning."
        assert original.greeting == "How can I help?", "configs are frozen"

    def test_tenants_can_be_listed_by_region(self) -> None:
        """Region drives vendor selection, so grouping by it is a real need."""
        store = TenantStore()
        store.add(_config("us-1", region=Region.US))
        store.add(_config("us-2", region=Region.US))
        store.add(_config("in-1", region=Region.INDIA))

        assert len(store.by_region(Region.US)) == 2
        assert len(store.by_region(Region.INDIA)) == 1

    def test_active_tenants_excludes_deactivated(self) -> None:
        store = TenantStore()
        store.add(_config("a"))
        store.add(_config("b"))
        store.deactivate("b")

        assert [c.tenant_id for c in store.active_tenants] == ["a"]


class TestTenantConfig:
    def test_empty_tenant_id_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="tenant_id"):
            TenantConfig(tenant_id="", region=Region.US, clinic_name="X")

    def test_at_least_one_language_is_required(self) -> None:
        with pytest.raises(ValueError, match="language"):
            _config(languages=())

    def test_context_carries_outbound_registration(self) -> None:
        """FR4.4 — the India outbound gate reads this."""
        context = _config(region=Region.INDIA, outbound_registered=True).context()
        assert context.outbound_registered is True

    def test_outbound_registration_defaults_off(self) -> None:
        assert _config().context().outbound_registered is False


class TestStaffedHours:
    def test_weekday_business_hours(self) -> None:
        hours = StaffedHours.weekdays()

        # Wednesday 2026-09-02 at 10:00 and at 20:00
        assert hours.is_staffed(datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
        assert not hours.is_staffed(datetime(2026, 9, 2, 20, 0, tzinfo=UTC))

    def test_weekend_is_unstaffed(self) -> None:
        hours = StaffedHours.weekdays()
        # Saturday 2026-09-05
        assert not hours.is_staffed(datetime(2026, 9, 5, 10, 0, tzinfo=UTC))

    def test_closing_time_is_exclusive(self) -> None:
        hours = StaffedHours.weekdays(closes=time(17, 0))
        assert hours.is_staffed(datetime(2026, 9, 2, 16, 59, tzinfo=UTC))
        assert not hours.is_staffed(datetime(2026, 9, 2, 17, 0, tzinfo=UTC))

    def test_never_staffed_is_the_safe_default_shape(self) -> None:
        """Assuming someone is there transfers callers into an empty room."""
        hours = StaffedHours.never()
        assert not hours.is_staffed(datetime(2026, 9, 2, 10, 0, tzinfo=UTC))


class TestEscalationRouting:
    def test_staffed_hours_route_to_the_number(self) -> None:
        config = _config(staffed_hours=StaffedHours.weekdays(), escalation_number="+15551230000")
        route = config.escalation_route(datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
        assert route == "+15551230000"

    def test_out_of_hours_routes_to_the_policy(self) -> None:
        config = _config(
            staffed_hours=StaffedHours.weekdays(),
            escalation_number="+15551230000",
            out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
        )
        route = config.escalation_route(datetime(2026, 9, 2, 22, 0, tzinfo=UTC))
        assert route is OutOfHoursPolicy.TAKE_MESSAGE

    def test_staffed_but_no_number_falls_back_to_the_policy(self) -> None:
        """A transfer target that does not exist is worse than admitting it."""
        config = _config(
            staffed_hours=StaffedHours.weekdays(),
            escalation_number=None,
            out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
        )
        route = config.escalation_route(datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
        assert route is OutOfHoursPolicy.TAKE_MESSAGE

    def test_transfer_anyway_is_available_for_round_the_clock_numbers(self) -> None:
        config = _config(
            staffed_hours=StaffedHours.never(),
            out_of_hours=OutOfHoursPolicy.TRANSFER_ANYWAY,
        )
        assert (
            config.escalation_route(datetime(2026, 9, 2, 3, 0, tzinfo=UTC))
            is OutOfHoursPolicy.TRANSFER_ANYWAY
        )


class TestTenantsAreIndependentlyConfigured:
    def test_two_clinics_differ_in_every_dimension_that_matters(self) -> None:
        store = TenantStore()
        store.add(
            _config(
                "us-clinic",
                region=Region.US,
                languages=("en",),
                staffed_hours=StaffedHours.weekdays(),
                out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
            )
        )
        store.add(
            _config(
                "in-clinic",
                region=Region.INDIA,
                languages=("en", "hi", "hi-en"),
                staffed_hours=StaffedHours.never(),
                out_of_hours=OutOfHoursPolicy.EXISTING_AFTER_HOURS,
                outbound_registered=True,
            )
        )

        us = store.get("us-clinic")
        india = store.get("in-clinic")

        assert us.region is not india.region
        assert "hi-en" in india.languages and "hi-en" not in us.languages
        assert india.context().outbound_registered
        assert not us.context().outbound_registered
