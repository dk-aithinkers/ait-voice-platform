# Requirements — Healthcare Receptionist Voice Agent

## Scope and method

Requirements for the MVP defined in `../../ideation/scope-definition/scope-document.md`,
serving the intent in `../../ideation/intent-capture/intent-statement.md` and
built under the practices affirmed in `../practices-discovery/team-practices.md`.

**Every requirement traces to an approved ideation artifact or to an interview
answer.** Nothing here is introduced without a source. Acceptance criteria use
Given/When/Then and carry a pass/fail threshold, except where a threshold
genuinely awaits a pilot baseline — those are marked `TARGET: TBD (pilot
baseline)` rather than invented or omitted.

**Depth: Standard**, per the active `feature` scope. The request is well-defined
after six ideation stages; the unknowns are external (no pilot clinic) rather
than definitional.

## Functional requirements

### FR1 — Inbound call answering

| | |
|---|---|
| **FR1.1** | The system shall answer inbound calls to a configured clinic number 24 hours a day. |
| **FR1.2** | The system shall handle multiple concurrent inbound calls to the same clinic number. |
| **FR1.3** | The system shall speak an AI disclosure and a recording disclosure at the start of every call, before any other content. |
| **FR1.4** | The system shall prevent an operator from removing or disabling the disclosures in FR1.3. |

*Source: scope-document (all four capabilities in scope); constraint-register C-R3, C-R4; wireframes Screen 1a.*

```
AC1.3.1
Given a caller dials a configured clinic number
When the agent answers
Then the first spoken content identifies the clinic, states that the caller is
     speaking with an AI assistant, and states that the call is recorded
And no other content precedes it

AC1.4.1
Given an operator editing a clinic configuration
When they attempt to remove the disclosure text
Then the system refuses the edit and explains why
```

### FR2 — Appointment booking and rescheduling

| | |
|---|---|
| **FR2.1** | The system shall book an appointment into the agent-owned calendar during a call. |
| **FR2.2** | The system shall reschedule an existing appointment identified by the caller. |
| **FR2.3** | The system shall cancel an existing appointment on caller request. |
| **FR2.4** | The system shall read back the resulting appointment date and time aloud before ending the call. |
| **FR2.5** | The system shall offer alternative times when a requested slot is unavailable. |

*Source: intent-statement; scope-document [Q1] — own calendar, no EHR integration in MVP; user-flow Flow 1.*

```
AC2.1.1
Given a caller requests an available appointment slot
When the caller confirms the slot
Then the appointment is persisted against that clinic and that caller
And the agent states the booked date and time aloud

AC2.5.1
Given a caller requests a slot that is already taken
When the agent processes the request
Then the agent offers at least one alternative time
And does not end the call without either booking or escalating
```

### FR3 — Patient intake

| | |
|---|---|
| **FR3.1** | The system shall capture caller-provided intake details over voice into structured fields. |
| **FR3.2** | The system shall confirm captured identifiers back to the caller before storing them. |

*Source: intent-statement; scope-document [Q2].*

```
AC3.2.1
Given the agent has captured a date of birth or similar identifier
When capture completes
Then the agent repeats the value back and obtains confirmation before storing it
```

### FR4 — Outbound reminder calls

| | |
|---|---|
| **FR4.1** | The system shall place outbound reminder calls for upcoming appointments in the agent-owned calendar. |
| **FR4.2** | The system shall allow the caller to confirm, reschedule or cancel during a reminder call. |
| **FR4.3** | The system shall never include marketing or promotional content in a reminder call. |
| **FR4.4** | The system shall not place outbound calls in a region until that region's regulatory registration is recorded as complete. |

*Source: scope-document [Q2]; constraint-register C-R5, C-R6, C-R9; raid-log D-04.*

```
AC4.3.1
Given a reminder call is in progress
When the agent composes any utterance
Then that utterance contains no offer, promotion or service upsell

AC4.4.1
Given a clinic configured in the India region
When outbound calling is attempted and DLT registration is not recorded complete
Then the system refuses to place the call and raises an operator alert
```

**FR4.3 is a hard product constraint, not a style preference.** The TCPA
healthcare exemption that makes these calls lawful without written consent
evaporates the moment promotional content appears.

### FR5 — Escalation and failure handling

| | |
|---|---|
| **FR5.1** | The system shall make one recovery attempt when it cannot understand the caller, then escalate. |
| **FR5.2** | The system shall escalate immediately, without a recovery attempt, when the caller asks for a person or raises a clinical or urgent matter. |
| **FR5.3** | The system shall transfer to a human with structured call context when a human is available. |
| **FR5.4** | The system shall take a message and state that the clinic will call back when no human is available. |
| **FR5.5** | The system shall route a mid-call dependency failure into the escalation path, with a spoken apology, rather than allowing silence. |
| **FR5.6** | The system shall never end a call without either completing the caller's task, transferring, or taking a message. |

*Source: user-flow Flows 1 and 2; rough-mockups [Q7], [Q8]; requirements [Q7]; constraint-register C-T6.*

```
AC5.2.1
Given a caller states a clinical symptom or asks for medical advice
When the agent classifies the utterance
Then the agent escalates without attempting to answer

AC5.5.1
Given a speech, model or telephony dependency fails mid-call
When the failure is detected
Then the agent speaks an apology and enters the escalation path within 3 seconds
And the caller never experiences more than 3 seconds of unexplained silence
```

### FR6 — Operator and clinic surfaces

| | |
|---|---|
| **FR6.1** | The system shall provide an internal operator console listing clinics with region, status, recent call volume and outstanding messages. |
| **FR6.2** | The system shall provide per-clinic configuration covering identity, greeting, languages, staffed hours, transfer destination and out-of-hours behaviour. |
| **FR6.3** | The system shall provide a test-call action that verifies a configuration end to end. |
| **FR6.4** | The system shall provide a read-only clinic view of recent calls, outcomes, bookings and messages awaiting callback. |
| **FR6.5** | The system shall provide a per-call detail view with transcript and outcome. |
| **FR6.6** | The system shall surface messages awaiting callback on both the operator and clinic surfaces. |

*Source: scope-document [Q5]; wireframes Screens 1, 1a, 2, 2a.*

```
AC6.3.1
Given an operator has saved a clinic configuration
When they run a test call
Then the result reports whether the configured number answered with the
     configured greeting, and a save alone is not treated as verification
```

### FR7 — Multi-tenancy and configuration

| | |
|---|---|
| **FR7.1** | The system shall isolate every clinic's data such that no request can read another clinic's calls, transcripts, bookings or messages. |
| **FR7.2** | The system shall determine the speech, telephony and model providers for a call from the clinic's configured region. |
| **FR7.3** | The system shall treat the language set for a clinic as configuration rather than a built-in property. |

*Source: scope-document [Q3], [Q4]; constraint-register C-T1, C-T4; requirements [Q4].*

**FR7.3 exists because a product decision was deferred.** The language set depends
on the pilot clinic's patients, which is unknown; making it configuration means
the answer can arrive without rework.

```
AC7.1.1
Given two clinics exist with call records
When any read path is exercised with clinic A's context
Then no clinic B record is returned, under any query, filter or export
```

## Out of scope

Explicitly excluded from this initiative. These are not omissions, deferrals to
be inferred, or things to build if time allows — they are declared exclusions,
restated here because this document is what Construction builds from.

| Excluded | Requirement consequence |
|---|---|
| **EHR / practice-management integration** | The system shall not read from or write to any external clinical or practice-management system. FR2 operates against the agent-owned calendar only. Deferred to a fast-follow, not to later in this MVP. |
| **Payment handling of any kind** | The system shall not capture, transmit, store or process card or bank details, and shall not take payment over a call. This keeps PCI DSS entirely out of scope; reintroducing payments reintroduces the whole regime. |
| **Clinical decision-making, triage or advice** | The system shall not answer clinical questions, assess symptoms, or offer medical guidance. FR5.2 makes such an utterance an immediate escalation trigger. This exclusion also protects the TCPA healthcare-exemption boundary that FR4.3 depends on. |
| **Aerospace AOG and finance agent packs** | No vertical other than healthcare is in scope. The platform core is built vertical-agnostic so they remain cheap to add, but nothing in this MVP implements them. |
| **Clinic self-service configuration** | Clinics view but do not configure. FR6.2 is an operator-only surface; FR6.4 and FR6.5 are read-only. |

*Source: `../../ideation/scope-definition/scope-document.md` "Out of scope"
and [Q1], [Q7] of scope definition.*

**Two of these are load-bearing rather than merely descriptive.** Excluding
payments is what keeps PCI DSS out of the compliance surface entirely. Excluding
clinical advice is what keeps outbound reminders inside the TCPA healthcare
exemption, which FR4.3 already depends on. Neither can be relaxed without
reopening a regulatory analysis.

## Non-functional requirements

### NFR1 — Conversational latency

**NFR1.1** — End-to-end response latency, measured from the caller ceasing speech
to the first audio of the agent's reply, shall be **under 1.5 seconds at p95**.

*Source: requirements [Q2]; docs/vendors.md measured vendor latencies.*

```
AC-NFR1.1
Given a representative sample of at least 100 conversational turns
When latency is measured from end-of-caller-speech to first agent audio
Then the 95th percentile is below 1500ms
```

### NFR2 — Availability and degraded mode

**NFR2.1** — Availability shall be **99.5% measured monthly** for inbound call
answering.

**NFR2.2** — When the agent cannot serve a call for any reason, the telephony
layer shall route the call to the clinic's existing answering path rather than
failing silently.

*Source: requirements [Q3]; team-assessment (capacity constraints make a higher
target a promise that cannot be kept).*

**NFR2.2 is the reason NFR2.1 is acceptable.** 99.5% permits roughly 3.6 hours of
downtime a month, and the product exists because unanswered calls are the problem.
An outage must degrade to the status quo, not to a dead line.

```
AC-NFR2.2
Given the agent service is unavailable
When a call arrives at the clinic number
Then the call is routed to the clinic's configured fallback path
And the caller does not receive silence or a failure tone
```

### NFR3 — Data protection and retention

**NFR3.1** — Call audio, transcripts and caller identifiers shall be treated as
protected health information throughout.

**NFR3.2** — Personal data shall be redacted before it reaches any log, metric or
analytics surface.

**NFR3.3** — Call audio shall be deleted within a short configured window after
the transcript and outcome are captured.

**NFR3.4** — Transcripts shall be retained for the clinic's configured
record-keeping period and no longer.

**NFR3.5** — The audit log shall contain no personal data; entries shall
reference by opaque identifier only.

**NFR3.6** — Security logs shall be retained for at least one year, in a log class
separate from any class subject to erasure.

*Source: requirements [Q5]; team-practices and discovered-rules (audit log
resolution); constraint-register C-R1, C-R2, C-R7, C-R8.*

**NFR3.5 and NFR3.6 together resolve a contradiction** found independently by two
reviewers at practices discovery: retention and erasure obligations can only both
hold if they apply to disjoint data.

```
AC-NFR3.2
Given a call containing a caller name, number and date of birth
When the call completes and logs are inspected
Then no log, metric or trace contains any of those values

AC-NFR3.5
Given any audit log entry
When it is inspected
Then it contains identifiers and event types only, and no transcript,
     caller name, number or clinical content
```

### NFR4 — Regional isolation and vendor boundary

**NFR4.1** — Data for a clinic shall remain within that clinic's configured
region.

**NFR4.2** — Every speech, telephony and text-to-speech provider shall be
replaceable per region without changes outside the provider boundary.

**NFR4.3** — No vendor may process call audio, transcripts or caller identity in
the US region without a recorded Business Associate Agreement.

*Source: constraint-register C-T1, C-R1; build-vs-buy; team-practices.*

### NFR5 — Capacity

**NFR5.1** — The system shall handle a single clinic's peak concurrent call load.

**NFR5.2** — The architecture shall not preclude horizontal scaling.

*Source: requirements [Q6].*

**No throughput figure is stated.** No volume forecast exists anywhere in this
workflow, and a number here would be invented rather than derived.

### NFR6 — Accessibility

**NFR6.1** — Operator and clinic surfaces shall meet WCAG 2.1 AA.

**NFR6.2** — A non-voice path shall exist for callers the voice channel cannot
serve.

*Source: rough-mockups [Q5] (AA applied as a labelled default); raid-log R-10.*

**NFR6.2 has no chosen mechanism.** R-10 records that the fallback is undecided;
the requirement states the obligation without prescribing SMS, web form or a
published direct line.

## Success metric definitions

Per [Q1], what is measured is fixed now; the thresholds await a pilot baseline.

| Metric | Definition | Window | Target |
|---|---|---|---|
| Call answer rate | Calls where agent audio is established, divided by inbound calls offered | Rolling 7 days | `TARGET: TBD (pilot baseline)` |
| Appointments booked or recovered | Appointments created or rescheduled by the agent | Rolling 7 days | `TARGET: TBD (pilot baseline)` |
| No-show reduction | No-show rate for reminded appointments against the pre-go-live rate | Rolling 30 days, baselined on the 2 weeks before go-live | `TARGET: TBD (pilot baseline)` |
| Front-desk hours saved | Agent-handled call minutes attributable to tasks previously handled by staff | Weekly, baselined on the 2 weeks before go-live | `TARGET: TBD (pilot baseline)` |

*Source: intent-statement; requirements [Q1]; raid-log I-02.*

**Baselining requires two weeks of observation before go-live at the pilot
clinic.** That is a dependency on D-01 and should be scheduled with it, not
discovered afterwards.

## Constraints carried into design

Not restated in full — see `../../ideation/feasibility/constraint-register.md`
for all 22. The ones that bind requirements most directly: C-T1 (per-region
provider replaceability), C-T2 (bidirectional media streaming), C-T3 (cascaded
pipeline), C-T4 (multi-tenancy in-house), C-T6 (structured handoff), C-R1 to
C-R9 (regulatory), and C-O1 (contended capacity).

## Assumptions & Open Questions

- **The three success-metric targets are undefined** pending a pilot baseline,
  and baselining needs two weeks of pre-go-live observation at a real clinic.
  [assumption]
- **The MVP language set is undetermined** [Q4]; FR7.3 makes it configuration so
  the answer can arrive later. [assumption]
- **The non-voice accessibility fallback has no chosen mechanism** (NFR6.2,
  R-10). [assumption]
- **Retention periods are stated as obligations, not durations** — "a short
  window", "the clinic's record-keeping period" — because the actual figures need
  the compliance counsel engagement and a clinic's own policy. [assumption]
- **No throughput figure is committed** (NFR5), because no volume forecast
  exists. [assumption]
- **Whether the agent's own calendar is acceptable to a clinic as the appointment
  system of record** is unresolved and underpins all of FR2. [assumption]
- **FR4.4's registration check assumes a machine-readable record** of regulatory
  registration status; that record does not yet exist and must be designed.
  [assumption]
## Review

**Verdict:** READY
**Reviewer:** aidlc-product-lead-agent
**Date:** 2026-08-28T14:46:39Z
**Iteration:** 2

### Findings

| # | Severity | Location | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Minor | `## Scope and method` | Carried forward, unaddressed, from iteration 1. The stage template calls for an "Intent analysis — what the user is trying to achieve (goals, not just features)" as its own analysis. The opening section is procedural (source documents, method, depth) rather than a goal statement; the reader has to infer intent from the intent-statement link rather than finding it stated here. | Add 2-3 sentences naming the problem being solved (unanswered/understaffed clinic phone lines) and the business goal (bookings recovered, front-desk time returned), distinct from the FR/NFR feature list. |
| 2 | Minor | Success metric definitions table | Carried forward, unaddressed, from iteration 1. Three of four success metrics carry `TARGET: TBD (pilot baseline)` with no numeric threshold, while the inception guardrail requires every requirement to have a clear pass/fail criterion. This is a defensible, disclosed application of the project's standing practice against manufacturing unsupported figures (Q1 explicitly chose to fix the measurement now and defer the number), and the measurement definition itself is testable once a baseline exists — but three of the four stated success metrics cannot be used as acceptance criteria until D-01 (a named pilot clinic) resolves. Worth the human's explicit awareness at the gate as a live dependency, not a paperwork gap. | No change required to the artifact; confirm D-01 is tracked as a blocking dependency for pilot go-live sign-off, not just a footnote. |

### Verification of the prior Major finding

The `## Out of scope` section is now present between FR7 and the NFR block. It
restates all five exclusions from `../../ideation/scope-definition/scope-document.md`
("Out of scope" table, `[Q7]`) — EHR/PMS integration, payment handling of any
kind, clinical decision-making/triage/advice, aerospace/finance agent packs,
and clinic self-service configuration — matching the upstream list item for
item, with no exclusion dropped and none added. Each row states a `shall
not`-shaped requirement consequence rather than only a label (e.g. "shall not
capture, transmit, store or process card or bank details, and shall not take
payment over a call"), which is a testable prohibition a developer can act on
directly rather than an interpretive note. The section also flags which two
exclusions are load-bearing for the compliance posture (payments → PCI DSS
stays out entirely; clinical advice → the TCPA healthcare exemption FR4.3
depends on), correctly cross-referencing the FR that already encodes part of
that boundary (FR5.2) without duplicating or contradicting it. This closes the
prior Major finding: a developer working from this artifact alone now has an
explicit, sourced "never build this" list, not just an inference from FR2's
source-line footnote.

### Summary

The revision fully resolves the blocking finding from the previous pass — the
`## Out of scope` section is present, matches the scope document's exclusion
list completely, and states each exclusion as a testable prohibition rather
than a restated label. The two Minor findings from iteration 1 remain
unaddressed but were never blocking on their own; nothing else in the
artifact changed. This pass finds no new issues.
