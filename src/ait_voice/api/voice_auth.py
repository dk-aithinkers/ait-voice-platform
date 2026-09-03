"""Proving that a request is Twilio's, and that a socket belongs to a call.

Two different problems, because Twilio solves one of them and not the other.

**The webhook** is signed. Twilio HMACs the full URL plus the sorted POST body
with the account auth token, and sends the result in `X-Twilio-Signature`. Its
SDK ships the validator, so we use it rather than reimplementing an HMAC scheme
where a subtle mistake looks exactly like working code.

**The WebSocket is not signed.** Twilio opens a plain connection to whatever URL
the TwiML named, with no credential of any kind. A public WSS endpoint that
started a call session for anyone who connected would let a stranger drive the
dialog engine, run up vendor spend, and — worse — do it inside a tenant context,
producing audit entries and transcripts for a call that never happened.

So the webhook mints a short-lived token binding the call to its tenant, and the
URL it hands Twilio carries it. The socket handler verifies it before opening
anything. That also solves a second problem for free: with more than one task
behind a load balancer, the webhook and the socket land on different containers,
so the tenant cannot be remembered between them. A signed token is state the
request carries rather than state a process holds.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

#: Long enough for Twilio to place the call, short enough that a leaked URL in a
#: log is not a standing invitation. Twilio connects within seconds.
TOKEN_TTL_SECONDS = 120


class RelayTokenInvalid(RuntimeError):
    """The socket presented a token that does not authorise a call."""


class VoiceAuthMisconfigured(RuntimeError):
    """No signing secret. Refused at startup rather than served insecurely."""


def relay_secret() -> str:
    secret = os.environ.get("AIT_RELAY_TOKEN_SECRET", "").strip()
    if not secret:
        raise VoiceAuthMisconfigured(
            "AIT_RELAY_TOKEN_SECRET is not set.\n\n"
            "It signs the token that authorises a ConversationRelay socket. "
            "Without it the WebSocket endpoint would accept any connection and "
            "open a tenant-scoped dialog session for it. Generate one and put "
            "it in Secrets Manager."
        )
    return secret


def mint_relay_token(tenant_id: str, call_sid: str, *, now: float | None = None) -> str:
    """A token binding one socket to one call for one tenant.

    The expiry is inside the signed payload rather than beside it, so it cannot
    be edited without breaking the signature.
    """
    expires = int((now if now is not None else time.time()) + TOKEN_TTL_SECONDS)
    payload = f"{tenant_id}:{call_sid}:{expires}"
    digest = hmac.new(relay_secret().encode(), payload.encode(), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return f"{base64.urlsafe_b64encode(payload.encode()).decode().rstrip('=')}.{signature}"


def _unpad(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_relay_token(token: str, *, now: float | None = None) -> tuple[str, str]:
    """Return (tenant_id, call_sid), or raise.

    Every failure raises the same exception with the same message. Telling a
    caller whether the signature or the expiry failed hands them a way to probe
    for one and then the other.
    """
    moment = now if now is not None else time.time()
    try:
        encoded, signature = token.split(".", 1)
        payload = _unpad(encoded).decode()
        tenant_id, call_sid, expires = payload.rsplit(":", 2)
        expected = hmac.new(relay_secret().encode(), payload.encode(), hashlib.sha256).digest()
        # compare_digest, not ==: a short-circuiting comparison leaks how much
        # of a forged signature was correct.
        if not hmac.compare_digest(_unpad(signature), expected):
            raise RelayTokenInvalid("relay token is not valid")
        if moment > int(expires):
            raise RelayTokenInvalid("relay token is not valid")
    except RelayTokenInvalid:
        raise
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise RelayTokenInvalid("relay token is not valid") from exc
    return tenant_id, call_sid


def validate_twilio_signature(
    *, url: str, params: dict[str, str], signature: str | None, auth_token: str
) -> bool:
    """Is this request actually from Twilio?

    Delegated to Twilio's own validator rather than reimplemented. The scheme is
    a documented HMAC over the URL and sorted parameters, and hand-rolling it is
    the kind of thing that appears to work until the one request that matters.
    """
    if not signature or not auth_token:
        return False
    from twilio.request_validator import RequestValidator

    return bool(RequestValidator(auth_token).validate(url, params, signature))
