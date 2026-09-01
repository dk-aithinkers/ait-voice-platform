"""The walking skeleton: ring, answer, converse, hang up.

These cover the requirements the skeleton actually implements — the disclosure
that must come first, the escalation paths, the region routing, and the latency
instrumentation. Booking, intake and outbound are not implemented yet and are
not tested here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import time

import pytest

from ait_voice.core.handoff import Urgency
from ait_voice.core.pipeline import (
    ESCALATE_CALLER_REQUEST,
    ESCALATE_CLINICAL,
    ESCALATE_DEPENDENCY,
    ESCALATE_NOT_UNDERSTOOD,
    CallEnding,
    VoicePipeline,
)
from ait_voice.core.tenancy import OutOfHoursPolicy, StaffedHours, TenantConfig
from ait_voice.core.types import PHI, Region, TenantContext, TurnTiming, Utterance
from ait_voice.providers.base import (
    ProviderRegistry,
    ProviderSet,
    UnregisteredRegionError,
)
from ait_voice.providers.offline import (
    CollectingSink,
    OfflineLLM,
    OfflineSTT,
    OfflineTelephony,
    OfflineTTS,
    offline_provider_set,
)


def _registry(region: Region, script: list[str]) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(region, offline_provider_set(script=script))
    return registry


def _tenant(region: Region = Region.US) -> TenantContext:
    return TenantContext(tenant_id="clinic-1", region=region)


class TestDisclosure:
    async def test_disclosure_is_spoken_before_anything_else(self) -> None:
        """FR1.3 — AI and recording disclosure precede all other content.

        Asserted by capturing what is synthesised, in order.
        """
        spoken: list[str] = []

        class RecordingTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                spoken.append(utterance.text.reveal())
                async for chunk in super().synthesize(tenant, utterance, voice=voice):
                    yield chunk

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["I'd like to book an appointment"]),
                llm=OfflineLLM(),
                tts=RecordingTTS(),
                telephony=OfflineTelephony(),
            ),
        )

        await VoicePipeline(registry, clinic_name="Northside").handle_call(_tenant(), "call-1")

        assert spoken, "nothing was spoken"
        first = spoken[0].lower()
        assert "ai assistant" in first
        assert "recorded" in first
        assert "northside" in first


class TestEscalation:
    async def test_caller_asking_for_a_person_escalates(self) -> None:
        """FR5.2 — honoured immediately, with no recovery attempt."""
        registry = _registry(Region.US, ["Can I speak to a person please?"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "call-2")

        assert result.escalated
        assert result.escalation_reason == str(ESCALATE_CALLER_REQUEST)
        assert result.turns == 1, "escalation should not take a recovery turn"

    async def test_clinical_content_escalates_without_answering(self) -> None:
        """FR5.2 and the scope exclusion on clinical advice."""
        registry = _registry(Region.US, ["I've had chest pain since this morning"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "call-3")

        assert result.escalated
        assert result.escalation_reason == str(ESCALATE_CLINICAL)

    async def test_ordinary_booking_does_not_escalate(self) -> None:
        registry = _registry(Region.US, ["I'd like to book an appointment"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "call-4")

        assert not result.escalated
        assert result.escalation_reason is None

    async def test_dependency_failure_escalates_and_speaks(self) -> None:
        """FR5.5 — dead air is the failure mode that matters on a live call."""
        spoken: list[str] = []

        class FailingLLM(OfflineLLM):
            async def respond(self, tenant, history, *, system_prompt):  # noqa: ANN001
                raise ConnectionError("vendor unreachable")

        class RecordingTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                spoken.append(utterance.text.reveal())
                async for chunk in super().synthesize(tenant, utterance, voice=voice):
                    yield chunk

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["Hello?"]),
                llm=FailingLLM(),
                tts=RecordingTTS(),
                telephony=OfflineTelephony(),
            ),
        )

        result = await VoicePipeline(registry).handle_call(_tenant(), "call-5")

        assert result.escalated
        assert result.escalation_reason == str(ESCALATE_DEPENDENCY)
        assert any("sorry" in s.lower() for s in spoken), "caller got silence, not an apology"


class TestRegionRouting:
    async def test_each_region_uses_its_own_providers(self) -> None:
        """C-T1 — no vendor serves both markets, so region selects the chain."""
        registry = ProviderRegistry()

        us = offline_provider_set(script=["hello"])
        india = ProviderSet(
            stt=OfflineSTT(script=["hello"]),
            llm=OfflineLLM(),
            tts=OfflineTTS(),
            telephony=OfflineTelephony(),
        )
        india.stt.name = "india-stt"

        registry.register(Region.US, us)
        registry.register(Region.INDIA, india)

        us_result = await VoicePipeline(registry).handle_call(_tenant(Region.US), "c-us")
        in_result = await VoicePipeline(registry).handle_call(_tenant(Region.INDIA), "c-in")

        assert us_result.providers["stt"] == "offline-stt"
        assert in_result.providers["stt"] == "india-stt"

    async def test_unregistered_region_fails_loudly(self) -> None:
        """Silently falling back would route audio to vendors with no BAA."""
        registry = ProviderRegistry()
        registry.register(Region.US, offline_provider_set(script=["hi"]))

        with pytest.raises(UnregisteredRegionError, match="india"):
            await VoicePipeline(registry).handle_call(_tenant(Region.INDIA), "c-6")


class TestLatencyMeasurement:
    async def test_every_turn_is_measured(self) -> None:
        registry = _registry(Region.US, ["book an appointment", "Tuesday please"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "call-7")

        assert len(result.timings) == result.turns
        assert all(t.total_ms > 0 for t in result.timings)

    def test_p95_is_none_without_turns(self) -> None:
        from ait_voice.core.pipeline import CallResult

        assert CallResult(call_id="c", tenant_id="t", region="us").p95_ms is None

    def test_p95_picks_the_tail(self) -> None:
        from ait_voice.core.pipeline import CallResult

        result = CallResult(call_id="c", tenant_id="t", region="us")
        result.timings = [
            TurnTiming(stt_ms=10, llm_ms=10, tts_first_audio_ms=10) for _ in range(19)
        ]
        result.timings.append(TurnTiming(stt_ms=900, llm_ms=900, tts_first_audio_ms=900))

        assert result.p95_ms == pytest.approx(2700.0)
        assert result.meets_latency_target is False

    def test_target_is_the_nfr_threshold(self) -> None:
        assert TurnTiming(stt_ms=400, llm_ms=600, tts_first_audio_ms=400).meets_target
        assert not TurnTiming(stt_ms=600, llm_ms=700, tts_first_audio_ms=300).meets_target


class TestCallResultCarriesNoPHI:
    async def test_result_fields_are_all_opaque(self) -> None:
        """A CallResult is logged and persisted, so it must hold no PHI.

        Only the textual fields are scanned. An earlier version rendered the
        whole ``__dict__`` and searched for ``1985`` — which a latency of
        1985 ms satisfies, failing a PHI test for a timing reason. Numbers
        here are durations and counts; content can only arrive as a string.
        """
        registry = _registry(Region.US, ["I'm Priya Sharma, born 1985-04-12"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "call-8")

        textual = [v for v in vars(result).values() if isinstance(v, str)]
        textual += [str(k) + str(v) for k, v in result.providers.items()]
        rendered = " ".join(textual)

        for fragment in ("Priya", "Sharma", "1985-04-12", "born"):
            assert fragment not in rendered, f"{fragment!r} leaked into CallResult"

        # And nothing textual is long enough to be transcript content.
        assert all(len(v) <= 64 for v in textual)


class TestOfflineProviders:
    async def test_sink_collects_audio(self) -> None:
        sink = CollectingSink()
        await sink.write(b"\x00" * 100)
        await sink.close()

        assert sink.total_bytes == 100
        assert sink.closed

    async def test_tts_streams_more_than_one_chunk(self) -> None:
        """Time to first audio only means something if audio is chunked."""
        tts = OfflineTTS(chunk_bytes=64)
        chunks = [
            c
            async for c in tts.synthesize(
                _tenant(), Utterance(text=PHI("a fairly long sentence to synthesise"))
            )
        ]
        assert len(chunks) > 1

    async def test_stt_yields_scripted_turns(self) -> None:
        stt = OfflineSTT(script=["one", "two"], latency_ms=1.0)

        async def audio() -> AsyncIterator[bytes]:
            yield b"\x00"

        turns = [u async for u in stt.transcribe(_tenant(), audio())]
        assert [t.text.reveal() for t in turns] == ["one", "two"]


class TestTenantConfigDrivesTheCall:
    """The tenant layer is only worth having if it changes what a caller hears."""

    async def test_greeting_comes_from_the_tenant(self) -> None:
        spoken: list[str] = []

        class RecordingTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                spoken.append(utterance.text.reveal())
                async for chunk in super().synthesize(tenant, utterance, voice=voice):
                    yield chunk

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["book an appointment"]),
                llm=OfflineLLM(),
                tts=RecordingTTS(),
                telephony=OfflineTelephony(),
            ),
        )
        config = TenantConfig(
            tenant_id="clinic-1",
            region=Region.US,
            clinic_name="Northside Medical",
            greeting="You've reached the front desk.",
        )

        await VoicePipeline(registry, config=config).handle_call(config.context(), "c-9")

        assert "You've reached the front desk." in spoken[0]

    async def test_the_disclosure_still_precedes_a_configured_greeting(self) -> None:
        """C-R3/C-R4 are not configurable — no greeting can displace them."""
        config = TenantConfig(
            tenant_id="clinic-1",
            region=Region.US,
            clinic_name="Northside",
            greeting="How may I help?",
        )
        pipeline = VoicePipeline(_registry(Region.US, ["hi"]), config=config)

        opening = pipeline._opening()

        assert opening.index("AI assistant") < opening.index("How may I help?")
        assert "recorded" in opening.lower()

    async def test_escalation_routes_to_the_number_when_staffed(self) -> None:
        config = TenantConfig(
            tenant_id="clinic-1",
            region=Region.US,
            clinic_name="Northside",
            staffed_hours=StaffedHours(
                days=frozenset(range(1, 8)), opens=time(0, 0), closes=time(23, 59)
            ),
            escalation_number="+15551230000",
        )
        registry = _registry(Region.US, ["Can I speak to a person please?"])

        result = await VoicePipeline(registry, config=config).handle_call(config.context(), "c-10")

        assert result.escalated
        assert result.escalation_route == "+15551230000"

    async def test_escalation_falls_to_the_policy_when_nobody_is_there(self) -> None:
        config = TenantConfig(
            tenant_id="clinic-1",
            region=Region.US,
            clinic_name="Northside",
            staffed_hours=StaffedHours.never(),
            escalation_number="+15551230000",
            out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
        )
        registry = _registry(Region.US, ["Can I speak to a person please?"])

        result = await VoicePipeline(registry, config=config).handle_call(config.context(), "c-11")

        assert result.escalation_route == "take_message"

    async def test_route_is_absent_without_a_config(self) -> None:
        """The skeleton demo has no tenant store; it must still run."""
        registry = _registry(Region.US, ["Can I speak to a person please?"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "c-12")

        assert result.escalated
        assert result.escalation_route is None


class TestRecoveryThenEscalate:
    """FR5.1 — one recovery attempt, then a person."""

    @staticmethod
    def _confused_registry(turns: int) -> ProviderRegistry:
        class ConfusedLLM(OfflineLLM):
            async def respond(self, tenant, history, *, system_prompt):  # noqa: ANN001
                return Utterance(text=PHI("Sorry, I didn't catch that."))

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["mumble"] * turns),
                llm=ConfusedLLM(),
                tts=OfflineTTS(),
                telephony=OfflineTelephony(),
            ),
        )
        return registry

    async def test_the_first_failure_is_a_recovery_attempt_not_an_escalation(
        self,
    ) -> None:
        result = await VoicePipeline(self._confused_registry(1)).handle_call(_tenant(), "c-r1")

        assert result.recovery_attempted
        assert not result.escalated

    async def test_the_second_failure_escalates(self) -> None:
        """A second attempt is where a caller decides the thing is broken."""
        result = await VoicePipeline(self._confused_registry(2)).handle_call(_tenant(), "c-r2")

        assert result.escalated
        assert result.escalation_reason == str(ESCALATE_NOT_UNDERSTOOD)
        assert result.handoff.recovery_attempted

    async def test_a_request_for_a_person_skips_recovery_entirely(self) -> None:
        """FR5.2 — immediately, with no recovery attempt."""
        registry = _registry(Region.US, ["Can I speak to a person please?"])

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-r3")

        assert result.escalated
        assert not result.recovery_attempted


class TestNeverEndsUnresolved:
    """FR5.6 — never end a call without a task, a transfer, or a message."""

    async def test_an_escalated_call_is_resolved(self) -> None:
        registry = _registry(Region.US, ["Can I speak to a person please?"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "c-e1")

        assert result.resolved
        assert result.ending is CallEnding.ESCALATED
        assert result.handoff_method

    async def test_a_caller_hanging_up_is_not_a_violation(self) -> None:
        """The requirement is about the system ending a call, not the caller."""
        registry = _registry(Region.US, ["I'd like to book an appointment"])
        result = await VoicePipeline(registry).handle_call(_tenant(), "c-e2")

        assert result.ending is CallEnding.CALLER_ENDED

    async def test_the_turn_limit_still_hands_off(self) -> None:
        """Running out of turns is the agent's problem, not the caller's."""
        registry = _registry(Region.US, ["hello"] * 6)

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-e3", max_turns=2)

        assert result.escalated
        assert result.ending is CallEnding.ESCALATED

    async def test_a_dependency_failure_hands_off_after_apologising(self) -> None:
        """AC5.5.1 — the apology comes first; the briefing is built after."""
        spoken: list[str] = []

        class FailingLLM(OfflineLLM):
            async def respond(self, tenant, history, *, system_prompt):  # noqa: ANN001
                raise ConnectionError("vendor unreachable")

        class RecordingTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                spoken.append(utterance.text.reveal())
                async for chunk in super().synthesize(tenant, utterance, voice=voice):
                    yield chunk

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["Hello?"]),
                llm=FailingLLM(),
                tts=RecordingTTS(),
                telephony=OfflineTelephony(),
            ),
        )

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-e4")

        assert result.escalated
        assert result.resolved
        assert result.handoff.urgency is Urgency.URGENT
        # The apology precedes the handoff promise.
        assert "sorry" in spoken[1].lower()


class TestHandoffCarriesContext:
    """C-T6 — a transfer that makes the caller repeat everything wastes the
    one thing that earns acceptance."""

    async def test_the_briefing_carries_what_the_caller_said(self) -> None:
        registry = _registry(Region.US, ["I've had chest pain since this morning"])

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-h1")

        said = result.handoff.for_human()["said"]
        assert any("chest pain" in line for line in said)

    async def test_the_briefing_omits_the_agents_own_replies(self) -> None:
        """Including them doubles what a person has to read."""
        registry = _registry(Region.US, ["Can I speak to a person please?"])

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-h2")

        said = result.handoff.for_human()["said"]
        assert not any("put you through" in line.lower() for line in said)

    async def test_clinical_content_is_marked_urgent_for_a_person(self) -> None:
        registry = _registry(Region.US, ["I've had chest pain since this morning"])

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-h3")

        assert result.handoff.urgency is Urgency.CLINICAL

    async def test_the_result_itself_still_carries_no_phi_when_logged(self) -> None:
        """CallResult is logged; the briefing must not ride along in its repr."""
        registry = _registry(Region.US, ["I've had chest pain since this morning"])

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-h4")

        assert "chest pain" not in repr(result)

    async def test_availability_decides_the_method(self) -> None:
        from datetime import time as clock

        from ait_voice.core.tenancy import OutOfHoursPolicy, StaffedHours

        always = StaffedHours(days=frozenset(range(1, 8)), opens=clock(0, 0), closes=clock(23, 59))
        for hours, expected in (
            (always, "transferred"),
            (StaffedHours.never(), "message_taken"),
        ):
            config = TenantConfig(
                tenant_id="clinic-1",
                region=Region.US,
                clinic_name="Northside",
                staffed_hours=hours,
                escalation_number="+15551230000",
                out_of_hours=OutOfHoursPolicy.TAKE_MESSAGE,
            )
            registry = _registry(Region.US, ["Can I speak to a person please?"])

            result = await VoicePipeline(registry, config=config).handle_call(
                config.context(), "c-h5"
            )

            assert result.handoff_method == expected


class TestHandoffFailureIsNotMasked:
    async def test_a_handoff_that_itself_fails_still_records_the_escalation(
        self,
    ) -> None:
        """Two failures in a row must not leave the call looking healthy."""

        class FailingLLM(OfflineLLM):
            async def respond(self, tenant, history, *, system_prompt):  # noqa: ANN001
                raise ConnectionError("vendor unreachable")

        class FailingTTS(OfflineTTS):
            async def synthesize(self, tenant, utterance, *, voice=None):  # noqa: ANN001
                raise ConnectionError("tts unreachable")
                yield b""  # pragma: no cover - defines the generator

        registry = ProviderRegistry()
        registry.register(
            Region.US,
            ProviderSet(
                stt=OfflineSTT(script=["Hello?"]),
                llm=FailingLLM(),
                tts=FailingTTS(),
                telephony=OfflineTelephony(),
            ),
        )

        result = await VoicePipeline(registry).handle_call(_tenant(), "c-double")

        assert result.escalated
        assert result.escalation_reason == str(ESCALATE_DEPENDENCY)

    async def test_an_unaccounted_ending_raises(self) -> None:
        """FR5.6's backstop, exercised directly.

        A future `break` added without resolving the call would land here, and
        the point of the invariant is that it fails loudly instead of dropping
        a caller silently.
        """
        from ait_voice.core.handoff import UnresolvedCall
        from ait_voice.core.pipeline import CallResult

        registry = _registry(Region.US, ["hello"])
        pipeline = VoicePipeline(registry)

        # Simulate the loop exiting without setting an ending.
        original = CallResult.__init__

        def unresolved(self, *args, **kwargs):  # noqa: ANN001, ANN202
            original(self, *args, **kwargs)
            self.ending = None

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                "ait_voice.core.pipeline.VoicePipeline._escalate",
                _leave_unresolved,
            )
            with pytest.raises(UnresolvedCall, match="FR5.6"):
                await pipeline.handle_call(_tenant(), "c-unresolved", max_turns=1)


async def _leave_unresolved(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
    """An _escalate that forgets to record the ending — the defect FR5.6 guards."""
    return None
