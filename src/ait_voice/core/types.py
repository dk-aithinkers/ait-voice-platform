"""Core types: tenant context, regions, and the PHI wrapper.

Three of these implement binding conventions affirmed at practices discovery,
where the reasoning is recorded in full:

- ``TenantContext`` is passed explicitly as a first parameter rather than held
  in an ambient context variable. A missing tenant filter is a cross-tenant PHI
  disclosure, not a defect, and an explicit parameter makes omission a type
  error rather than a runtime surprise.
- ``PHI`` wraps any value that must never reach a log. Its ``__repr__`` and
  ``__str__`` redact, so the most likely breach — a value landing in an f-string
  or a traceback — produces a redaction marker instead of patient data.
- ``Region`` drives provider selection. Constraint C-T1 makes per-region
  provider replaceability a hard requirement: no vendor serves both the US and
  India adequately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")

REDACTED = "[REDACTED]"


class Region(StrEnum):
    """Deployment region for a tenant.

    Region is not a label. It determines which vendors may process a call,
    which regulations bind it, and where its data lives.
    """

    US = "us"
    INDIA = "india"


class PHI(Generic[T]):
    """A value that must never reach a log, metric, trace or exception message.

    Wrapping is deliberate rather than automatic: a developer marks a value as
    protected, and from then on the type system and the logging facade keep it
    out of places it should not go.

    The value is reachable only through :meth:`reveal`, which is greppable. A
    review — or a CI rule — can find every place PHI is unwrapped.

        >>> name = PHI("Priya Sharma")
        >>> str(name)
        '[REDACTED]'
        >>> f"caller: {name}"
        'caller: [REDACTED]'
        >>> name.reveal()
        'Priya Sharma'
    """

    __slots__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    def reveal(self) -> T:
        """Return the underlying value.

        Every call site is a deliberate decision to handle protected data.
        """
        return self._value

    def __repr__(self) -> str:
        return REDACTED

    def __str__(self) -> str:
        return REDACTED

    def __format__(self, _spec: str) -> str:
        # Without this, f"{phi:>10}" would bypass __str__ and leak.
        return REDACTED

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PHI):
            return bool(self._value == other._value)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Identifies whose call this is, and therefore which rules apply.

    Passed as the first parameter to anything that touches tenant data. Frozen
    so it cannot be mutated mid-call into another tenant's context.
    """

    tenant_id: str
    region: Region
    #: Whether this tenant's region has completed the regulatory registration
    #: outbound calling requires. Gates FR4.4 — in India, DLT registration and
    #: 1600-series numbering are a precondition, not a task.
    outbound_registered: bool = False

    def __post_init__(self) -> None:
        if not self.tenant_id:
            raise ValueError("tenant_id must not be empty")

    @property
    def is_phi_jurisdiction(self) -> bool:
        """Whether US HIPAA obligations apply to this tenant's data.

        India's DPDP obligations are handled separately; this flag specifically
        gates the BAA-chain requirements in NFR4.3.
        """
        return self.region is Region.US


@dataclass(frozen=True, slots=True)
class Utterance:
    """One turn of speech in a call, in either direction."""

    text: PHI[str]
    is_final: bool = True
    language: str | None = None


@dataclass(frozen=True, slots=True)
class TurnTiming:
    """Latency measurements for a single conversational turn.

    NFR1.1 requires end-to-end response under 1.5 seconds at p95, measured from
    the caller ceasing speech to the first audio of the agent's reply. These
    fields exist so that number is measured rather than assumed.

    All values are milliseconds.
    """

    stt_ms: float
    llm_ms: float
    tts_first_audio_ms: float

    @property
    def total_ms(self) -> float:
        """End-to-end latency as NFR1.1 defines it."""
        return self.stt_ms + self.llm_ms + self.tts_first_audio_ms

    @property
    def meets_target(self) -> bool:
        """Whether this turn met the NFR1.1 threshold.

        A single turn passing does not mean the p95 does; that needs a sample.
        """
        return self.total_ms < 1500.0
