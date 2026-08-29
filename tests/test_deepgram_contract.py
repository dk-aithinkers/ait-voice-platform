"""Contract tests for the Deepgram adapter.

This adapter is event-driven rather than request/response, so its translation
logic — vendor callback to domain :class:`Utterance`, and the queue that turns
callbacks back into an async iterator — is where the bugs would live. A fake
client exercises exactly that without a credential or a socket.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ait_voice.core.types import PHI, Region, TenantContext


def _india() -> TenantContext:
    return TenantContext(tenant_id="clinic-in", region=Region.INDIA)


class _FakeAlternative:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript


class _FakeChannel:
    def __init__(self, transcripts: list[str]) -> None:
        self.alternatives = [_FakeAlternative(t) for t in transcripts]


class _FakeResult:
    def __init__(self, transcripts: list[str], is_final: bool = True) -> None:
        self.channel = _FakeChannel(transcripts)
        self.is_final = is_final


class _FakeLiveClient:
    """Replays scripted recognition events once audio starts flowing."""

    def __init__(self, _api_key: str) -> None:
        self._handlers: dict[str, Any] = {}
        self.sent: list[bytes] = []
        self.started_with: Any = None
        self.finished = False
        #: Set by the test before use.
        self.script: list[_FakeResult] = []

    def on(self, event: str, handler: Any) -> None:
        self._handlers[event] = handler

    async def start(self, options: Any) -> None:
        self.started_with = options

    async def send(self, chunk: bytes) -> None:
        self.sent.append(chunk)
        # Emit the scripted results as soon as the first audio arrives, which
        # is when a real client would begin returning interim transcripts.
        if len(self.sent) == 1:
            for result in self.script:
                await self._handlers["Results"](self, result)

    async def finish(self) -> None:
        self.finished = True
        await self._handlers["Close"](self)


@pytest.fixture
def stt(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    from ait_voice.providers.deepgram_stt import DeepgramSTT

    return DeepgramSTT(model="test-model", sample_rate=8000)


async def _audio(chunks: int = 2):  # noqa: ANN202
    for _ in range(chunks):
        yield b"\x00" * 160
        await asyncio.sleep(0)


def _install_fake(monkeypatch: pytest.MonkeyPatch, script: list[_FakeResult]) -> list:
    """Patch the vendor SDK symbols the adapter imports lazily."""
    created: list[_FakeLiveClient] = []

    def factory(api_key: str) -> _FakeLiveClient:
        client = _FakeLiveClient(api_key)
        client.script = script
        created.append(client)
        return client

    import sys
    import types

    fake_module = types.ModuleType("deepgram")
    fake_module.AsyncLiveClient = factory  # type: ignore[attr-defined]
    fake_module.LiveOptions = lambda **kw: kw  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "deepgram", fake_module)
    return created


class TestDeepgramContract:
    async def test_transcripts_become_utterances(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        _install_fake(monkeypatch, [_FakeResult(["book an appointment"])])

        turns = [u async for u in stt.transcribe(_india(), _audio())]

        assert len(turns) == 1
        assert turns[0].text.reveal() == "book an appointment"

    async def test_recognised_text_is_wrapped_as_phi(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """A transcript is PHI the moment it exists, not once it is stored."""
        _install_fake(monkeypatch, [_FakeResult(["my name is Priya Sharma"])])

        turns = [u async for u in stt.transcribe(_india(), _audio())]

        assert isinstance(turns[0].text, PHI)
        assert str(turns[0].text) == "[REDACTED]"

    async def test_interim_results_are_marked_not_final(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """The pipeline uses finals for the dialog turn and interims for barge-in."""
        _install_fake(
            monkeypatch,
            [_FakeResult(["book an"], is_final=False), _FakeResult(["book an appointment"])],
        )

        turns = [u async for u in stt.transcribe(_india(), _audio())]

        assert [t.is_final for t in turns] == [False, True]

    async def test_empty_transcripts_are_dropped(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """Silence produces empty results; they are not turns."""
        _install_fake(
            monkeypatch, [_FakeResult([""]), _FakeResult(["hello"]), _FakeResult([])]
        )

        turns = [u async for u in stt.transcribe(_india(), _audio())]

        assert [t.text.reveal() for t in turns] == ["hello"]

    async def test_audio_reaches_the_vendor(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        created = _install_fake(monkeypatch, [_FakeResult(["hi"])])

        [u async for u in stt.transcribe(_india(), _audio(chunks=3))]

        assert len(created[0].sent) == 3
        assert created[0].finished, "the vendor stream must be closed"

    async def test_telephony_audio_settings_are_requested(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """8kHz mulaw is what carriers deliver — not the studio audio benchmarks use."""
        created = _install_fake(monkeypatch, [_FakeResult(["hi"])])

        [u async for u in stt.transcribe(_india(), _audio())]

        options = created[0].started_with
        assert options["encoding"] == "mulaw"
        assert options["sample_rate"] == 8000
        assert options["channels"] == 1

    async def test_language_defaults_to_multi_for_code_switching(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """`multi` is the mode that handles Hindi-English switching at all."""
        created = _install_fake(monkeypatch, [_FakeResult(["hi"])])

        [u async for u in stt.transcribe(_india(), _audio())]

        assert created[0].started_with["language"] == "multi"

    async def test_explicit_language_overrides_the_default(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        created = _install_fake(monkeypatch, [_FakeResult(["hi"])])

        [u async for u in stt.transcribe(_india(), _audio(), language="en-US")]

        assert created[0].started_with["language"] == "en-US"

    async def test_endpointing_is_configured(
        self, stt, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN001
        """Waiting for the vendor's end-of-turn beats a fixed silence timeout."""
        created = _install_fake(monkeypatch, [_FakeResult(["hi"])])

        [u async for u in stt.transcribe(_india(), _audio())]

        assert created[0].started_with["endpointing"] == 300
