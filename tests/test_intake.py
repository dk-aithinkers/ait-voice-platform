"""Structured intake capture (P10, FR3.1-FR3.2).

The load-bearing tests are TestConfirmationIsStructural: AC3.2.1 requires an
identifier to be read back and confirmed *before* storing, and the point of
this design is that "we forgot to confirm" is an exception rather than a wrong
date of birth in a patient record.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from ait_voice.core.intake import (
    FIELDS,
    FieldName,
    IntakeRecord,
    IntakeSession,
    IntakeStore,
    InvalidValue,
    UnconfirmedIdentifier,
    speak_date,
    speak_digits,
)
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, Region


def _tenant(tenant_id: str = "northside"):  # noqa: ANN202
    return TenantConfig(
        tenant_id=tenant_id, region=Region.US, clinic_name="Northside"
    ).context()


def _complete(session: IntakeSession) -> IntakeSession:
    """Drive a session through every required field, confirming each."""
    answers = {
        FieldName.FULL_NAME: "Priya Sharma",
        FieldName.DATE_OF_BIRTH: "1985-03-04",
        FieldName.CALLBACK_NUMBER: "+15551234541",
        FieldName.REASON_FOR_VISIT: "follow-up on my knee",
    }
    for name, raw in answers.items():
        if session.capture(name, raw):
            session.confirm(name)
    return session


class TestConfirmationIsStructural:
    """FR3.2 — there is no route from a pending value to a stored one."""

    def test_an_unconfirmed_identifier_blocks_the_record(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Priya Sharma")
        session.confirm(FieldName.FULL_NAME)
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")  # never confirmed

        with pytest.raises(UnconfirmedIdentifier, match="date_of_birth"):
            session.completed(call_id="c-1", tenant_id="northside")

    def test_the_refusal_names_the_requirement(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")

        with pytest.raises(UnconfirmedIdentifier, match="FR3.2"):
            session.completed(call_id="c-1", tenant_id="northside")

    def test_a_captured_identifier_starts_pending(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")

        assert session.confirmed == {}

    def test_confirming_is_what_stores_it(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")
        session.confirm(FieldName.DATE_OF_BIRTH)

        assert FieldName.DATE_OF_BIRTH in session.confirmed

    def test_a_rejected_value_does_not_survive(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")
        session.reject(FieldName.DATE_OF_BIRTH)

        assert FieldName.DATE_OF_BIRTH not in session.confirmed

    def test_a_missing_required_field_blocks_the_record(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Priya Sharma")
        session.confirm(FieldName.FULL_NAME)

        with pytest.raises(UnconfirmedIdentifier, match="not captured"):
            session.completed(call_id="c-1", tenant_id="northside")

    def test_a_complete_session_produces_a_record(self) -> None:
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )

        assert record.get(FieldName.FULL_NAME) == "Priya Sharma"
        assert record.get(FieldName.DATE_OF_BIRTH) == date(1985, 3, 4)


class TestNonIdentifiersSkipConfirmation:
    def test_a_reason_for_visit_is_stored_immediately(self) -> None:
        """Reading a symptom back adds a turn and catches nothing."""
        session = IntakeSession()

        readback = session.capture(FieldName.REASON_FOR_VISIT, "knee pain")

        assert readback is None
        assert FieldName.REASON_FOR_VISIT in session.confirmed

    def test_identifiers_do_require_it(self) -> None:
        session = IntakeSession()
        for name in (
            FieldName.FULL_NAME,
            FieldName.DATE_OF_BIRTH,
            FieldName.CALLBACK_NUMBER,
        ):
            assert session.capture(name, _valid_for(name)) is not None


def _valid_for(name: FieldName) -> str:
    return {
        FieldName.FULL_NAME: "Priya Sharma",
        FieldName.DATE_OF_BIRTH: "1985-03-04",
        FieldName.CALLBACK_NUMBER: "+15551234541",
    }[name]


class TestSpokenReadBack:
    """The read-back exists to catch mishearings, so it must be sayable."""

    def test_a_date_is_spoken_as_a_person_says_it(self) -> None:
        assert speak_date(date(1985, 3, 4)) == (
            "the fourth of March, nineteen eighty-five"
        )

    def test_transposed_day_and_month_sound_different(self) -> None:
        """The single most common intake error, and the reason for all this."""
        assert speak_date(date(1985, 3, 4)) != speak_date(date(1985, 4, 3))
        assert "March" in speak_date(date(1985, 3, 4))
        assert "April" in speak_date(date(1985, 4, 3))

    def test_no_digits_survive_in_a_spoken_date(self) -> None:
        """A synthesiser given "4th" may say "four th"."""
        spoken = speak_date(date(2003, 12, 31))
        assert not any(char.isdigit() for char in spoken)

    @pytest.mark.parametrize(
        ("year", "expected"),
        [
            (1985, "nineteen eighty-five"),
            (1990, "nineteen ninety"),
            (2003, "two thousand three"),
            (2015, "twenty fifteen"),
        ],
    )
    def test_years_are_spoken_naturally(self, year: int, expected: str) -> None:
        assert expected in speak_date(date(year, 6, 15))

    def test_a_number_is_read_digit_by_digit(self) -> None:
        """Read as a number it is unverifiable; digit by digit a caller follows."""
        spoken = speak_digits("+15551234541")

        assert spoken.startswith("one five five")
        assert not any(char.isdigit() for char in spoken)

    def test_an_empty_number_speaks_as_nothing(self) -> None:
        assert speak_digits("") == ""

    def test_the_readback_asks_for_confirmation(self) -> None:
        session = IntakeSession()
        readback = session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")

        assert readback.endswith("Is that right?")
        assert "fourth of March" in readback


class TestValidation:
    """Speech recognition mishears constantly; storing the result silently is
    worse than asking again."""

    def test_a_future_birth_date_is_refused(self) -> None:
        tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()

        with pytest.raises(InvalidValue, match="future"):
            IntakeSession().capture(FieldName.DATE_OF_BIRTH, tomorrow)

    def test_an_implausible_year_is_refused(self) -> None:
        with pytest.raises(InvalidValue, match="too far back"):
            IntakeSession().capture(FieldName.DATE_OF_BIRTH, "1085-03-04")

    def test_unparseable_text_is_refused(self) -> None:
        with pytest.raises(InvalidValue, match="not a date"):
            IntakeSession().capture(FieldName.DATE_OF_BIRTH, "sometime in march")

    def test_a_too_short_number_is_refused(self) -> None:
        with pytest.raises(InvalidValue, match="too short"):
            IntakeSession().capture(FieldName.CALLBACK_NUMBER, "555")

    def test_an_indian_number_is_accepted(self) -> None:
        """A strict US pattern would reject half the target market."""
        session = IntakeSession()
        assert session.capture(FieldName.CALLBACK_NUMBER, "+91 99900 01111")

    def test_a_one_letter_name_is_refused(self) -> None:
        with pytest.raises(InvalidValue, match="too short"):
            IntakeSession().capture(FieldName.FULL_NAME, "P")

    def test_a_name_of_only_punctuation_is_refused(self) -> None:
        with pytest.raises(InvalidValue, match="does not contain a name"):
            IntakeSession().capture(FieldName.FULL_NAME, "-- ..")

    def test_whitespace_is_normalised(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "  Priya   Sharma ")
        session.confirm(FieldName.FULL_NAME)

        assert session.confirmed[FieldName.FULL_NAME].value.reveal() == "Priya Sharma"

    def test_a_name_is_not_title_cased(self) -> None:
        """McDonald, de Silva, ffrench — "correcting" these writes a subtly
        wrong name into a patient record."""
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Ronan de Silva")
        session.confirm(FieldName.FULL_NAME)

        assert session.confirmed[FieldName.FULL_NAME].value.reveal() == "Ronan de Silva"


class TestAskingOrder:
    def test_it_asks_for_the_first_missing_field(self) -> None:
        session = IntakeSession()
        assert session.next_prompt()[0] is FieldName.FULL_NAME

    def test_it_moves_on_once_a_field_is_captured(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Priya Sharma")
        session.confirm(FieldName.FULL_NAME)

        assert session.next_prompt()[0] is FieldName.DATE_OF_BIRTH

    def test_a_rejected_field_is_asked_again(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Priya Sharma")
        session.reject(FieldName.FULL_NAME)

        assert session.next_prompt()[0] is FieldName.FULL_NAME

    def test_optional_fields_come_after_the_required_ones(self) -> None:
        session = _complete(IntakeSession())
        assert session.next_prompt()[0] is FieldName.NOTES

    def test_nothing_is_asked_once_everything_is_captured(self) -> None:
        session = _complete(IntakeSession())
        session.capture(FieldName.NOTES, "uses a wheelchair")

        assert session.next_prompt() is None

    def test_optional_fields_do_not_block_completion(self) -> None:
        session = _complete(IntakeSession())
        assert session.is_complete()


class TestExhaustion:
    def test_repeated_failures_mark_the_field_exhausted(self) -> None:
        """A caller re-reading their date of birth a fourth time has already
        decided the agent is broken."""
        session = IntakeSession(max_attempts=3)
        for _ in range(3):
            session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")
            session.reject(FieldName.DATE_OF_BIRTH)

        assert FieldName.DATE_OF_BIRTH in session.exhausted

    def test_a_confirmed_field_is_never_exhausted(self) -> None:
        session = IntakeSession(max_attempts=2)
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")
        session.reject(FieldName.DATE_OF_BIRTH)
        session.capture(FieldName.DATE_OF_BIRTH, "1985-04-03")
        session.confirm(FieldName.DATE_OF_BIRTH)

        assert session.exhausted == []

    def test_a_fresh_session_has_nothing_exhausted(self) -> None:
        assert IntakeSession().exhausted == []

    def test_attempts_accumulate_across_retries(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.FULL_NAME, "Priya Sharma")
        session.reject(FieldName.FULL_NAME)
        session.capture(FieldName.FULL_NAME, "Priya Sharma")

        assert session._captures[FieldName.FULL_NAME].attempts == 2  # noqa: SLF001


class TestPHIHandling:
    def test_every_captured_value_is_wrapped(self) -> None:
        session = _complete(IntakeSession())

        for capture in session.confirmed.values():
            assert isinstance(capture.value, PHI)

    def test_the_summary_shows_which_fields_exist_not_their_values(self) -> None:
        """A front-desk screen should not display a date of birth."""
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )

        rendered = str(record.summary())
        assert "Priya" not in rendered
        assert "1985" not in rendered
        assert "full_name" in rendered

    def test_the_clinician_view_reveals_deliberately(self) -> None:
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )

        revealed = record.for_clinician()
        assert revealed["full_name"] == "Priya Sharma"
        assert revealed["date_of_birth"] == "1985-03-04"

    def test_a_capture_does_not_leak_in_its_repr(self) -> None:
        session = IntakeSession()
        session.capture(FieldName.DATE_OF_BIRTH, "1985-03-04")

        assert "1985" not in repr(session.confirmed)
        assert "1985" not in repr(session._captures)  # noqa: SLF001


class TestNoNationalIdentifier:
    def test_the_field_set_excludes_ssn_and_aadhaar(self) -> None:
        """Both carry obligations beyond this system's compliance surface, and
        nothing in the MVP needs one. Adding it should be deliberate."""
        names = {str(spec.name) for spec in FIELDS}

        assert not any(
            token in name
            for name in names
            for token in ("ssn", "social", "aadhaar", "national")
        )

    def test_the_field_set_is_closed(self) -> None:
        """A free-form dictionary would let a prompt change quietly widen what
        we hold about a patient."""
        with pytest.raises(KeyError):
            IntakeSession().capture("insurance_number", "12345")  # type: ignore[arg-type]


class TestStoreIsolation:
    def test_one_clinic_cannot_read_anothers_intake(self) -> None:
        store = IntakeStore()
        north, park = _tenant("northside"), _tenant("parkclinic")
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )
        store.add(north, record)

        assert store.get(north, record.intake_id) is not None
        assert store.get(park, record.intake_id) is None
        assert store.recent(park) == []

    def test_intake_can_be_found_by_call(self) -> None:
        store = IntakeStore()
        tenant = _tenant()
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )
        store.add(tenant, record)

        assert [r.intake_id for r in store.for_call(tenant, "c-1")] == [
            record.intake_id
        ]
        assert store.for_call(tenant, "c-other") == []

    def test_intake_is_erasable(self) -> None:
        """Intake is content, and DPDP erasure applies to content."""
        store = IntakeStore()
        tenant = _tenant()
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )
        store.add(tenant, record)

        assert store.erase(tenant, record.intake_id)
        assert store.get(tenant, record.intake_id) is None

    def test_one_clinic_cannot_erase_anothers_intake(self) -> None:
        store = IntakeStore()
        north, park = _tenant("northside"), _tenant("parkclinic")
        record = _complete(IntakeSession()).completed(
            call_id="c-1", tenant_id="northside"
        )
        store.add(north, record)

        assert store.erase(park, record.intake_id) is False
        assert store.get(north, record.intake_id) is not None

    def test_the_store_refuses_to_iterate_without_a_tenant(self) -> None:
        with pytest.raises(TypeError, match="tenant context"):
            list(IntakeStore())


class TestRecordShape:
    def test_an_absent_field_reads_as_none(self) -> None:
        record = IntakeRecord(intake_id="i", tenant_id="t", call_id="c")
        assert record.get(FieldName.FULL_NAME) is None

    def test_confirming_something_never_captured_raises(self) -> None:
        with pytest.raises(KeyError):
            IntakeSession().confirm(FieldName.FULL_NAME)

    def test_rejecting_something_never_captured_raises(self) -> None:
        with pytest.raises(KeyError):
            IntakeSession().reject(FieldName.FULL_NAME)
