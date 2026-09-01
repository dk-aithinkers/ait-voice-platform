"""The cascaded transport, extracted from the pipeline.

These pin the behaviour that used to live inline, so the extraction cannot
silently change it.
"""

from __future__ import annotations

from ait_voice.core.types import PHI, Region, TenantContext, Utterance
from ait_voice.providers.base import DialogSession, DialogTransport, ProviderSet
from ait_voice.providers.cascaded import CascadedTransport, transport_for
from ait_voice.providers.conversation_relay import ConversationRelayTransport
from ait_voice.providers.offline import (
    CollectingSink,
    OfflineLLM,
    OfflineSTT,
    OfflineTelephony,
    OfflineTTS,
)


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="t", region=Region.US)


def _set(**overrides) -> ProviderSet:  # noqa: ANN003
    base = {
        "stt": OfflineSTT(script=["hello"]),
        "llm": OfflineLLM(),
        "tts": OfflineTTS(),
        "telephony": OfflineTelephony(),
    }
    return ProviderSet(**{**base, **overrides})


class TestSelection:
    def test_a_plain_set_gets_the_cascade(self) -> None:
        assert isinstance(transport_for(_set()), CascadedTransport)

    def test_a_bundle_wins_when_configured(self) -> None:
        relay = ConversationRelayTransport()
        assert transport_for(_set(dialog=relay)) is relay

    def test_the_cascade_satisfies_the_protocol(self) -> None:
        assert isinstance(_set() and CascadedTransport(_set()), DialogTransport)

    def test_it_names_the_vendors_it_composed(self) -> None:
        """The name is provenance — it should say which chain actually ran."""
        name = CascadedTransport(_set()).name
        assert "offline-stt" in name and "offline-tts" in name


class TestSession:
    async def test_it_satisfies_the_protocol(self) -> None:
        session = await CascadedTransport(_set()).open(_tenant(), "c-1")
        assert isinstance(session, DialogSession)

    async def test_interim_results_are_filtered_out(self) -> None:
        """The dialog policy has no use for a half-recognised sentence."""

        class PartialSTT(OfflineSTT):
            async def transcribe(self, tenant, audio, *, language=None):  # noqa: ANN001
                yield Utterance(text=PHI("boo"), is_final=False)
                yield Utterance(text=PHI("booking"), is_final=False)
                yield Utterance(text=PHI("booking please"), is_final=True)

        session = await CascadedTransport(_set(stt=PartialSTT())).open(_tenant(), "c-2")

        heard = [u.text.reveal() async for u in session.listen()]

        assert heard == ["booking please"]

    async def test_speaking_observes_time_to_first_audio(self) -> None:
        session = await CascadedTransport(_set()).open(_tenant(), "c-3")

        timing = await session.speak(Utterance(text=PHI("a reply worth timing")))

        assert timing.observed_audio is True
        assert timing.elapsed_ms > 0

    async def test_silent_synthesis_reports_elapsed_rather_than_zero(self) -> None:
        """A zero here would quietly improve the p95 instead of showing a fault."""

        class SilentTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                return
                yield b""  # pragma: no cover - unreachable, defines the generator

        session = await CascadedTransport(_set(tts=SilentTTS())).open(_tenant(), "c-4")

        timing = await session.speak(Utterance(text=PHI("nothing comes back")))

        assert timing.elapsed_ms > 0
        assert timing.observed_audio is True

    async def test_audio_reaches_the_sink(self) -> None:
        transport = CascadedTransport(_set())
        session = await transport.open(_tenant(), "c-5")

        await session.speak(Utterance(text=PHI("some words to synthesise")))

        sink = session._sink  # noqa: SLF001
        assert isinstance(sink, CollectingSink)
        assert sink.total_bytes > 0

    async def test_closing_closes_the_sink(self) -> None:
        session = await CascadedTransport(_set()).open(_tenant(), "c-6")
        await session.close()
        sink = session._sink  # noqa: SLF001
        assert isinstance(sink, CollectingSink)
        assert sink.closed


class TestProviderSetDescribe:
    def test_a_cascade_names_four_legs(self) -> None:
        assert set(_set().describe()) == {"stt", "llm", "tts", "telephony"}

    def test_a_bundle_names_the_dialog_and_the_llm_only(self) -> None:
        described = _set(dialog=ConversationRelayTransport()).describe()
        assert set(described) == {"dialog", "llm"}

    def test_is_bundled_reflects_the_choice(self) -> None:
        assert not _set().is_bundled
        assert _set(dialog=ConversationRelayTransport()).is_bundled
