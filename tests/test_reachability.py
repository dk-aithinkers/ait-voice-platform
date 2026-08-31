"""Credential verification, and the failure it exists to catch.

The bug being fixed: the doctor called a leg LIVE when its environment variable
was set, so a `.env` full of the string "test" reported four live legs and a
confident summary. These tests pin the distinction between configured and
working.
"""

from __future__ import annotations

import httpx
import pytest

from ait_voice.providers.reachability import (
    Reachability,
    _from_status,
    verify_all,
)

VENDOR_VARS = (
    "ANTHROPIC_API_KEY",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in VENDOR_VARS:
        monkeypatch.delenv(var, raising=False)


def _transport(status: int) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(status, json={}))


@pytest.fixture
def _mock_http(monkeypatch: pytest.MonkeyPatch):
    """Swap the client's transport, leaving the request-building code real."""

    def install(status: int) -> None:
        original = httpx.AsyncClient.__init__

        def patched(self, *args, **kwargs):  # noqa: ANN001, ANN202
            kwargs["transport"] = _transport(status)
            original(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)

    return install


class TestStatusInterpretation:
    def test_200_is_accepted(self) -> None:
        assert _from_status("x", 200).reachable

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_failures_say_the_key_is_rejected(self, status: int) -> None:
        result = _from_status("x", status)
        assert not result.reachable
        assert "rejected" in result.detail

    def test_429_is_distinguished_from_a_bad_key(self) -> None:
        """Regenerating a key that was rate limited wastes an afternoon."""
        result = _from_status("x", 429)
        assert not result.reachable
        assert "quota" in result.detail or "rate limited" in result.detail


class TestVerdicts:
    def test_unconfigured_is_not_reported_as_failed(self) -> None:
        """Nothing set and something broken are different problems."""
        r = Reachability("x", configured=False, reachable=False, detail="not set")
        assert r.verdict == "not configured"

    def test_configured_but_rejected_is_failed(self) -> None:
        assert Reachability("x", True, False, "401").verdict == "FAILED"

    def test_working_is_ok(self) -> None:
        assert Reachability("x", True, True, "fine").verdict == "OK"


class TestVerifyAll:
    async def test_a_set_but_invalid_key_is_reported_failed(
        self, monkeypatch: pytest.MonkeyPatch, _mock_http
    ) -> None:
        """The exact case that misled: present, non-empty, and worthless."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        _mock_http(401)

        [result] = await verify_all(["anthropic"])

        assert result.configured
        assert not result.reachable

    async def test_a_valid_key_is_reported_ok(
        self, monkeypatch: pytest.MonkeyPatch, _mock_http
    ) -> None:
        monkeypatch.setenv("DEEPGRAM_API_KEY", "a-real-looking-key")
        _mock_http(200)

        [result] = await verify_all(["deepgram"])

        assert result.reachable

    async def test_an_unset_key_is_not_called_at_all(self) -> None:
        [result] = await verify_all(["elevenlabs"])

        assert not result.configured
        assert "ELEVENLABS_API_KEY" in result.detail

    async def test_twilio_sid_without_a_token_is_called_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A half-filled .env reads as configured everywhere else."""
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")

        [result] = await verify_all(["twilio"])

        assert not result.configured
        assert "AUTH_TOKEN" in result.detail

    async def test_a_network_failure_is_not_blamed_on_the_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fine-key")

        original = httpx.AsyncClient.__init__

        def patched(self, *args, **kwargs):  # noqa: ANN001, ANN202
            def boom(request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("no route to host")

            kwargs["transport"] = httpx.MockTransport(boom)
            original(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)

        [result] = await verify_all(["anthropic"])

        assert not result.reachable
        assert "could not reach" in result.detail

    async def test_every_vendor_is_checked_by_default(self) -> None:
        results = await verify_all()
        assert {r.provider for r in results} == {
            "anthropic",
            "deepgram",
            "elevenlabs",
            "twilio",
        }

    async def test_no_key_material_appears_in_any_detail(
        self, monkeypatch: pytest.MonkeyPatch, _mock_http
    ) -> None:
        """These lines get pasted into chats and tickets."""
        secret = "sk-super-secret-value-9999"
        monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
        _mock_http(401)

        [result] = await verify_all(["anthropic"])

        assert secret not in result.detail
        assert secret not in repr(result)
