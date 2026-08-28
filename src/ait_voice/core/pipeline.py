"""The cascaded voice pipeline: speech in, dialog, speech out.

Cascaded rather than speech-to-speech, per constraint C-T3. Speech-to-speech
wins on raw latency but loses on everything this system needs: cascading keeps
text at every stage, so each component is independently BAA-able and auditable,
prompts and guardrails work normally, and vendors stay swappable.

The turn loop is instrumented because NFR1.1 sets a measurable threshold —
under 1.5 seconds at p95 from the caller ceasing speech to the first audio of
the reply — and a threshold nobody measures is decoration.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from ait_voice.core.logging import CallLogger
from ait_voice.core.types import PHI, TenantContext, TurnTiming, Utterance
from ait_voice.providers.base import ProviderRegistry, ProviderSet

#: FR1.3 and FR1.4: the AI disclosure and the recording disclosure are spoken at
#: the start of every call, before any other content, and cannot be removed by
#: configuration. California AB 2905 requires the AI disclosure *before* the
#: message, not after it, which is why this is prepended by the pipeline rather
#: than left to the greeting template.
DISCLOSURE_TEMPLATE = (
    "You're speaking with an AI assistant at {clinic}, and this call is recorded."
)

SYSTEM_PROMPT = """You are a receptionist for a medical clinic.

You may help with: booking, rescheduling and cancelling appointments, and taking
basic intake details.

You must never: give medical advice, assess symptoms, discuss treatment, or
answer clinical questions. If a caller raises anything clinical or urgent, hand
off to a person immediately without attempting an answer.

If a caller asks for a person, hand off immediately. Do not try to resolve it
first.

Keep replies short. This is a phone call, not a chat window."""


class EscalationReason(str):
    """Why a call left the agent. Values are opaque and safe to log."""


ESCALATE_CALLER_REQUEST = EscalationReason("caller_requested_human")
ESCALATE_CLINICAL = EscalationReason("clinical_content")
ESCALATE_NOT_UNDERSTOOD = EscalationReason("not_understood_after_recovery")
ESCALATE_DEPENDENCY = EscalationReason("dependency_failure")


@dataclass
class CallResult:
    """What happened on a call. Contains no PHI — safe to log and persist."""

    call_id: str
    tenant_id: str
    region: str
    turns: int = 0
    timings: list[TurnTiming] = field(default_factory=list)
    escalated: bool = False
    escalation_reason: str | None = None
    providers: dict[str, str] = field(default_factory=dict)

    @property
    def p95_ms(self) -> float | None:
        """95th percentile end-to-end turn latency, as NFR1.1 measures it."""
        if not self.timings:
            return None
        ordered = sorted(t.total_ms for t in self.timings)
        idx = min(int(len(ordered) * 0.95), len(ordered) - 1)
        return ordered[idx]

    @property
    def meets_latency_target(self) -> bool | None:
        p95 = self.p95_ms
        return None if p95 is None else p95 < 1500.0


class VoicePipeline:
    """Runs one call end to end.

    This is the walking skeleton: ring, answer, converse, hang up. It does not
    book appointments, take intake, or place outbound calls. It exists to prove
    the vendor chain holds together and to measure what it costs.
    """

    def __init__(self, registry: ProviderRegistry, *, clinic_name: str = "the clinic") -> None:
        self._registry = registry
        self._clinic_name = clinic_name

    async def handle_call(
        self,
        tenant: TenantContext,
        call_id: str,
        *,
        max_turns: int = 8,
    ) -> CallResult:
        """Answer a call, converse, and return what happened."""
        providers: ProviderSet = self._registry.for_tenant(tenant)
        log = CallLogger.for_call(__name__, tenant, call_id)
        result = CallResult(
            call_id=call_id,
            tenant_id=tenant.tenant_id,
            region=tenant.region.value,
            providers=providers.describe(),
        )
        log.info("call started", providers=result.providers)

        inbound, sink = await providers.telephony.stream(tenant, call_id)
        history: list[Utterance] = []

        try:
            # FR1.3 — disclosure first, before anything else is spoken.
            await self._speak(
                tenant,
                providers,
                sink,
                Utterance(text=PHI(DISCLOSURE_TEMPLATE.format(clinic=self._clinic_name))),
            )
            log.info("disclosure spoken")

            # NFR1.1 measures from the caller ceasing speech to the first
            # audio of the reply. The recognition wait happens *inside* the
            # async-for, before an utterance is yielded, so the clock has to
            # start before the loop body — not after.
            listening_since = time.perf_counter()

            async for caller in providers.stt.transcribe(tenant, inbound):
                if not caller.is_final:
                    continue

                stt_ms = (time.perf_counter() - listening_since) * 1000
                history.append(caller)

                llm_start = time.perf_counter()
                reply = await providers.llm.respond(
                    tenant, history, system_prompt=SYSTEM_PROMPT
                )
                llm_ms = (time.perf_counter() - llm_start) * 1000

                tts_start = time.perf_counter()
                first_audio_ms = await self._speak(tenant, providers, sink, reply)
                tts_ms = first_audio_ms if first_audio_ms else (
                    time.perf_counter() - tts_start
                ) * 1000

                history.append(reply)
                result.turns += 1
                result.timings.append(
                    TurnTiming(stt_ms=stt_ms, llm_ms=llm_ms, tts_first_audio_ms=tts_ms)
                )
                log.info(
                    "turn complete",
                    turn=result.turns,
                    total_ms=round(result.timings[-1].total_ms, 1),
                    met_target=result.timings[-1].meets_target,
                )

                if reason := self._escalation_reason(reply):
                    result.escalated = True
                    result.escalation_reason = str(reason)
                    log.info("escalating", reason=result.escalation_reason)
                    break

                if result.turns >= max_turns:
                    log.info("turn limit reached", limit=max_turns)
                    break

                listening_since = time.perf_counter()

        except Exception as exc:
            # FR5.5 — a dependency failure mid-call routes to escalation with a
            # spoken apology. Dead air is the failure mode that matters on a
            # live call, so the caller is told something before the handoff.
            result.escalated = True
            result.escalation_reason = str(ESCALATE_DEPENDENCY)
            log.error("dependency failure", error_type=type(exc).__name__)
            try:
                await self._speak(
                    tenant,
                    providers,
                    sink,
                    Utterance(
                        text=PHI("I'm sorry — I'm having trouble. Let me get you to someone.")
                    ),
                )
            except Exception:  # noqa: BLE001 - the apology is best-effort
                log.error("could not speak apology")
        finally:
            await sink.close()

        log.info(
            "call ended",
            turns=result.turns,
            escalated=result.escalated,
            p95_ms=round(result.p95_ms, 1) if result.p95_ms else None,
        )
        return result

    async def _speak(
        self,
        tenant: TenantContext,
        providers: ProviderSet,
        sink,  # noqa: ANN001 - AudioSink protocol
        utterance: Utterance,
    ) -> float:
        """Synthesise and play an utterance. Returns time to first audio, in ms."""
        started = time.perf_counter()
        first_audio_ms = 0.0
        async for chunk in providers.tts.synthesize(tenant, utterance):
            if first_audio_ms == 0.0:
                first_audio_ms = (time.perf_counter() - started) * 1000
            await sink.write(chunk)
        return first_audio_ms

    @staticmethod
    def _escalation_reason(reply: Utterance) -> EscalationReason | None:
        """Detect that the agent has decided to hand off.

        Reading the agent's own reply is a deliberate simplification for the
        skeleton. A real implementation classifies the *caller's* utterance
        rather than inferring from the response — that arrives with the
        healthcare pack, not here.
        """
        text = reply.text.reveal().lower()
        if "put you through" in text:
            return ESCALATE_CALLER_REQUEST
        if "not able to advise" in text:
            return ESCALATE_CLINICAL
        return None


async def collect(stream: AsyncIterator[bytes]) -> bytes:
    """Drain an audio stream into a single buffer. Test helper."""
    out = bytearray()
    async for chunk in stream:
        out.extend(chunk)
    return bytes(out)
