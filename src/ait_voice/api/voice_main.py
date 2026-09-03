"""The voice service entrypoint — the second command on the same image.

    uv run uvicorn --factory ait_voice.api.voice_main:voice_app

Separate from `ait_voice.api.main` because the two services differ in every way
that matters operationally: this one is a public carrier webhook holding sockets
open for the length of a call, that one is an authenticated console serving short
requests. Same image, different task definition.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ait_voice.api.voice import VoiceServices, create_voice_app
from ait_voice.api.voice_auth import relay_secret
from ait_voice.config import build_registry, load_baa_register, load_dotenv_if_present
from ait_voice.core.logging import configure_logging
from ait_voice.core.pipeline import VoicePipeline
from ait_voice.db.calls import PostgresCallStore
from ait_voice.db.connection import Database
from ait_voice.db.storage import build_storage
from ait_voice.db.tenants import PostgresTenantStore
from ait_voice.providers.conversation_relay import ConversationRelayTransport


class VoiceMisconfigured(RuntimeError):
    """Refused at startup rather than answering a call badly."""


def voice_app() -> FastAPI:
    load_dotenv_if_present()
    configure_logging()

    websocket_base = os.environ.get("AIT_RELAY_WS_URL", "").strip()
    if not websocket_base:
        raise VoiceMisconfigured(
            "AIT_RELAY_WS_URL is not set. It is the wss:// address this service "
            "puts in the TwiML, so without it Twilio is told to connect nowhere."
        )
    if not websocket_base.startswith("wss://"):
        # ws:// would carry the conversation in clear text, and the
        # conversation is PHI.
        raise VoiceMisconfigured(
            f"AIT_RELAY_WS_URL is {websocket_base!r}. It must be wss://: a plain "
            "ws:// socket carries the transcript in clear text, and C-R2 makes "
            "that PHI."
        )
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if not auth_token:
        raise VoiceMisconfigured(
            "TWILIO_AUTH_TOKEN is not set. It validates the webhook signature, "
            "and without it every request would have to be treated as forged — "
            "which is the same as accepting them all."
        )
    # Raises if the relay signing secret is absent. Checked here so the failure
    # is at startup rather than on the first call.
    relay_secret()

    database = Database()
    storage = build_storage()
    baa = load_baa_register()
    registry, _ = build_registry(baa_register=baa)

    services = VoiceServices(
        tenants=PostgresTenantStore(database),
        calls=PostgresCallStore(database),
        audit=storage.audit,
        pipeline=VoicePipeline(registry),
        relay=ConversationRelayTransport(baa_confirmed=baa.get("twilio", False)),
        websocket_base=websocket_base,
        auth_token=auth_token,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await database.connect()
        try:
            yield
        finally:
            await database.close()

    app = create_voice_app(services)
    app.router.lifespan_context = lifespan
    logging.getLogger(__name__).info(
        "voice service configured — relay=%s storage=%s", websocket_base, storage.description
    )
    return app
