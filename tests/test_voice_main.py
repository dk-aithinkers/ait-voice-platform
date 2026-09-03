"""`voice_app`, and the four ways it refuses to start.

Every check here is a misconfiguration that would otherwise produce a service
that appears healthy and is not: a TwiML pointing nowhere, a webhook that
accepts forgeries, a socket anyone can open, or a transcript crossing the
network in clear text. All are cheap to get wrong in a task definition and
expensive to notice from the outside.
"""

from __future__ import annotations

import pytest

from ait_voice.api.voice_auth import VoiceAuthMisconfigured
from ait_voice.api.voice_main import VoiceMisconfigured, voice_app

REQUIRED = {
    "AIT_RELAY_WS_URL": "wss://voice.example.com",
    "TWILIO_AUTH_TOKEN": "an-auth-token",
    "AIT_RELAY_TOKEN_SECRET": "a-signing-secret",
    "AIT_AUDIT_BUCKET": "audit",
    "AIT_CONTENT_BUCKET": "content",
}


@pytest.fixture(autouse=True)
def _environment(monkeypatch) -> None:  # noqa: ANN001
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)
    for name in ("AIT_AUDIT_ROOT", "AIT_CONTENT_ROOT"):
        monkeypatch.delenv(name, raising=False)


class TestItRefusesToStartMisconfigured:
    def test_without_a_relay_url(self, monkeypatch) -> None:  # noqa: ANN001
        monkeypatch.delenv("AIT_RELAY_WS_URL")

        with pytest.raises(VoiceMisconfigured, match="connect nowhere"):
            voice_app()

    def test_with_a_plaintext_relay_url(self, monkeypatch) -> None:  # noqa: ANN001
        """ws:// would carry the transcript in clear text, and C-R2 makes that PHI."""
        monkeypatch.setenv("AIT_RELAY_WS_URL", "ws://voice.example.com")

        with pytest.raises(VoiceMisconfigured, match="clear text"):
            voice_app()

    def test_without_a_twilio_auth_token(self, monkeypatch) -> None:  # noqa: ANN001
        """No token means no signature check, which is the same as accepting
        every forgery."""
        monkeypatch.delenv("TWILIO_AUTH_TOKEN")

        with pytest.raises(VoiceMisconfigured, match="signature"):
            voice_app()

    def test_without_a_relay_signing_secret(self, monkeypatch) -> None:  # noqa: ANN001
        """Without it the WebSocket accepts anyone."""
        monkeypatch.delenv("AIT_RELAY_TOKEN_SECRET")

        with pytest.raises(VoiceAuthMisconfigured, match="accept any connection"):
            voice_app()


class TestItBuilds:
    def test_a_complete_environment_produces_an_app(self) -> None:
        app = voice_app()

        assert app.router.lifespan_context is not None
        paths = {getattr(r, "path", "") for r in app.routes}
        assert paths >= {"/voice/incoming", "/voice/relay", "/voice/health"}

    def test_building_it_opens_no_connection(self) -> None:
        """The pool opens in the lifespan. A factory that connected eagerly
        would fail on any machine without a database, including during test
        collection."""
        voice_app()
