"""The agent's own calendar (P7, FR2.1–FR2.5).

The load-bearing test is TestNoDoubleBooking: 24/7 answering with simultaneous
callers means two people asking for the same slot is the normal case, and a
calendar that only *usually* refuses the second one puts two patients in a room.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, time, timedelta

import pytest

from ait_voice.core.scheduling import (
    Appointment,
    AppointmentNotFound,
    AppointmentStatus,
    BookingHours,
    Calendar,
    SlotUnavailable,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region

#: Tuesday 2026-09-01, 12:00 UTC = 08:00 in New York.
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
#: Wednesday 10:30 New York.
WEDNESDAY_1030 = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)


def _config(tenant_id: str = "northside", timezone: str = "America/New_York") -> TenantConfig:
    return TenantConfig(
        tenant_id=tenant_id,
        region=Region.US,
        clinic_name="Northside Medical",
        timezone=timezone,
    )


@pytest.fixture
def config() -> TenantConfig:
    return _config()


@pytest.fixture
def hours() -> BookingHours:
    return BookingHours()


@pytest.fixture
def calendar() -> Calendar:
    return Calendar()


class TestBooking:
    def test_a_slot_can_be_booked(self, calendar, config, hours) -> None:
        appointment = calendar.book(
            config.context(), config, hours, WEDNESDAY_1030, now=NOW
        )

        assert appointment.status is AppointmentStatus.BOOKED
        assert appointment.starts_at == WEDNESDAY_1030
        assert appointment.duration_minutes == 30

    def test_it_is_persisted_against_the_clinic(self, calendar, config, hours) -> None:
        """The BDD criterion: persisted against that clinic and that caller."""
        appointment = calendar.book(
            config.context(), config, hours, WEDNESDAY_1030,
            caller_ref="caller-abc", call_id="c-1", now=NOW,
        )

        stored = calendar.get(config.context(), appointment.appointment_id)
        assert stored.caller_ref == "caller-abc"
        assert stored.call_id == "c-1"

    def test_the_time_is_read_back_in_clinic_local_time(self, calendar, config, hours) -> None:
        """FR2.4 — and 14:30 UTC must be spoken as half past ten, not half past two."""
        appointment = calendar.book(
            config.context(), config, hours, WEDNESDAY_1030, now=NOW
        )

        assert appointment.spoken(config) == "Wednesday 2 September at 10:30 am"

    def test_a_naive_datetime_is_refused(self, calendar, config, hours) -> None:
        """It would be read as UTC and book someone hours from where they meant."""
        with pytest.raises(ValueError, match="timezone-aware"):
            calendar.book(
                config.context(), config, hours,
                datetime(2026, 9, 2, 14, 30), now=NOW,
            )

    def test_phi_is_wrapped(self, calendar, config, hours) -> None:
        appointment = calendar.book(
            config.context(), config, hours, WEDNESDAY_1030,
            patient_name="Priya Sharma", reason="persistent cough", now=NOW,
        )

        assert isinstance(appointment.patient_name, PHI)
        assert "Priya" not in repr(appointment.patient_name)
        assert "cough" not in repr(appointment.reason)

    def test_the_summary_carries_no_phi(self, calendar, config, hours) -> None:
        """A diary view needs times, not names."""
        appointment = calendar.book(
            config.context(), config, hours, WEDNESDAY_1030,
            patient_name="Priya Sharma", reason="persistent cough", now=NOW,
        )

        assert "Priya" not in str(appointment.summary())
        assert "cough" not in str(appointment.summary())


class TestNoDoubleBooking:
    """Simultaneous callers are the normal case, not an edge case."""

    def test_the_second_booking_is_refused(self, calendar, config, hours) -> None:
        calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

        with pytest.raises(SlotUnavailable, match="already taken"):
            calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

    def test_concurrent_bookings_produce_exactly_one_winner(
        self, calendar, config, hours
    ) -> None:
        """The race that puts two patients in one room, run for real."""
        tenant = config.context()
        booked, refused = [], []

        def attempt(index: int) -> None:
            try:
                booked.append(
                    calendar.book(
                        tenant, config, hours, WEDNESDAY_1030,
                        caller_ref=f"caller-{index}", now=NOW,
                    )
                )
            except SlotUnavailable:
                refused.append(index)

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(attempt, range(16)))

        assert len(booked) == 1, "more than one caller was given the same slot"
        assert len(refused) == 15

    def test_a_cancelled_slot_becomes_free_again(self, calendar, config, hours) -> None:
        first = calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)
        calendar.cancel(config.context(), first.appointment_id)

        second = calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

        assert second.appointment_id != first.appointment_id


class TestAlternatives:
    def test_a_refusal_always_offers_alternatives(self, calendar, config, hours) -> None:
        """FR2.5, and the criterion forbidding a call that ends with neither."""
        calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

        with pytest.raises(SlotUnavailable) as refusal:
            calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

        assert refusal.value.alternatives
        assert WEDNESDAY_1030 not in refusal.value.alternatives

    def test_alternatives_are_nearest_not_merely_next(self, calendar, config, hours) -> None:
        """A caller who asked for Wednesday should not be offered three weeks out."""
        tenant = config.context()
        calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)

        offered = calendar.alternatives(tenant, config, hours, WEDNESDAY_1030, now=NOW)

        gaps = [abs(slot - WEDNESDAY_1030) for slot in offered]
        assert all(gap <= timedelta(hours=4) for gap in gaps)

    def test_a_closed_day_is_refused_with_alternatives(self, calendar, config, hours) -> None:
        saturday = datetime(2026, 9, 5, 14, 30, tzinfo=UTC)

        with pytest.raises(SlotUnavailable, match="not open") as refusal:
            calendar.book(config.context(), config, hours, saturday, now=NOW)

        assert refusal.value.alternatives

    def test_a_past_time_is_refused(self, calendar, config, hours) -> None:
        with pytest.raises(SlotUnavailable, match="in the past"):
            calendar.book(
                config.context(), config, hours,
                NOW - timedelta(days=1), now=NOW,
            )

    def test_beyond_the_horizon_is_refused(self, calendar, config, hours) -> None:
        """A phone agent should not commit a clinic's diary a year out."""
        with pytest.raises(SlotUnavailable, match="days ahead"):
            calendar.book(
                config.context(), config, hours,
                NOW + timedelta(days=200), now=NOW,
            )

    def test_an_off_grid_time_is_refused(self, calendar, config, hours) -> None:
        with pytest.raises(SlotUnavailable, match="half hour"):
            calendar.book(
                config.context(), config, hours,
                WEDNESDAY_1030 + timedelta(minutes=7), now=NOW,
            )


class TestRescheduling:
    def test_an_appointment_can_be_moved(self, calendar, config, hours) -> None:
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)

        moved = calendar.reschedule(
            tenant, config, hours, original.appointment_id,
            WEDNESDAY_1030 + timedelta(hours=2), now=NOW,
        )

        assert moved.status is AppointmentStatus.RESCHEDULED
        assert moved.previous_starts_at == WEDNESDAY_1030

    def test_the_old_slot_frees_up(self, calendar, config, hours) -> None:
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)
        calendar.reschedule(
            tenant, config, hours, original.appointment_id,
            WEDNESDAY_1030 + timedelta(hours=2), now=NOW,
        )

        assert calendar.is_free(tenant, WEDNESDAY_1030)

    def test_a_move_onto_a_taken_slot_is_refused_and_keeps_the_original(
        self, calendar, config, hours
    ) -> None:
        """The old slot must not free until the new one is actually taken."""
        tenant = config.context()
        first = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)
        second_time = WEDNESDAY_1030 + timedelta(hours=1)
        calendar.book(tenant, config, hours, second_time, now=NOW)

        with pytest.raises(SlotUnavailable):
            calendar.reschedule(
                tenant, config, hours, first.appointment_id, second_time, now=NOW
            )

        assert calendar.get(tenant, first.appointment_id).starts_at == WEDNESDAY_1030

    def test_moving_to_the_same_time_is_a_no_op(self, calendar, config, hours) -> None:
        """Otherwise it would collide with itself."""
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)

        same = calendar.reschedule(
            tenant, config, hours, original.appointment_id, WEDNESDAY_1030, now=NOW
        )

        assert same.status is AppointmentStatus.BOOKED

    def test_rescheduling_an_unknown_appointment_raises(self, calendar, config, hours) -> None:
        with pytest.raises(AppointmentNotFound):
            calendar.reschedule(
                config.context(), config, hours, "ghost", WEDNESDAY_1030, now=NOW
            )

    def test_a_cancelled_appointment_cannot_be_moved(self, calendar, config, hours) -> None:
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)
        calendar.cancel(tenant, original.appointment_id)

        with pytest.raises(AppointmentNotFound):
            calendar.reschedule(
                tenant, config, hours, original.appointment_id,
                WEDNESDAY_1030 + timedelta(hours=1), now=NOW,
            )


class TestCancelling:
    def test_cancelling_keeps_the_row(self, calendar, config, hours) -> None:
        """The clinic needs to know a cancellation happened, not just see a gap."""
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)

        cancelled = calendar.cancel(tenant, original.appointment_id)

        assert cancelled.status is AppointmentStatus.CANCELLED
        assert calendar.get(tenant, original.appointment_id) is not None
        assert cancelled not in calendar.active(tenant)

    def test_cancelling_twice_raises(self, calendar, config, hours) -> None:
        tenant = config.context()
        original = calendar.book(tenant, config, hours, WEDNESDAY_1030, now=NOW)
        calendar.cancel(tenant, original.appointment_id)

        with pytest.raises(AppointmentNotFound):
            calendar.cancel(tenant, original.appointment_id)


class TestCallerIdentification:
    def test_a_caller_finds_their_own_appointments(self, calendar, config, hours) -> None:
        tenant = config.context()
        mine = calendar.book(
            tenant, config, hours, WEDNESDAY_1030, caller_ref="caller-abc", now=NOW
        )
        calendar.book(
            tenant, config, hours, WEDNESDAY_1030 + timedelta(hours=1),
            caller_ref="caller-xyz", now=NOW,
        )

        found = calendar.for_caller(tenant, "caller-abc")

        assert [a.appointment_id for a in found] == [mine.appointment_id]

    def test_an_unknown_caller_gets_nothing_rather_than_everything(
        self, calendar, config, hours
    ) -> None:
        """An empty reference matching every appointment is how the wrong one
        gets cancelled."""
        tenant = config.context()
        calendar.book(tenant, config, hours, WEDNESDAY_1030, caller_ref="", now=NOW)

        assert calendar.for_caller(tenant, "") == []


class TestTenantIsolation:
    def test_one_clinic_cannot_see_anothers_diary(self, calendar, hours) -> None:
        north, park = _config("northside"), _config("parkclinic")
        calendar.book(north.context(), north, hours, WEDNESDAY_1030, now=NOW)

        assert len(calendar.active(north.context())) == 1
        assert calendar.active(park.context()) == []

    def test_the_same_slot_is_bookable_by_each_clinic(self, calendar, hours) -> None:
        """Two clinics are not competing for one room."""
        north, park = _config("northside"), _config("parkclinic")

        calendar.book(north.context(), north, hours, WEDNESDAY_1030, now=NOW)
        calendar.book(park.context(), park, hours, WEDNESDAY_1030, now=NOW)

        assert len(calendar.active(north.context())) == 1
        assert len(calendar.active(park.context())) == 1

    def test_one_clinic_cannot_cancel_anothers_appointment(self, calendar, hours) -> None:
        north, park = _config("northside"), _config("parkclinic")
        appointment = calendar.book(north.context(), north, hours, WEDNESDAY_1030, now=NOW)

        with pytest.raises(AppointmentNotFound):
            calendar.cancel(park.context(), appointment.appointment_id)

    def test_the_calendar_refuses_to_iterate_without_a_tenant(self, calendar) -> None:
        with pytest.raises(TypeError, match="tenant context"):
            list(calendar)


class TestBookingHours:
    def test_slots_are_generated_on_the_grid(self) -> None:
        hours = BookingHours(opens=time(9, 0), closes=time(11, 0), slot_minutes=30)
        day = datetime(2026, 9, 2, 0, 0)

        assert [s.strftime("%H:%M") for s in hours.slots_on(day)] == [
            "09:00", "09:30", "10:00", "10:30"
        ]

    def test_the_closing_slot_is_exclusive(self) -> None:
        """A 17:00 close must not book someone at 17:00."""
        hours = BookingHours(opens=time(16, 0), closes=time(17, 0))
        day = datetime(2026, 9, 2, 0, 0)

        assert [s.strftime("%H:%M") for s in hours.slots_on(day)] == ["16:00", "16:30"]

    def test_a_closed_day_yields_nothing(self) -> None:
        saturday = datetime(2026, 9, 5, 0, 0)
        assert BookingHours().slots_on(saturday) == []

    def test_invalid_hours_are_refused_at_construction(self) -> None:
        with pytest.raises(ValueError, match="opens must be before"):
            BookingHours(opens=time(17, 0), closes=time(9, 0))
        with pytest.raises(ValueError, match="slot_minutes"):
            BookingHours(slot_minutes=0)

    def test_booking_hours_are_separate_from_staffed_hours(self) -> None:
        """A clinic can be bookable when nobody is on the phone."""
        from ait_voice.core.tenancy import StaffedHours

        config = TenantConfig(
            tenant_id="t", region=Region.US, clinic_name="T",
            staffed_hours=StaffedHours.never(), timezone="America/New_York",
        )
        calendar, hours = Calendar(), BookingHours()

        appointment = calendar.book(config.context(), config, hours, WEDNESDAY_1030, now=NOW)

        assert appointment.is_active
        assert not config.is_staffed(NOW)


class TestAvailability:
    def test_it_lists_free_slots_soonest_first(self, calendar, config, hours) -> None:
        free = calendar.availability(config.context(), config, hours, now=NOW, limit=3)

        assert free == sorted(free)
        assert all(slot > NOW for slot in free)

    def test_booked_slots_disappear_from_availability(self, calendar, config, hours) -> None:
        tenant = config.context()
        first = calendar.availability(tenant, config, hours, now=NOW, limit=1)[0]

        calendar.book(tenant, config, hours, first, now=NOW)

        assert first not in calendar.availability(tenant, config, hours, now=NOW, limit=5)

    def test_availability_respects_the_horizon(self, config, hours) -> None:
        calendar = Calendar(horizon_days=1)
        free = calendar.availability(config.context(), config, hours, now=NOW, limit=100)

        assert all(slot <= NOW + timedelta(days=1) for slot in free)


class TestAppointmentShape:
    def test_ends_at_follows_the_duration(self) -> None:
        appointment = Appointment(
            appointment_id="a", tenant_id="t", starts_at=WEDNESDAY_1030,
            duration_minutes=45,
        )
        assert appointment.ends_at == WEDNESDAY_1030 + timedelta(minutes=45)

    @pytest.mark.parametrize(
        ("status", "active"),
        [
            (AppointmentStatus.BOOKED, True),
            (AppointmentStatus.RESCHEDULED, True),
            (AppointmentStatus.CANCELLED, False),
            (AppointmentStatus.COMPLETED, False),
            (AppointmentStatus.NO_SHOW, False),
        ],
    )
    def test_only_live_appointments_are_active(self, status, active) -> None:
        appointment = Appointment(
            appointment_id="a", tenant_id="t", starts_at=WEDNESDAY_1030, status=status
        )
        assert appointment.is_active is active

    def test_midday_is_spoken_as_twelve_not_zero(self) -> None:
        """strftime("%I") gives "12"; a naive lstrip("0") would give "2"."""
        config = _config(timezone="UTC")
        appointment = Appointment(
            appointment_id="a", tenant_id="t",
            starts_at=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        )
        assert "at 12:00 pm" in appointment.spoken(config)


class TestClinicLocalTime:
    def test_staffed_hours_are_evaluated_in_the_clinics_zone(self) -> None:
        """14:00 UTC is 10:00 in New York — inside 9-5, not outside it."""
        config = _config(timezone="America/New_York")
        assert config.is_staffed(datetime(2026, 9, 2, 14, 0, tzinfo=UTC))
        assert not config.is_staffed(datetime(2026, 9, 2, 2, 0, tzinfo=UTC))

    def test_an_india_clinic_reads_its_own_hours(self) -> None:
        config = TenantConfig(
            tenant_id="parkclinic", region=Region.INDIA, clinic_name="Park",
            timezone="Asia/Kolkata",
        )
        # 05:00 UTC = 10:30 IST
        assert config.is_staffed(datetime(2026, 9, 2, 5, 0, tzinfo=UTC))

    def test_an_unknown_timezone_is_refused_at_construction(self) -> None:
        """Better than discovering it when a patient is given the wrong hour."""
        with pytest.raises(ValueError, match="unknown timezone"):
            TenantConfig(
                tenant_id="t", region=Region.US, clinic_name="T",
                timezone="Mars/Olympus_Mons",
            )

    def test_the_default_zone_is_utc(self) -> None:
        assert TenantConfig(
            tenant_id="t", region=Region.US, clinic_name="T"
        ).timezone == "UTC"
