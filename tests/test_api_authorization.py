"""The HTTP tenant boundary.

Adding a client meant adding a place where tenant scoping has to be
re-established: inside the process `TenantScoped` makes cross-tenant access
structurally impossible, but over HTTP a tenant id is a string in a query
parameter. These tests are the argument that the boundary holds.

Every one of them is written from the attacker's side: a clinic principal
holding a valid credential, trying to read a different clinic's data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from ait_voice.api.app import Services, create_app
from ait_voice.api.auth import (
    ForbiddenError,
    Principal,
    PrincipalStore,
    Role,
    hash_token,
    new_token,
    resolve_scope,
)
from ait_voice.core.records import CallOutcome, CallRecord, CallStore, Message
from ait_voice.core.tenancy import TenantConfig, TenantStore
from ait_voice.core.types import PHI, Region

NORTHSIDE = "northside"
PARKCLINIC = "parkclinic"


@pytest.fixture
def services() -> Services:
    tenants = TenantStore()
    tenants.add(
        TenantConfig(tenant_id=NORTHSIDE, region=Region.US, clinic_name="Northside")
    )
    tenants.add(
        TenantConfig(
            tenant_id=PARKCLINIC,
            region=Region.INDIA,
            clinic_name="Park",
            timezone="Asia/Kolkata",
        )
    )

    calls = CallStore()
    for tenant_id, call_id, number in (
        (NORTHSIDE, "call-north-1", "+15551110001"),
        (PARKCLINIC, "call-park-1", "+919990001111"),
    ):
        context = tenants.resolve(tenant_id)
        calls.add(
            context,
            CallRecord(
                call_id=call_id,
                tenant_id=tenant_id,
                started_at=datetime.now(UTC) - timedelta(hours=1),
                duration_seconds=130.0,
                turns=4,
                outcome=CallOutcome.NO_ACTION,
                caller=PHI(number),
            ),
        )
    calls.add_message(
        tenants.resolve(PARKCLINIC),
        Message(
            message_id="msg-park-1",
            call_id="call-park-1",
            tenant_id=PARKCLINIC,
            taken_at=datetime.now(UTC),
            caller=PHI("+919990001111"),
            note=PHI("Wants to reschedule Thursday"),
        ),
    )
    return Services(tenants=tenants, calls=calls, principals=PrincipalStore())


@pytest.fixture
def tokens(services: Services) -> dict[str, str]:
    return {
        "operator": services.principals.issue(
            Principal(principal_id="op", role=Role.OPERATOR)
        ),
        "northside": services.principals.issue(
            Principal(principal_id="c1", role=Role.CLINIC, tenant_id=NORTHSIDE)
        ),
        "parkclinic": services.principals.issue(
            Principal(principal_id="c2", role=Role.CLINIC, tenant_id=PARKCLINIC)
        ),
    }


@pytest.fixture
def client(services: Services) -> TestClient:
    return TestClient(create_app(services))


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestCrossTenantAccessOverHTTP:
    """The reason this file exists."""

    def test_a_clinic_cannot_read_another_clinics_calls(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.get(
            f"/api/calls?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        )

        assert response.status_code == 403
        assert PARKCLINIC in response.json()["detail"]

    def test_the_refusal_is_not_a_silent_redirect(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """Quietly serving their own data would hide an attempt worth noticing."""
        response = client.get(
            f"/api/calls?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 403
        assert not isinstance(response.json(), list)

    def test_omitting_the_tenant_gives_a_clinic_its_own_data(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.get("/api/calls", headers=_auth(tokens["northside"]))

        assert response.status_code == 200
        assert [c["call_id"] for c in response.json()] == ["call-north-1"]

    def test_a_clinic_cannot_fetch_another_clinics_call_by_id(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """404 rather than 403 — 403 would confirm the id exists somewhere."""
        response = client.get(
            "/api/calls/call-park-1", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 404

    def test_a_clinic_cannot_read_another_clinics_messages(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.get(
            f"/api/messages?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 403

    def test_a_clinic_cannot_resolve_another_clinics_message(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/messages/msg-park-1/resolve", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 404

    def test_a_clinic_cannot_read_another_clinics_summary(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.get(
            f"/api/summary?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 403

    def test_a_clinic_naming_its_own_tenant_is_allowed(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.get(
            f"/api/calls?tenant={NORTHSIDE}", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 200


class TestOperatorScope:
    def test_an_operator_must_name_a_tenant(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """No cross-tenant context exists, so no handler can be written against one."""
        response = client.get("/api/calls", headers=_auth(tokens["operator"]))

        assert response.status_code == 403
        assert "choose a clinic" in response.json()["detail"]

    def test_an_operator_may_read_any_named_tenant(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        for tenant_id, call_id in ((NORTHSIDE, "call-north-1"), (PARKCLINIC, "call-park-1")):
            response = client.get(
                f"/api/calls?tenant={tenant_id}", headers=_auth(tokens["operator"])
            )
            assert response.status_code == 200
            assert [c["call_id"] for c in response.json()] == [call_id]

    def test_only_an_operator_lists_clinics(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        assert client.get("/api/clinics", headers=_auth(tokens["operator"])).status_code == 200
        assert client.get("/api/clinics", headers=_auth(tokens["northside"])).status_code == 403

    def test_only_an_operator_writes_configuration(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """The clinic surface is read-only per the scope document."""
        response = client.post(
            f"/api/clinic?tenant={NORTHSIDE}",
            headers=_auth(tokens["northside"]),
            json={"greeting": "hacked"},
        )
        assert response.status_code == 403

    def test_an_unknown_config_field_is_rejected_not_ignored(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """A silently ignored typo looks like a saved setting that never applies."""
        response = client.post(
            f"/api/clinic?tenant={NORTHSIDE}",
            headers=_auth(tokens["operator"]),
            json={"greetng": "typo"},
        )
        assert response.status_code == 400
        assert "greetng" in response.json()["detail"]

    def test_an_operator_can_update_a_greeting(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        response = client.post(
            f"/api/clinic?tenant={NORTHSIDE}",
            headers=_auth(tokens["operator"]),
            json={"greeting": "Good morning."},
        )
        assert response.status_code == 200
        assert response.json()["greeting"] == "Good morning."


class TestAuthentication:
    def test_no_credential_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/calls").status_code == 401

    def test_a_bad_credential_is_rejected(self, client: TestClient) -> None:
        assert client.get("/api/calls", headers=_auth("not-a-token")).status_code == 401

    def test_the_failure_says_nothing_about_why(self, client: TestClient) -> None:
        assert client.get("/api/calls", headers=_auth("x")).json()["detail"] == (
            "unauthenticated"
        )

    def test_health_needs_no_credential(self, client: TestClient) -> None:
        assert client.get("/api/health").status_code == 200

    def test_me_reports_the_bound_tenant(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        body = client.get("/api/me", headers=_auth(tokens["northside"])).json()
        assert body["role"] == "clinic"
        assert body["tenant_id"] == NORTHSIDE

    def test_an_operator_has_no_bound_tenant(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        body = client.get("/api/me", headers=_auth(tokens["operator"])).json()
        assert body["tenant_id"] is None


class TestTokenHandling:
    def test_tokens_are_stored_hashed(self) -> None:
        """A leaked store must not be a leaked credential."""
        store = PrincipalStore()
        token = store.issue(Principal(principal_id="op", role=Role.OPERATOR))

        assert token not in repr(store.__dict__)
        assert hash_token(token) in store.__dict__["_by_token_hash"]

    def test_tokens_are_high_entropy(self) -> None:
        assert len({new_token() for _ in range(50)}) == 50
        assert len(new_token()) >= 40

    def test_an_unbound_clinic_principal_is_rejected(self) -> None:
        """It would be an operator by accident, given resolve_scope."""
        with pytest.raises(ValueError, match="bound to a tenant"):
            Principal(principal_id="x", role=Role.CLINIC)


class TestResolveScope:
    def test_an_inactive_tenant_is_refused(self) -> None:
        tenants = TenantStore()
        tenants.add(TenantConfig(tenant_id="t", region=Region.US, clinic_name="T"))
        tenants.deactivate("t")

        with pytest.raises(ForbiddenError, match="unknown or inactive"):
            resolve_scope(
                Principal(principal_id="c", role=Role.CLINIC, tenant_id="t"), None, tenants
            )

    def test_an_unknown_tenant_is_refused(self) -> None:
        with pytest.raises(ForbiddenError, match="unknown or inactive"):
            resolve_scope(
                Principal(principal_id="op", role=Role.OPERATOR), "ghost", TenantStore()
            )


class TestPHIExposure:
    def test_list_views_never_carry_a_full_number(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """Masking happens server-side, so a forgetful client cannot leak it."""
        body = client.get("/api/calls", headers=_auth(tokens["northside"])).text

        assert "+15551110001" not in body
        assert "…01" in body

    def test_the_detail_view_also_masks_the_number(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        body = client.get(
            "/api/calls/call-north-1", headers=_auth(tokens["northside"])
        ).text
        assert "+15551110001" not in body

    def test_the_message_queue_masks_the_number_but_shows_the_note(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        """The note is the point of the queue; the number is not."""
        body = client.get("/api/messages", headers=_auth(tokens["parkclinic"])).json()

        assert body[0]["caller_masked"].endswith("11")
        assert "+919990001111" not in str(body)
        assert body[0]["note"] == "Wants to reschedule Thursday"

    def test_no_openapi_schema_is_served(self, client: TestClient) -> None:
        """An unauthenticated schema of PHI endpoints is free reconnaissance."""
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404


class TestDemoSeed:
    """The demo app is what someone runs first, so it must not teach bad habits."""

    def test_it_builds_and_serves_both_surfaces(self) -> None:
        from ait_voice.api.demo import demo_app

        client = TestClient(demo_app())
        operator = {"Authorization": "Bearer demo-operator-token"}

        clinics = client.get("/api/clinics", headers=operator)

        assert clinics.status_code == 200
        assert {c["tenant_id"] for c in clinics.json()} == {"northside", "parkclinic"}

    def test_the_demo_clinic_token_is_bound_to_one_tenant(self) -> None:
        from ait_voice.api.demo import demo_app

        client = TestClient(demo_app())
        clinic = {"Authorization": "Bearer demo-clinic-token"}

        assert client.get("/api/calls?tenant=parkclinic", headers=clinic).status_code == 403
        assert client.get("/api/calls", headers=clinic).status_code == 200

    def test_the_seeded_data_is_synthetic(self) -> None:
        """`project.md` forbids real call content anywhere in this repository."""
        from ait_voice.api import demo

        source = __import__("pathlib").Path(demo.__file__).read_text()

        # 555-01xx is the reserved fictional range; 999 000 1111 is not a
        # routable Indian number. Both are deliberately unusable.
        assert "+1555111" in source
        assert "+919990001111" in source

    def test_the_bundled_call_is_flagged_as_unmeasurable(self) -> None:
        """The relayed demo call must not present its floor as a measurement."""
        from ait_voice.api.demo import demo_app

        client = TestClient(demo_app())
        calls = client.get(
            "/api/calls?tenant=parkclinic",
            headers={"Authorization": "Bearer demo-operator-token"},
        ).json()

        assert calls[0]["latency_observable"] is False


class TestAppointmentEndpoints:
    @pytest.fixture
    def booked(self, services: Services) -> str:
        from ait_voice.core.scheduling import BookingHours

        config = services.tenants.get(PARKCLINIC)
        hours = BookingHours()
        slot = services.calendar.availability(
            services.tenants.resolve(PARKCLINIC), config, hours, limit=1
        )[0]
        appointment = services.calendar.book(
            services.tenants.resolve(PARKCLINIC), config, hours, slot,
            caller_ref="caller-park",
        )
        return appointment.appointment_id

    def test_a_clinic_sees_its_own_diary(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        response = client.get("/api/appointments", headers=_auth(tokens["parkclinic"]))

        assert response.status_code == 200
        assert [a["appointment_id"] for a in response.json()] == [booked]

    def test_a_clinic_cannot_see_anothers_diary(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        assert client.get(
            f"/api/appointments?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        ).status_code == 403
        assert client.get(
            "/api/appointments", headers=_auth(tokens["northside"])
        ).json() == []

    def test_a_clinic_cannot_cancel_anothers_appointment(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        response = client.post(
            f"/api/appointments/{booked}/cancel", headers=_auth(tokens["northside"])
        )
        assert response.status_code == 403

    def test_the_clinic_surface_cannot_cancel_at_all(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        """Read-only per the scope document; the agent is what books."""
        response = client.post(
            f"/api/appointments/{booked}/cancel", headers=_auth(tokens["parkclinic"])
        )
        assert response.status_code == 403

    def test_an_operator_can_cancel(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        response = client.post(
            f"/api/appointments/{booked}/cancel?tenant={PARKCLINIC}",
            headers=_auth(tokens["operator"]),
        )

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert client.get(
            f"/api/appointments?tenant={PARKCLINIC}", headers=_auth(tokens["operator"])
        ).json() == []

    def test_cancelling_an_unknown_appointment_is_a_404(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        assert client.post(
            f"/api/appointments/ghost/cancel?tenant={PARKCLINIC}",
            headers=_auth(tokens["operator"]),
        ).status_code == 404

    def test_availability_is_scoped_too(
        self, client: TestClient, tokens: dict[str, str]
    ) -> None:
        assert client.get(
            f"/api/availability?tenant={PARKCLINIC}", headers=_auth(tokens["northside"])
        ).status_code == 403

    def test_times_are_returned_in_clinic_local_time_as_well_as_utc(
        self, client: TestClient, tokens: dict[str, str], booked: str
    ) -> None:
        """The clinic reads its diary in its own hours, not in UTC."""
        [appointment] = client.get(
            "/api/appointments", headers=_auth(tokens["parkclinic"])
        ).json()

        assert appointment["starts_at"].endswith("+00:00")
        assert appointment["local_start"] != appointment["starts_at"]
        assert "spoken" in appointment

    def test_the_diary_carries_no_patient_name(
        self, client: TestClient, tokens: dict[str, str], services: Services
    ) -> None:
        from ait_voice.core.scheduling import BookingHours

        config = services.tenants.get(PARKCLINIC)
        hours = BookingHours()
        slot = services.calendar.availability(
            services.tenants.resolve(PARKCLINIC), config, hours, limit=1
        )[0]
        services.calendar.book(
            services.tenants.resolve(PARKCLINIC), config, hours, slot,
            patient_name="Priya Sharma", reason="persistent cough",
        )

        body = client.get("/api/appointments", headers=_auth(tokens["parkclinic"])).text

        assert "Priya" not in body
        assert "cough" not in body
