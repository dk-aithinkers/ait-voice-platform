"""Structured intake capture over voice.

P10, FR3.1 and FR3.2. The requirement that shapes everything here is AC3.2.1:

    Given the agent has captured a date of birth or similar identifier
    When capture completes
    Then the agent repeats the value back and obtains confirmation
    before storing it

So confirmation is not a step someone remembers to call. A value arrives
:class:`Pending`, and the only route into a stored record is
:meth:`IntakeSession.confirm`. :meth:`IntakeSession.completed` refuses to
produce a record while any identifier is unconfirmed, so "we forgot to confirm"
is an exception rather than a wrong date of birth in a patient file.

**Why the read-back has to be spoken, not printed.** A date rendered
``1985-03-04`` is unusable on a phone, and worse, it hides the single most
common speech error in intake — a transposed day and month. Read back as "the
fourth of March, nineteen eighty-five" a caller catches it immediately. Every
field that requires confirmation therefore owns a spoken form.

**What is deliberately not collected.** No national identifier — no SSN, no
Aadhaar. Both carry obligations well beyond the rest of this system's
compliance surface (Aadhaar in particular is regulated separately from DPDP
generally, with its own authentication and storage rules), and nothing in the
MVP needs one: an appointment needs a name, a date of birth to disambiguate,
and a number to call back. Adding one later should be a deliberate act with
counsel involved, which is why the field set is a closed enum rather than a
free-form dictionary.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from enum import StrEnum

from ait_voice.core.tenancy import TenantScoped
from ait_voice.core.types import PHI, TenantContext

#: Oldest plausible caller. A date before this is a recognition error, not a
#: patient, and storing it silently corrupts the record it was meant to make
#: reliable.
EARLIEST_BIRTH_YEAR = 1900

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_ONES = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_TENS = (
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
)


class FieldName(StrEnum):
    """The closed set of things intake captures.

    A closed enum rather than a free-form dictionary, because "what do we hold
    about this patient" must be answerable by reading one file. A dictionary
    would let a prompt change quietly widen the compliance surface.
    """

    FULL_NAME = "full_name"
    DATE_OF_BIRTH = "date_of_birth"
    CALLBACK_NUMBER = "callback_number"
    REASON_FOR_VISIT = "reason_for_visit"
    #: Free text: allergies, mobility needs, an interpreter. Not clinical
    #: assessment — the agent is forbidden that — just something to pass on.
    NOTES = "notes"


class CaptureStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    #: The caller said the read-back was wrong. Kept rather than discarded, so
    #: repeated mishearing of the same field is visible instead of invisible.
    REJECTED = "rejected"


class InvalidValue(ValueError):
    """A captured value cannot be what the caller meant.

    Raised rather than stored. Speech recognition mishears constantly, and a
    silently accepted birth year of 1085 is worse than asking again.
    """


class UnconfirmedIdentifier(RuntimeError):
    """An identifier would be stored without the caller confirming it."""


def _spell_number(value: int) -> str:
    """Small integers as words, for the spoken read-back."""
    if value < 20:
        return _ONES[value]
    tens, ones = divmod(value, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def _spoken_year(year: int) -> str:
    """Say a year the way a person does: nineteen eighty-five, not 1985."""
    if 1000 <= year < 2000:
        return f"nineteen {_spell_number(year - 1900)}"
    if 2000 <= year < 2010:
        return f"two thousand {_ONES[year - 2000]}".strip()
    if 2010 <= year < 2100:
        return f"twenty {_spell_number(year - 2000)}"
    return str(year)


#: Spoken ordinals. Written out for the same reason the year is: this string
#: goes to a speech synthesiser, and "4th" is one vendor's normalisation away
#: from "four th". Words leave nothing to interpret.
_ORDINALS = (
    "",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "twenty-first",
    "twenty-second",
    "twenty-third",
    "twenty-fourth",
    "twenty-fifth",
    "twenty-sixth",
    "twenty-seventh",
    "twenty-eighth",
    "twenty-ninth",
    "thirtieth",
    "thirty-first",
)


def _ordinal(day: int) -> str:
    return _ORDINALS[day]


def speak_date(value: date) -> str:
    """A date as a person would say it.

    The whole point of the read-back: `1985-03-04` and `1985-04-03` look nearly
    identical and sound nothing alike, and a transposed day and month is the
    most common intake error there is.
    """
    return f"the {_ordinal(value.day)} of {_MONTHS[value.month - 1]}, {_spoken_year(value.year)}"


def speak_digits(value: str) -> str:
    """A phone number digit by digit, grouped for breath.

    Read as a number — "fifteen billion..." — it is unverifiable. Digit by digit
    a caller can follow along.
    """
    digits = re.sub(r"\D", "", value)
    if not digits:
        return ""
    groups = [digits[i : i + 3] for i in range(0, len(digits), 3)]
    return ", ".join(" ".join(_ONES[int(d)] for d in group) for group in groups)


def _validate_name(raw: str) -> str:
    """Normalise whitespace, and nothing else.

    Deliberately not title-cased. Capitalisation rules are not universal —
    McDonald, de Silva, van der Berg, ffrench — and a system that "corrects"
    them writes a subtly wrong name into a patient record while looking tidier
    for it. The caller's own rendering is the best available answer.
    """
    cleaned = " ".join(raw.split())
    if len(cleaned) < 2:
        raise InvalidValue("that name is too short to be right")
    if not any(ch.isalpha() for ch in cleaned):
        raise InvalidValue("that does not contain a name")
    return cleaned


def _validate_dob(raw: str) -> date:
    try:
        value = date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise InvalidValue("that is not a date I can read") from exc
    today = datetime.now(UTC).date()
    if value > today:
        raise InvalidValue("that date is in the future")
    if value.year < EARLIEST_BIRTH_YEAR:
        raise InvalidValue("that year is too far back to be right")
    return value


def _validate_number(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    # Loose on purpose: E.164 allows 15 digits and national formats vary, and a
    # strict pattern here would reject valid Indian and US numbers alike. The
    # read-back is what actually catches a mishearing.
    if len(re.sub(r"\D", "", digits)) < 7:
        raise InvalidValue("that number is too short")
    return digits


def _validate_text(raw: str) -> str:
    cleaned = " ".join(raw.split())
    if not cleaned:
        raise InvalidValue("nothing was captured")
    return cleaned


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """How one field is asked, checked and read back."""

    name: FieldName
    prompt: str
    #: Identifiers require confirmation — AC3.2.1. A reason for visit does not:
    #: reading a symptom back adds a turn and catches nothing, because the
    #: caller just said it in their own words.
    requires_confirmation: bool
    validate: Callable[[str], object]
    speak: Callable[[object], str]
    required: bool = True


#: The field set. Order is the order a caller is asked.
FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name=FieldName.FULL_NAME,
        prompt="Can I take your full name?",
        requires_confirmation=True,
        validate=_validate_name,
        speak=lambda v: str(v),
    ),
    FieldSpec(
        name=FieldName.DATE_OF_BIRTH,
        prompt="And your date of birth?",
        requires_confirmation=True,
        validate=_validate_dob,
        speak=lambda v: speak_date(v),  # type: ignore[arg-type]
    ),
    FieldSpec(
        name=FieldName.CALLBACK_NUMBER,
        prompt="What's the best number to reach you on?",
        requires_confirmation=True,
        validate=_validate_number,
        speak=lambda v: speak_digits(str(v)),
    ),
    FieldSpec(
        name=FieldName.REASON_FOR_VISIT,
        prompt="And briefly, what's the appointment for?",
        requires_confirmation=False,
        validate=_validate_text,
        speak=lambda v: str(v),
    ),
    FieldSpec(
        name=FieldName.NOTES,
        prompt="Anything we should know before you come in?",
        requires_confirmation=False,
        validate=_validate_text,
        speak=lambda v: str(v),
        required=False,
    ),
)

FIELDS_BY_NAME = {spec.name: spec for spec in FIELDS}


@dataclass(frozen=True, slots=True)
class Capture:
    """One captured value and where it is in the confirmation cycle."""

    field: FieldName
    value: PHI[object]
    status: CaptureStatus = CaptureStatus.PENDING
    #: How many times this field has been asked. Rises on every rejection, and
    #: is what tells the agent to stop trying and fetch a person.
    attempts: int = 1

    @property
    def is_confirmed(self) -> bool:
        return self.status is CaptureStatus.CONFIRMED


class IntakeSession:
    """Capture during one call. Nothing here is stored until it is confirmed."""

    def __init__(self, fields: tuple[FieldSpec, ...] = FIELDS, *, max_attempts: int = 3) -> None:
        self._fields = fields
        self._max_attempts = max_attempts
        self._captures: dict[FieldName, Capture] = {}

    # -- asking ----------------------------------------------------------

    def next_prompt(self) -> tuple[FieldName, str] | None:
        """The next thing to ask, or None when intake is done."""
        for spec in self._fields:
            capture = self._captures.get(spec.name)
            if capture is None:
                if spec.required or self._all_required_done():
                    return spec.name, spec.prompt
                continue
            if capture.status is CaptureStatus.REJECTED:
                return spec.name, spec.prompt
        return None

    def _all_required_done(self) -> bool:
        return all(
            self._captures.get(spec.name) is not None
            and self._captures[spec.name].status is not CaptureStatus.REJECTED
            for spec in self._fields
            if spec.required
        )

    # -- capturing -------------------------------------------------------

    def capture(self, name: FieldName, raw: str) -> str | None:
        """Take a value and return the read-back to speak, if one is needed.

        Returns None for a field that needs no confirmation — it is stored
        immediately, because reading a symptom back catches nothing.
        """
        spec = FIELDS_BY_NAME[name]
        previous = self._captures.get(name)
        attempts = (previous.attempts + 1) if previous else 1

        value = spec.validate(raw)

        status = CaptureStatus.PENDING if spec.requires_confirmation else CaptureStatus.CONFIRMED
        self._captures[name] = Capture(
            field=name, value=PHI(value), status=status, attempts=attempts
        )
        if not spec.requires_confirmation:
            return None
        return f"I have {spec.speak(value)}. Is that right?"

    def confirm(self, name: FieldName) -> Capture:
        """The caller said the read-back was right. Only route to storage."""
        capture = self._captures.get(name)
        if capture is None:
            raise KeyError(f"nothing captured for {name}")
        confirmed = replace(capture, status=CaptureStatus.CONFIRMED)
        self._captures[name] = confirmed
        return confirmed

    def reject(self, name: FieldName) -> Capture:
        """The caller said it was wrong. The value does not survive."""
        capture = self._captures.get(name)
        if capture is None:
            raise KeyError(f"nothing captured for {name}")
        rejected = replace(capture, status=CaptureStatus.REJECTED)
        self._captures[name] = rejected
        return rejected

    # -- state -----------------------------------------------------------

    @property
    def exhausted(self) -> list[FieldName]:
        """Fields asked too many times.

        A caller re-reading their date of birth for the fourth time has already
        decided the agent is broken. This is what tells the dialog to stop and
        fetch a person rather than keep trying.
        """
        return [
            name
            for name, capture in self._captures.items()
            if capture.attempts >= self._max_attempts and not capture.is_confirmed
        ]

    @property
    def confirmed(self) -> dict[FieldName, Capture]:
        return {n: c for n, c in self._captures.items() if c.is_confirmed}

    def is_complete(self) -> bool:
        return all(
            self._captures.get(spec.name) is not None and self._captures[spec.name].is_confirmed
            for spec in self._fields
            if spec.required
        )

    def completed(self, *, call_id: str, tenant_id: str) -> IntakeRecord:
        """Produce the record. Refuses while any identifier is unconfirmed.

        This is the structural half of FR3.2: there is no path from a pending
        value to a stored one that does not pass through :meth:`confirm`.
        """
        unconfirmed = [
            spec.name
            for spec in self._fields
            if spec.requires_confirmation
            and (capture := self._captures.get(spec.name)) is not None
            and not capture.is_confirmed
        ]
        if unconfirmed:
            raise UnconfirmedIdentifier(
                f"{', '.join(sorted(unconfirmed))} was captured but never confirmed "
                "by the caller (FR3.2)"
            )
        missing = [
            spec.name for spec in self._fields if spec.required and spec.name not in self.confirmed
        ]
        if missing:
            raise UnconfirmedIdentifier(
                f"intake is incomplete: {', '.join(sorted(missing))} not captured"
            )
        return IntakeRecord(
            intake_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            call_id=call_id,
            values={name: capture.value for name, capture in self.confirmed.items()},
        )


@dataclass(frozen=True, slots=True)
class IntakeRecord:
    """A completed intake. Every value in it was confirmed aloud by the caller."""

    intake_id: str
    tenant_id: str
    call_id: str
    values: dict[FieldName, PHI[object]] = field(default_factory=dict)
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get(self, name: FieldName) -> object | None:
        wrapped = self.values.get(name)
        return wrapped.reveal() if wrapped else None

    def summary(self) -> dict[str, object]:
        """List shape. Every intake value is PHI, so none of them appear.

        What a list can honestly show is that an intake exists and which fields
        it holds — enough for a clinic to see the work was done without putting
        a date of birth on a screen at a front desk.
        """
        return {
            "intake_id": self.intake_id,
            "call_id": self.call_id,
            "captured_at": self.captured_at.isoformat(),
            "fields": sorted(str(name) for name in self.values),
        }

    def for_clinician(self) -> dict[str, str]:
        """The revealed record, for a person who needs to act on it.

        The one place intake values are unwrapped, and only behind an
        authenticated tenant-scoped request — the same shape as the handoff
        briefing, for the same reason.
        """
        rendered: dict[str, str] = {}
        for name, wrapped in self.values.items():
            value = wrapped.reveal()
            rendered[str(name)] = value.isoformat() if isinstance(value, date) else str(value)
        return rendered


class IntakeStore:
    """Tenant-partitioned intake records."""

    def __init__(self) -> None:
        self._records: TenantScoped[IntakeRecord] = TenantScoped()

    def add(self, tenant: TenantContext, record: IntakeRecord) -> IntakeRecord:
        return self._records.put(tenant, record.intake_id, record)

    def get(self, tenant: TenantContext, intake_id: str) -> IntakeRecord | None:
        return self._records.get(tenant, intake_id)

    def for_call(self, tenant: TenantContext, call_id: str) -> list[IntakeRecord]:
        return [r for r in self._records.values(tenant) if r.call_id == call_id]

    def recent(self, tenant: TenantContext, *, limit: int = 50) -> list[IntakeRecord]:
        return sorted(self._records.values(tenant), key=lambda r: r.captured_at, reverse=True)[
            :limit
        ]

    def erase(self, tenant: TenantContext, intake_id: str) -> bool:
        """DPDP erasure. Intake is content, and content is erasable."""
        return self._records.delete(tenant, intake_id)

    def __iter__(self) -> Iterator[str]:
        raise TypeError("IntakeStore is not iterable without tenant context. Use recent(tenant).")
