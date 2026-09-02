"""The production entrypoint: the API, backed by Postgres.

    uv run uvicorn --factory ait_voice.api.main:production_app

The difference from :mod:`ait_voice.api.demo` is the whole point of this
module. The demo holds its data in memory, which is right for looking at the UI
and wrong for everything else: a restart loses every clinic's configuration,
the entire diary, all call records and transcripts, every waiting handoff, all
intake, and the India consent ledger with its seven-day expiry state — the last
of which is a compliance consequence (C-R9) rather than an inconvenience.

`Database.connect()` refuses a superuser, so a misconfigured deployment fails
here at startup rather than serving requests with row-level security enabled
and enforcing nothing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ait_voice.api.app import Services, create_app
from ait_voice.config import load_dotenv_if_present
from ait_voice.db.connection import Database


def production_app() -> FastAPI:
    """Build the app and bind the connection pool to its lifespan.

    A factory rather than a module-level app: the pool must open inside the
    running event loop, and importing this module must not try to reach a
    database — that would make the import itself fail on a machine with no
    Postgres, including during collection of tests that never touch it.
    """
    load_dotenv_if_present()
    database = Database()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await database.connect()
        try:
            yield
        finally:
            await database.close()

    return create_app(Services.from_database(database), lifespan=lifespan)
