"""Who is asking, and which tenant they are allowed to ask about.

This module exists because of an objection raised when the UI was proposed: a
JSON API is a **new boundary** where the tenant-scoping discipline has to be
re-established. Inside the Python process, `TenantScoped` makes cross-tenant
access structurally impossible. Over HTTP, a tenant id is just a string in a
URL, and the guarantee is only as good as the check on it.

So the tenant is never taken from the request path for a clinic user. It comes
from their identity. A clinic principal is *bound* to one tenant at
authentication time and cannot widen that, whatever the URL says — asking for
another clinic's calls returns 403, not that clinic's calls.

An operator may act across tenants, because that is their job, and every such
act is auditable. The distinction is enforced in one place: :func:`resolve_scope`.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from enum import StrEnum

from ait_voice.core.tenancy import TenantNotFoundError, TenantStore
from ait_voice.core.types import TenantContext


class Role(StrEnum):
    """What a principal may do."""

    #: AI Thinkers staff. May configure clinics and see across tenants.
    OPERATOR = "operator"
    #: Clinic staff. Read-only, and bound to exactly one tenant.
    CLINIC = "clinic"


class AuthError(RuntimeError):
    """Authentication failed. Deliberately vague to the caller."""


class ForbiddenError(RuntimeError):
    """Authenticated, but not permitted to reach this tenant or action."""


@dataclass(frozen=True, slots=True)
class Principal:
    """An authenticated user.

    ``tenant_id`` is None for an operator and set for a clinic user. That
    asymmetry is the authorization model in one field.
    """

    principal_id: str
    role: Role
    tenant_id: str | None = None
    display_name: str = ""

    @property
    def is_operator(self) -> bool:
        return self.role is Role.OPERATOR

    def __post_init__(self) -> None:
        if self.role is Role.CLINIC and not self.tenant_id:
            # A clinic principal with no tenant would be an unbound read-only
            # user — which, given resolve_scope, is an operator by accident.
            raise ValueError("a clinic principal must be bound to a tenant")


def hash_token(token: str) -> str:
    """Hash an API token for storage.

    Tokens are stored hashed so a leaked store is not a leaked credential.
    SHA-256 rather than a password KDF is deliberate and bounded: these are
    high-entropy machine-generated tokens, not user-chosen passwords, so the
    brute-force resistance a KDF buys does not apply. If this ever accepts a
    human-chosen secret, it must change.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    """A fresh API token. 32 bytes of urandom, URL-safe."""
    return secrets.token_urlsafe(32)


class PrincipalStore:
    """Maps API tokens to principals.

    In-memory for now, seeded from the environment. The shape is what matters:
    a token identifies a principal, and a principal carries its own tenant
    binding, so no request can name a tenant it was not issued for.
    """

    def __init__(self) -> None:
        self._by_token_hash: dict[str, Principal] = {}

    def issue(self, principal: Principal, token: str | None = None) -> str:
        token = token or new_token()
        self._by_token_hash[hash_token(token)] = principal
        return token

    def authenticate(self, token: str | None) -> Principal:
        if not token:
            raise AuthError("no credential presented")
        digest = hash_token(token)
        for known, principal in self._by_token_hash.items():
            # Constant-time comparison across the whole set: a short-circuiting
            # dict lookup on a secret-derived key leaks timing information
            # about which prefixes exist.
            if hmac.compare_digest(known, digest):
                return principal
        raise AuthError("credential not recognised")

    def __len__(self) -> int:
        return len(self._by_token_hash)


def resolve_scope(
    principal: Principal,
    requested_tenant: str | None,
    tenants: TenantStore,
) -> TenantContext:
    """The single place a request is bound to a tenant.

    For a clinic user the requested tenant is *ignored* unless it matches their
    own — passing someone else's id is a 403, never a silent redirect to their
    own data, because a silent redirect hides an attempt worth noticing.

    For an operator the requested tenant is required: there is no "all tenants"
    context, so no handler can accidentally be written against one.
    """
    if principal.role is Role.CLINIC:
        if requested_tenant and requested_tenant != principal.tenant_id:
            raise ForbiddenError(f"you do not have access to tenant {requested_tenant!r}")
        target = principal.tenant_id
    else:
        if not requested_tenant:
            # Deliberately no cross-tenant context exists, so that no handler
            # can be written against one — but that rationale belongs in this
            # comment, not in a banner an operator reads.
            raise ForbiddenError("choose a clinic: every request names one")
        target = requested_tenant

    try:
        return tenants.resolve(target or "")
    except TenantNotFoundError as exc:
        raise ForbiddenError(f"unknown or inactive tenant: {target!r}") from exc


def seed_from_environment(store: PrincipalStore) -> list[str]:
    """Issue tokens from environment variables, for local development.

    Returns the names of the principals seeded. Tokens are read, never printed
    and never logged. Absent variables simply seed nothing, so a deployment
    that uses a real identity provider is unaffected.
    """
    seeded: list[str] = []
    if token := os.environ.get("AIT_OPERATOR_TOKEN"):
        store.issue(
            Principal(
                principal_id="operator",
                role=Role.OPERATOR,
                display_name="AI Thinkers operator",
            ),
            token,
        )
        seeded.append("operator")
    if (token := os.environ.get("AIT_CLINIC_TOKEN")) and (
        tenant := os.environ.get("AIT_CLINIC_TENANT")
    ):
        store.issue(
            Principal(
                principal_id=f"clinic:{tenant}",
                role=Role.CLINIC,
                tenant_id=tenant,
                display_name=tenant,
            ),
            token,
        )
        seeded.append(f"clinic:{tenant}")
    return seeded
