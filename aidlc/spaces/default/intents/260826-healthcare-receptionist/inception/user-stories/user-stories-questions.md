# User Stories — Story Plan and Questions

**Mode:** guided

## Assessment outcome

EXECUTE. See `user-stories-assessment.md` — user-facing product, four distinct
actors, complex escalation logic. Requirements state what the system shall do;
stories capture why a person is calling and what a bad experience looks like from
their side.

## Story plan

**Format:** `As a [persona], I want [action], so that [benefit]`, with
Given/When/Then acceptance criteria. INVEST criteria applied — every story
independently deliverable and testable.

**Prioritisation:** MoSCoW, aligned to the proto-Unit ranking already in
`../../ideation/scope-definition/intent-backlog.md`. The MVP boundary is formally
decided at Delivery Planning; these priorities inform it rather than replace it.

**Traceability:** every story traces to a functional requirement in
`../requirements-analysis/requirements.md`. Stories that trace to nothing are
either missing a requirement or are not in scope.

Each question below carries a **recommended answer**, following the practice
learned at practices discovery.

---

## Q1. Which personas should the stories be written for?

The intent statement names AI Thinkers internal, a pilot clinic, its
practitioners and patients. Not all of those interact with the system.

A. Four — Patient (caller), Front-desk staff, Practice owner, and AI Thinkers operator.
B. Three — Patient, Clinic staff (one persona covering both staff and owner), and Operator.
C. Two — Patient and Clinic, treating the operator's work as internal tooling rather than a user journey.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** Front-desk staff and the practice owner want genuinely
different things — one wants to know what happened while they were busy, the
other wants to know whether it is working. `../../ideation/rough-mockups/wireframes.md`
already records that the clinic view serves both readings and is provisional
because of it. Keeping them separate is what makes that decision visible rather
than buried. Practitioners are named in the intent statement but do not interact
with the system, so they get no persona.

[Answer]: A. Four — Patient (caller), Front-desk staff, Practice owner, and AI Thinkers operator.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q2. How should the stories be broken down?

A. By workflow — the inbound call, the outbound reminder, configuration, review. Follows how the product is actually used.
B. By persona — everything the patient does, then everything staff do, then the operator.
C. By feature — booking, intake, reminders, escalation, dashboards.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** The product's value lives in complete journeys rather than
in features: a booking that succeeds but cannot escalate is not a partial
success. Workflow breakdown also matches the walking-skeleton sequencing already
chosen, which is a thin slice of a whole journey rather than one complete
feature.

[Answer]: A. By workflow — the inbound call, the outbound reminder, configuration, review. Follows how the product is actually used.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q3. How granular should the stories be?

A. One story per meaningful user outcome — roughly 15–25 stories across the MVP.
B. Fine-grained — one per interaction step, 40+ stories.
C. Coarse — one per capability, under 10 stories.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** INVEST wants stories small enough to complete in a
sitting, which matters more than usual here: `../../ideation/team-formation/team-assessment.md`
records residual, interrupted availability, and a story that completes in one
session survives an interruption where a multi-session story does not.

[Answer]: A. One story per meaningful user outcome — roughly 15–25 stories across the MVP.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q4. Should the patient be written as a persona at all, given they never chose to use the product?

A patient calls a clinic. They did not select this software, cannot opt out of
it, and in many cases would rather have reached a person.

A. Yes, and state that constraint explicitly in the persona — it is the single most important fact about them and it should shape every story they appear in.
B. Yes, as a conventional persona without that framing.
C. No — model the clinic as the only customer, since the clinic is who buys and configures.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** Every other persona here chose to be here. The patient did
not, which is exactly why `../../ideation/market-research/market-trends.md` found
acceptance contingent on a route to a human. A persona that omits this produces
stories written as though the patient wanted the agent.

[Answer]: A. Yes, and state that constraint explicitly in the persona — it is the single most important fact about them and it should shape every story they appear in.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---

## Q5. How should stories handle the parts that are still undecided?

Several requirements carry open items: the language set (FR7.3), the non-voice
accessibility fallback (NFR6.2), and the three success metrics with TBD targets.

A. Write the stories, and mark each affected acceptance criterion as blocked on the specific open item.
B. Omit stories for undecided areas until the decisions land.
C. Write the stories with assumed answers, to be corrected later.
D. Not yet decided.
X. Other (please specify)

**Recommendation: A.** Omitting them hides work that will certainly be needed;
assuming answers manufactures decisions nobody made. Marking the specific
criterion as blocked keeps the story visible and its dependency explicit — and
makes it obvious at Delivery Planning which stories cannot be scheduled yet.

[Answer]: A. Write the stories, and mark each affected acceptance criterion as blocked on the specific open item.

_Recorded note: the orchestrator's recommendation, accepted by the human after review._

---
