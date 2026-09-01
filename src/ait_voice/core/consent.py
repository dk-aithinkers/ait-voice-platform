"""Consent, and the fact that it expires.

Constraint C-R9: in India, consent for commercial calls **expires after seven
days**. Most consent models treat consent as durable — granted once, held
forever — and that model is simply wrong here. Building it that way and adding
expiry later means auditing every place consent was read.

The other half is C-R6 and the DLT registration it depends on. Outbound calling
to Indian numbers requires 1600-series numbering with completed registration,
penalties reach ₹1M per instance with a two-year cross-operator blacklist, and
no provider does the registration on a customer's behalf. That is a *precondition*
rather than a task, so :func:`may_place_outbound_call` checks it before anything
dials.

US obligations differ and are handled separately: the TCPA healthcare exemption
means appointment reminders need prior express consent rather than written
consent — but it evaporates the moment marketing content enters the call, which
is a product constraint rather than a consent one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ait_voice.core.types import Region, TenantContext

#: C-R9 — India. Not a tunable; it is what the regulation says.
INDIA_CONSENT_VALIDITY = timedelta(days=7)


class ConsentPurpose(StrEnum):
    """What consent was given *for*. Consent is never general."""

    APPOINTMENT_REMINDER = "appointment_reminder"
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    CLINICAL_FOLLOW_UP = "clinical_follow_up"
    CALL_RECORDING = "call_recording"


class ConsentDenied(RuntimeError):
    """Raised when an outbound call would proceed without valid consent."""


@dataclass(frozen=True, slots=True)
class Consent:
    """A grant, with the expiry the jurisdiction requires."""

    caller_ref: str
    purpose: ConsentPurpose
    granted_at: datetime
    region: Region

    @property
    def expires_at(self) -> datetime | None:
        """When this consent stops being valid.

        ``None`` means it does not expire on a clock. That is the US position
        for the healthcare exemption — it is not a claim that consent is
        irrevocable, only that it has no fixed lifetime.
        """
        if self.region is Region.INDIA:
            return self.granted_at + INDIA_CONSENT_VALIDITY
        return None

    def is_valid(self, *, now: datetime | None = None) -> bool:
        expiry = self.expires_at
        if expiry is None:
            return True
        return (now or datetime.now(UTC)) < expiry

    def remaining(self, *, now: datetime | None = None) -> timedelta | None:
        expiry = self.expires_at
        if expiry is None:
            return None
        return max(expiry - (now or datetime.now(UTC)), timedelta(0))


class ConsentLedger:
    """Records consent grants and answers whether one is currently valid.

    In-memory for the skeleton. The behaviour that matters — that expiry is
    evaluated at read time rather than stamped at write time — is independent
    of where it is stored, so a later move to a database changes persistence
    and not semantics.
    """

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str, str], Consent] = {}

    @staticmethod
    def _key(
        tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> tuple[str, str, str]:
        return (tenant.tenant_id, caller_ref, str(purpose))

    def grant(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        at: datetime | None = None,
    ) -> Consent:
        consent = Consent(
            caller_ref=caller_ref,
            purpose=purpose,
            granted_at=at or datetime.now(UTC),
            region=tenant.region,
        )
        self._grants[self._key(tenant, caller_ref, purpose)] = consent
        return consent

    def revoke(self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose) -> bool:
        """Withdraw consent. Always available, in every jurisdiction."""
        return self._grants.pop(self._key(tenant, caller_ref, purpose), None) is not None

    def lookup(
        self, tenant: TenantContext, caller_ref: str, purpose: ConsentPurpose
    ) -> Consent | None:
        return self._grants.get(self._key(tenant, caller_ref, purpose))

    def is_valid(
        self,
        tenant: TenantContext,
        caller_ref: str,
        purpose: ConsentPurpose,
        *,
        now: datetime | None = None,
    ) -> bool:
        consent = self.lookup(tenant, caller_ref, purpose)
        return bool(consent and consent.is_valid(now=now))


def may_place_outbound_call(
    tenant: TenantContext,
    caller_ref: str,
    purpose: ConsentPurpose,
    ledger: ConsentLedger,
    *,
    now: datetime | None = None,
) -> None:
    """Raise unless an outbound call to this caller is permitted right now.

    Two independent gates, and both must pass:

    1. **Registration.** In India, DLT registration and 1600-series numbering
       are a precondition for commercial calling at all. A tenant without it
       cannot place the call regardless of consent.
    2. **Consent.** Valid, unexpired, and granted for *this* purpose.
    """
    if tenant.region is Region.INDIA and not tenant.outbound_registered:
        raise ConsentDenied(
            f"tenant {tenant.tenant_id!r} has not completed DLT registration and "
            "1600-series numbering; outbound commercial calling to India numbers "
            "is a precondition, not a task (C-R6)"
        )

    consent = ledger.lookup(tenant, caller_ref, purpose)
    if consent is None:
        raise ConsentDenied(
            f"no consent recorded for purpose {purpose!s} — outbound calls require "
            "consent granted for the specific purpose"
        )

    if not consent.is_valid(now=now):
        raise ConsentDenied(
            f"consent for {purpose!s} expired at {consent.expires_at!s}; "
            "in India consent lasts seven days and must be renewed (C-R9)"
        )
