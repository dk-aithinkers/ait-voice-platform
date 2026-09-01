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
from enum import StrEnum

from ait_voice.core.handoff import (
    HandoffContext,
    HandoffDecision,
    HandoffMethod,
    UnresolvedCall,
    decide_handoff,
    spoken_promise,
    urgency_for,
)
from ait_voice.core.logging import CallLogger
from ait_voice.core.tenancy import TenantConfig
from ait_voice.core.types import PHI, TenantContext, TurnTiming, Utterance
from ait_voice.providers.base import ProviderRegistry, ProviderSet
from ait_voice.providers.cascaded import transport_for

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


class CallEnding(StrEnum):
    """How a call finished.

    Recorded because FR5.6 is about the *system* ending a call, not about the
    caller ending one. A caller who hangs up mid-sentence has not been failed;
    an agent that stops talking and drops them has. Without this distinction
    the invariant either never fires or fires constantly, and neither is a
    check worth having.
    """

    #: The caller stopped speaking or hung up. Their choice, not a failure.
    CALLER_ENDED = "caller_ended"
    #: Handed to a person, or a message taken.
    ESCALATED = "escalated"
    #: What the caller rang for was done.
    TASK_COMPLETED = "task_completed"


class EscalationReason(str):
    """Why a call left the agent. Values are opaque and safe to log."""


#: What the agent says when it did not catch something. One attempt only.
RECOVERY_PROMPT = "Sorry, I didn't catch that. Could you say it once more?"

#: Substrings that mark the model as not having understood. Crude, and the
#: same deliberate simplification as _escalation_reason: a real implementation
#: classifies the caller's utterance rather than reading the agent's reply.
NOT_UNDERSTOOD_MARKERS = ("didn't catch", "did not catch", "didn't understand")

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
    #: Where the escalation went — a transfer number, or the out-of-hours
    #: policy that applied because nobody was available. Opaque; safe to log.
    escalation_route: str | None = None
    #: How the call actually left the agent, once it escalated. None while the
    #: agent still holds the call.
    handoff_method: str | None = None
    #: The briefing handed to whoever picks the call up. Carries PHI, so it is
    #: excluded from anything that logs a CallResult.
    handoff: HandoffContext | None = field(default=None, repr=False)
    #: True once the caller's task was completed, a transfer happened, or a
    #: message was taken. FR5.6 forbids ending a call with none of the three.
    resolved: bool = False
    #: One recovery attempt was made before escalating — FR5.1.
    recovery_attempted: bool = False
    #: How the call finished. None means the loop exited a way this pipeline
    #: does not account for, which FR5.6 treats as a defect.
    ending: CallEnding | None = None
    providers: dict[str, str] = field(default_factory=dict)
    #: False when the transport hands text to a vendor that synthesises
    #: downstream, so the reply-latency column stops short of the audio the
    #: caller hears. NFR1.1 numbers from such a run are a floor, not a
    #: measurement, and must not be compared against a cascaded run as equals.
    latency_observable: bool = True

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

    def __init__(
        self,
        registry: ProviderRegistry,
        *,
        clinic_name: str = "the clinic",
        config: TenantConfig | None = None,
    ) -> None:
        """
        Args:
            config: The tenant's configuration. When supplied it drives the
                greeting and the escalation route, so a call behaves the way
                that clinic is set up rather than the way the default is.
                ``clinic_name`` remains for the skeleton demo, which has no
                tenant store behind it.
        """
        self._registry = registry
        self._config = config
        self._clinic_name = config.clinic_name if config else clinic_name

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

        transport = transport_for(providers)
        result.latency_observable = transport.observes_audio
        session = await transport.open(tenant, call_id)
        history: list[Utterance] = []

        try:
            # FR1.3 — disclosure first, before anything else is spoken.
            await session.speak(Utterance(text=PHI(self._opening())))
            log.info("disclosure spoken")

            # NFR1.1 measures from the caller ceasing speech to the first
            # audio of the reply. The recognition wait happens *inside* the
            # async-for, before an utterance is yielded, so the clock has to
            # start before the loop body — not after.
            listening_since = time.perf_counter()

            async for caller in session.listen():
                stt_ms = (time.perf_counter() - listening_since) * 1000
                history.append(caller)

                llm_start = time.perf_counter()
                reply = await providers.llm.respond(
                    tenant, history, system_prompt=SYSTEM_PROMPT
                )
                llm_ms = (time.perf_counter() - llm_start) * 1000

                spoken = await session.speak(reply)
                tts_ms = spoken.elapsed_ms

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

                # FR5.1 — one recovery attempt when the agent did not
                # understand, then escalate. A second attempt is where a caller
                # decides the thing is broken; escalating on the second failure
                # is the point of allowing a first.
                if self._not_understood(reply):
                    if not result.recovery_attempted:
                        result.recovery_attempted = True
                        log.info("recovery attempt")
                    else:
                        await self._escalate(
                            tenant, session, result, ESCALATE_NOT_UNDERSTOOD,
                            history, log,
                        )
                        break

                # FR5.2 — a request for a person or clinical content escalates
                # immediately, with no recovery attempt.
                elif reason := self._escalation_reason(reply):
                    await self._escalate(tenant, session, result, reason, history, log)
                    break

                if result.turns >= max_turns:
                    log.info("turn limit reached", limit=max_turns)
                    # Reaching the limit still owes the caller a resolution.
                    await self._escalate(
                        tenant, session, result, ESCALATE_NOT_UNDERSTOOD, history, log
                    )
                    break

                listening_since = time.perf_counter()
            else:
                # The caller's stream ended on its own: they stopped speaking
                # or hung up. Not a failure, and not something the agent can
                # resolve on their behalf.
                if result.ending is None:
                    result.ending = CallEnding.CALLER_ENDED
                    result.resolved = True

        except Exception as exc:
            # FR5.5 — a dependency failure mid-call routes to escalation with a
            # spoken apology. Dead air is the failure mode that matters on a
            # live call, so the caller is told something before the handoff.
            log.error("dependency failure", error_type=type(exc).__name__)
            try:
                # The apology comes first and the briefing is assembled after,
                # because AC5.5.1 budgets three seconds from failure to spoken
                # apology and the caller is listening to silence until then.
                await session.speak(
                    Utterance(
                        text=PHI("I'm sorry — I'm having trouble. Let me get you to someone.")
                    )
                )
            except Exception:  # noqa: BLE001 - the apology is best-effort
                log.error("could not speak apology")
            try:
                await self._escalate(
                    tenant, session, result, ESCALATE_DEPENDENCY, history, log,
                    speak_promise=False,
                )
            except Exception:  # noqa: BLE001 - never mask the original failure
                log.error("could not complete handoff after dependency failure")
                result.escalated = True
                result.escalation_reason = str(ESCALATE_DEPENDENCY)
        finally:
            await session.close()

        if result.ending is None:
            # FR5.6 — the agent must never end a call without the caller's task
            # done, a transfer, or a message. Reaching here means the loop
            # exited a way this method does not account for, which is a defect
            # rather than a caller hanging up. Failing loudly beats a caller
            # dropped with nothing recorded.
            raise UnresolvedCall(
                f"call {result.call_id!r} ended after {result.turns} turn(s) with "
                "no completed task, transfer, or message (FR5.6)"
            )

        log.info(
            "call ended",
            turns=result.turns,
            escalated=result.escalated,
            ending=str(result.ending) if result.ending else None,
            handoff=result.handoff_method,
            p95_ms=round(result.p95_ms, 1) if result.p95_ms else None,
        )
        return result

    async def _escalate(
        self,
        tenant: TenantContext,
        session,  # noqa: ANN001 - DialogSession protocol
        result: CallResult,
        reason: EscalationReason,
        history: list[Utterance],
        log: CallLogger,
        *,
        speak_promise: bool = True,
    ) -> None:
        """Hand the call to a person, carrying what the caller said — C-T6.

        Every exit from the dialog goes through here, so there is one place
        that decides where a call goes and one place that records it. A second
        path would be a second chance to end a call with nothing recorded.
        """
        result.escalated = True
        result.escalation_reason = str(reason)

        decision = (
            decide_handoff(self._config)
            if self._config
            # With no tenant config the skeleton has no staffed hours to read,
            # so it cannot claim a person is available.
            else HandoffDecision(method=HandoffMethod.MESSAGE_TAKEN)
        )
        result.handoff_method = str(decision.method)
        result.escalation_route = decision.transfer_to or (
            str(decision.policy) if decision.policy else None
        )
        result.handoff = HandoffContext(
            call_id=result.call_id,
            tenant_id=tenant.tenant_id,
            reason=str(reason),
            urgency=urgency_for(str(reason)),
            # Only the caller's turns. The agent's own replies are not context
            # a person needs, and including them doubles what they must read.
            said=tuple(u.text for u in history[::2]),
            turns=result.turns,
            recovery_attempted=result.recovery_attempted,
        )

        if speak_promise:
            await session.speak(Utterance(text=PHI(spoken_promise(decision))))

        # FR5.6 — the call now has a transfer or a message behind it.
        result.resolved = True
        result.ending = CallEnding.ESCALATED
        log.info(
            "escalating",
            reason=result.escalation_reason,
            method=result.handoff_method,
            urgency=str(result.handoff.urgency),
        )

    @staticmethod
    def _not_understood(reply: Utterance) -> bool:
        return any(
            marker in reply.text.reveal().lower() for marker in NOT_UNDERSTOOD_MARKERS
        )

    def _opening(self) -> str:
        """Disclosure first, then the tenant's greeting.

        The disclosure is prepended here rather than left to the greeting
        template, so no configuration can remove it. C-R3 and C-R4 are Firm
        constraints, and California AB 2905 requires the AI disclosure before
        the message rather than after it.
        """
        disclosure = DISCLOSURE_TEMPLATE.format(clinic=self._clinic_name)
        if self._config:
            return f"{disclosure} {self._config.greeting}"
        return disclosure

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
