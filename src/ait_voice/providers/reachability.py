"""Does this credential actually work?

The doctor originally reported a leg as LIVE when its environment variable was
*set*. That is a weaker claim than it sounds, and it misleads in exactly the
situation it exists to prevent: a `.env` full of placeholder values reports four
live legs and a confident summary, and the first real call is where you find
out. A key that is present, malformed, revoked, or out of quota all look
identical from the environment.

So this module asks the vendor. One cheap authenticated GET per provider — no
audio, no synthesis, no model invocation, nothing metered beyond an API call
that any account can make.

Deliberately kept off the call path. Verification is something you run
before a deployment, not on every call: an outbound HTTP round-trip per leg
would add latency to the thing NFR1.1 measures, and a vendor's status endpoint
being briefly unreachable must never be the reason a caller hears silence.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx

#: Generous. This runs interactively, and a slow answer beats a wrong one.
TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class Reachability:
    """What one vendor said when asked to authenticate us."""

    provider: str
    configured: bool
    reachable: bool
    detail: str

    @property
    def verdict(self) -> str:
        if not self.configured:
            return "not configured"
        return "OK" if self.reachable else "FAILED"


def _missing(provider: str, what: str) -> Reachability:
    return Reachability(provider, configured=False, reachable=False, detail=what)


def _from_status(provider: str, status: int) -> Reachability:
    if status == 200:
        return Reachability(provider, True, True, "credential accepted")
    if status in (401, 403):
        return Reachability(provider, True, False, f"HTTP {status} — the key is set but rejected")
    if status == 429:
        return Reachability(provider, True, False, f"HTTP {status} — rate limited or out of quota")
    return Reachability(provider, True, False, f"HTTP {status}")


async def _check_anthropic(client: httpx.AsyncClient) -> Reachability:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return _missing("anthropic", "ANTHROPIC_API_KEY is not set")
    response = await client.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    return _from_status("anthropic", response.status_code)


async def _check_deepgram(client: httpx.AsyncClient) -> Reachability:
    key = os.environ.get("DEEPGRAM_API_KEY")
    if not key:
        return _missing("deepgram", "DEEPGRAM_API_KEY is not set")
    response = await client.get(
        "https://api.deepgram.com/v1/projects",
        headers={"Authorization": f"Token {key}"},
    )
    return _from_status("deepgram", response.status_code)


async def _check_elevenlabs(client: httpx.AsyncClient) -> Reachability:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return _missing("elevenlabs", "ELEVENLABS_API_KEY is not set")
    response = await client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
    return _from_status("elevenlabs", response.status_code)


async def _check_twilio(client: httpx.AsyncClient) -> Reachability:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid:
        return _missing("twilio", "TWILIO_ACCOUNT_SID is not set")
    if not token:
        # Worth calling out separately: a SID with no token is the shape a
        # half-filled .env takes, and it reads as "configured" everywhere else.
        return _missing("twilio", "TWILIO_AUTH_TOKEN is not set (SID alone is not enough)")
    response = await client.get(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json", auth=(sid, token)
    )
    return _from_status("twilio", response.status_code)


CHECKS = {
    "anthropic": _check_anthropic,
    "deepgram": _check_deepgram,
    "elevenlabs": _check_elevenlabs,
    "twilio": _check_twilio,
}


async def verify_all(providers: list[str] | None = None) -> list[Reachability]:
    """Ask each vendor whether our credential works. Never returns key material."""
    wanted = providers or list(CHECKS)
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:

        async def run(name: str) -> Reachability:
            try:
                return await CHECKS[name](client)
            except httpx.HTTPError as exc:
                # A network failure is not a bad credential, and saying so
                # saves someone regenerating a key that was fine.
                return Reachability(
                    name, True, False, f"could not reach the vendor: {type(exc).__name__}"
                )

        return list(await asyncio.gather(*(run(name) for name in wanted)))
