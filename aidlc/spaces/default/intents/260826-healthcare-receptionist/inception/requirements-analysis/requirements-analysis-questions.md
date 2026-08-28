# Requirements Analysis — Questions

**Mode:** guided

## Context

Six ideation stages and the affirmed practices already settle most of what this
stage would normally ask. Scope, capabilities, exclusions, constraints, risks,
call flows and testing posture are all decided and are not re-asked.

**What requirements analysis cannot proceed without is numbers.** The intent
statement names three success metrics with no targets and no measurement
windows, recorded as I-02 and flagged Major by the product-lead review at intent
capture. Acceptance criteria must have a pass/fail threshold — the inception
guardrails require every requirement to be testable — and none can be written
against "improved" anything.

Several questions below carry a **recommended answer** with reasoning, because
they are technical thresholds where a default is more useful than an open
question. Confirm, adjust, or reject each.

---

## Q1. What are the numeric targets for the three success metrics?

The metrics are call answer rate, appointments booked or recovered with no-show
reduction, and front-desk staff hours saved per week. No baseline exists for any
of them, because no pilot clinic has been observed.

A. Set provisional targets now, marked provisional, to be replaced by real numbers once a pilot clinic provides a baseline.
B. Define the *measurement* now — what is counted, over what window, from what point — and leave the target numbers until a baseline exists.
C. Set firm targets now and hold the product to them.
D. Defer entirely; requirements will carry the metrics without thresholds.
X. Other (please specify)

**Recommendation: B.** A target without a baseline is invented, and this project
has a standing practice against producing figures the evidence cannot support.
But the *definition* — "a call is answered when audio is established within N
rings", "hours saved is measured against the two weeks before go-live" — can be
fixed now, is what acceptance criteria actually need, and is what makes the
baseline measurable when a clinic appears.

[Answer]: B. Define the *measurement* now — what is counted, over what window, from what point — and leave the target numbers until a baseline exists.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q2. What is the conversational latency requirement?

`docs/vendors.md` records independently measured time-to-first-audio of 188–337ms
across TTS vendors and roughly 300ms for streaming speech-to-text, and notes that
above roughly 300ms total, conversation stops feeling live.

A. Target end-to-end response under 1.5 seconds from caller stopping speech to agent audio starting, measured at p95.
B. Under 1 second at p95 — aggressive, constrains vendor choice significantly.
C. Under 2.5 seconds at p95 — comfortable, risks the agent feeling slow.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** 1.5s at p95 is achievable with the cascaded pipeline the
constraint register mandates, leaves headroom for the model call, and is the
threshold above which callers start talking over the agent. p95 rather than
average because the tail is what people remember.

[Answer]: A. Target end-to-end response under 1.5 seconds from caller stopping speech to agent audio starting, measured at p95.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q3. What availability target applies to a 24/7 answering service?

The product exists because calls go unanswered. An agent that is down is
indistinguishable from the problem it was bought to solve.

A. 99.5% monthly — roughly 3.6 hours of downtime a month.
B. 99.9% monthly — roughly 43 minutes a month.
C. 99.0% monthly — roughly 7.2 hours a month.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** 99.9% is the reflex answer and it is the wrong one here:
it implies on-call response, redundancy and operational maturity that one
engineer on residual time cannot provide, and committing to it would be a
promise the team assessment says cannot be kept. 99.5% is defensible, and the
human-handoff path bounds the damage of the remainder.

[Answer]: A. 99.5% monthly — roughly 3.6 hours of downtime a month.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q4. Which languages must the MVP actually support?

Indic code-switching is the stated differentiator but is ranked Should rather
than Must in the backlog, because no evidence establishes the quality is
achievable.

A. English only at MVP; Indic languages follow once the bake-off (D-02) establishes achievable quality.
B. English plus Hindi and Hinglish, accepting the risk before the bake-off.
C. English plus Hindi, Hinglish and the regional languages named in the vendor research.
D. Not yet decided — depends on the pilot clinic's patient population.
X. Other (please specify)

**Recommendation: D, with A as the fallback.** Which languages matter is a
property of the pilot clinic's patients, and no clinic is named. Building Indic
support before knowing whether the pilot needs it risks building the
differentiator for nobody; building English-only when the pilot is Indian would
be worse. This is another item D-01 resolves.

[Answer]: D. Not yet decided — depends on the pilot clinic's patient population. English-only is the recorded fallback if the answer does not arrive.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q5. How long are call recordings and transcripts retained?

India requires security logs retained at least one year and personal data erased
once its purpose is fulfilled. The affirmed practices resolved the audit log to
be PHI-free, which leaves recordings and transcripts as a separate question.

A. Transcripts retained for the clinic's stated record-keeping period; audio deleted after a short window (days) once the transcript and outcome are captured.
B. Both retained for a long period, on the basis that they are clinical records.
C. Both deleted as soon as the call outcome is recorded, keeping only structured outcome data.
D. Not yet decided — needs the compliance counsel engagement.
X. Other (please specify)

**Recommendation: A.** Audio is the highest-risk artifact — voice is itself a
listed identifier — and its value drops sharply once a transcript exists. A short
audio window with longer transcript retention minimises exposure while keeping
what the clinic actually refers back to. It should still be confirmed with
counsel, which is already planned.

[Answer]: A. Transcripts retained for the clinic's stated record-keeping period; audio deleted after a short window (days) once the transcript and outcome are captured.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q6. What call volume should the system be built to handle?

No volume forecast exists anywhere in the workflow.

A. Design for a single clinic's realistic load — tens of concurrent calls at peak — and treat scaling beyond that as a later problem.
B. Design for multi-clinic scale from the start, since multi-tenancy is already in scope.
C. Not yet decided.
X. Other (please specify)

**Recommendation: A.** Multi-tenancy is about isolation, not throughput. The MVP
serves one pilot clinic; building for a scale nobody has forecast is the
definition of premature. Requirements should state the architecture must not
*preclude* horizontal scaling, without committing to a throughput figure that
would be invented.

[Answer]: A. Design for a single clinic's realistic load — tens of concurrent calls at peak — and treat scaling beyond that as a later problem.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q7. What must happen when the agent cannot reach a dependency mid-call?

The call flow covers the agent failing to understand. It does not cover the
speech vendor, model or telephony leg failing while a patient is on the line.

A. Fail to the escalation branch immediately — transfer if staffed, message and callback if not, with a spoken apology rather than silence.
B. Retry once transparently, then escalate.
C. Not yet decided.
X. Other (please specify)

**Recommendation: A.** The failure mode that matters on a live call is dead air.
The escalation branch already exists and already handles the unstaffed case;
routing dependency failures into it means one path to build and test rather than
two. A retry that adds seconds of silence is worse than a fast handoff.

[Answer]: A. Fail to the escalation branch immediately — transfer if staffed, message and callback if not, with a spoken apology rather than silence.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Consolidated Summary Confirmation

Summary of all answers:

- **Success metrics:** define the measurement now — what is counted, over what window, from what point — and leave target numbers until a pilot baseline exists. [Q1]
- **Latency:** end-to-end response under 1.5 seconds at p95, from caller stopping speech to agent audio starting. [Q2]
- **Availability:** 99.5% monthly. [Q3]
- **Languages:** determined by the pilot clinic's patient population; English-only recorded as the fallback if that answer does not arrive. [Q4]
- **Retention:** transcripts for the clinic's record-keeping period; audio deleted after a short window once the transcript and outcome are captured. [Q5]
- **Volume:** one clinic's realistic load; the architecture must not preclude horizontal scaling, but no throughput figure is committed. [Q6]
- **Mid-call dependency failure:** route to the existing escalation branch immediately, with a spoken apology rather than silence. [Q7]

**Provenance.** All seven were answered by accepting an orchestrator
recommendation presented with its reasoning, rather than as unprompted answers.
This follows the practice learned at practices discovery, where four consecutive
deferrals showed that dense technical questions asked cold produce deferrals
rather than decisions.

**What [Q1] means for this stage's output.** Requirements will carry measurement
definitions with an explicit `TARGET: TBD (pilot baseline)` marker on the three
success metrics, rather than either inventing numbers or omitting the metrics.
Acceptance criteria for everything *else* are fully testable; only the three
success-metric thresholds wait.

**A consequence of [Q4] worth stating.** With the language set undetermined, the
requirements must specify that language selection is configuration rather than
built-in, so the answer can arrive later without rework. That is a real
architectural requirement produced by a deferred product decision.

**A tension between [Q3] and the scope.** 99.5% monthly permits about 3.6 hours
of downtime, and the product's entire premise is that unanswered calls are the
problem. The requirement therefore pairs the availability target with a stated
degraded-mode obligation: when the agent cannot serve a call, the telephony layer
must still route to the clinic's existing path rather than fail silently. An
outage should degrade to the status quo, not to a dead line.

Does this all look correct before I generate the requirements?

- Looks correct
- Request changes

[Answer]: Looks correct
