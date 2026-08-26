# Intent Backlog — Proto-Units

## Purpose and method

The prioritised backlog of proto-Units for the scope defined in
`scope-document.md`, bounded by the approved intent statement
(`../intent-capture/intent-statement.md`), the feasibility verdict
(`../feasibility/feasibility-assessment.md`) and the constraints in
`../feasibility/constraint-register.md`.

These are **proto-Units**, not Units. Units of work with dependency edges are
produced later, at Units Generation. This backlog establishes what exists and in
what order it matters.

**Prioritisation uses MoSCoW**, not WSJF or RICE. WSJF needs a cost of delay, and
RICE needs reach and effort figures — none of which exist here: there is no
deadline, no budget, no volume forecast and no capture target. Scoring against
invented inputs would produce arithmetic that looks rigorous and means nothing.
MoSCoW needs only relative necessity, which the scope answers do establish.

**Ordering follows the walking-skeleton-first heuristic** [Q6], so the sequence
below is not simply the MoSCoW ranking: P1 exists to prove the chain end to end
before depth is added anywhere.

## Backlog

| # | Proto-Unit | MoSCoW | Rationale | Key constraints |
|---|---|---|---|---|
| **P1** | **Walking skeleton** — one inbound call answered end to end across the real vendor chain: telephony in, speech to text, model, speech out, hang up. No features. | Must | The sequencing heuristic [Q6] and the `feature` scope's `skeleton: on` both put this first. Proves the riskiest structural assumption — that the chain holds together — before anything is built on it. Also the first thing demonstrable, which matters when there is no deadline. | C-T2 (bidirectional streaming), C-T3 (cascaded pipeline) |
| **P2** | **Provider abstraction** — telephony, speech-to-text and text-to-speech behind stable internal interfaces, selectable per region. | Must | C-T1 makes this a hard constraint, not a preference: no vendor serves both markets, so the abstraction is the only configuration the vendor landscape permits. Must exist before either region is wired up. | C-T1, C-T5 |
| **P3** | **Compliance core** — region isolation, PII/PHI redaction before logging or analytics, jurisdiction-aware consent and AI disclosure, immutable audit log. | Must | `BRIEF.md` places this in Phase 1 as "brutally expensive to retrofit", and `../market-research/market-trends.md` finds compliance becoming a barrier to entry. Both regions in scope [Q3] means it carries both regimes. | C-R1–C-R4, C-R7–C-R9 |
| **P4** | **Multi-tenancy** — tenant model, data isolation, per-tenant configuration. | Must | [Q4] chose full multi-tenancy from day one. With PHI in scope the isolation boundary is a compliance surface, not only an engineering one. | C-T4 |
| **P5** | **Human handoff** — transfer to a person with structured context carried across. | Must | `../market-research/market-trends.md` finds patient acceptance is contingent on human availability, not on the technology. That makes this an acceptance requirement as well as C-T6. | C-T6 |
| **P6** | **Inbound receptionist agent** — answer 24/7, handle simultaneous callers, understand intent, route. | Must | The baseline capability the intent statement's problem statement rests on. | C-R3, C-R4 |
| **P7** | **Appointment booking and rescheduling** — against the agent's own calendar. | Must | [Q2] and [Q1]. Directly serves the front-desk overload problem that is the initiative's primary value story. | — |
| **P8** | **Call analytics and transcripts** — call records, outcomes, transcript storage inside the redaction boundary. | Must | Without it the success metrics in the intent statement cannot be measured at all, and P9 has nothing to display. | C-R2, C-R7 |
| **P9** | **Operator surface** — internal configuration plus a read-only clinic view of calls, transcripts and bookings. | Must | [Q5]. Deliberately excluded from the reducible list in `scope-document.md`: without it the clinic cannot see value and the metrics cannot be demonstrated. | — |
| **P10** | **Patient intake** — structured data capture over voice. | Should | [Q2] puts it in the MVP, but it is the least entangled capability and `scope-document.md` names it the fourth candidate for reduction. | C-R2 |
| **P11** | **Outbound reminder calls** — reminder and recall campaigns with consent handling. | Should | In the MVP by [Q2], but ranked Should rather than Must because it is the first candidate for reduction and is **blocked in India by D-04**. Delivers the no-show-reduction success metric. | C-R5, C-R6, C-R9 |
| **P12** | **Indic language and code-switching support** — Hindi, Hinglish and regional languages with mid-sentence switching. | Should | The stated differentiator, and entirely unvalidated: R-01 in `../feasibility/raid-log.md`. Cannot be committed to as Must until the bake-off (D-02) establishes achievable quality. | C-T5 |
| **P13** | **EHR / practice-management integration** | Won't (this initiative) | Deferred by [Q1]. Recorded here rather than omitted, because `../market-research/competitive-analysis.md` identifies it as the differentiator and it is the intended fast-follow. | Blocked by D-01 |
| **P14** | **Clinic self-service configuration** | Won't (this initiative) | The SaaS surface; `BRIEF.md` sequences it after the managed service proves out. | — |
| **P15** | **Aerospace AOG and finance packs** | Won't (this initiative) | [Q7]. The platform core is built vertical-agnostic so these stay cheap to add later. | — |

## Non-development work on the critical path

These are not proto-Units — no engineering builds them — but the MVP does not
ship without them, and a backlog that omitted them would misrepresent the work.

| Item | Blocks | Why it belongs here |
|---|---|---|
| **D-01 — pilot clinic conversation** | P13 scoping; the calendar-source-of-truth question in `scope-document.md`; the jurisdiction decision; D-02 | The critical path item from `../feasibility/feasibility-assessment.md`. Needs no engineering capacity, which matters when capacity is contended. |
| **D-04 — DLT registration and 1600-series numbering** | P11 in India | Promoted to critical path by [Q2] plus [Q3]. A hard precondition, not a task; no provider does it for you; currently unowned. |
| **D-02 — Indic accuracy bake-off on real 8kHz recordings** | Committing P12 above Should | The only way to convert the differentiator from claim to evidence. Likely depends on D-01 for recordings. |
| **D-03 — orchestration spike** | Confirms or reopens the LiveKit recommendation | Scheduled during Inception in parallel [feasibility Q7]. |

## Dependency shape

Not a full dependency graph — that is Units Generation's output — but the
ordering constraints already visible:

- **P1 precedes everything.** The skeleton proves the chain; building depth on an
  unproven chain is the failure mode the heuristic exists to prevent.
- **P2 precedes region-specific work.** Wiring either region before the
  abstraction exists means wiring it twice.
- **P3 precedes anything that touches real call data.** Redaction and audit added
  after data starts flowing is the retrofit `BRIEF.md` warns about.
- **P4 precedes a second tenant**, and with PHI the isolation boundary must exist
  before real patient data does.
- **P8 precedes P9.** The clinic view has nothing to show without call records.
- **P11 in India is blocked by D-04**, which is external and unowned.
- **P12 cannot be committed above Should until D-02** produces evidence.

## Assumptions & Open Questions

- MoSCoW rankings are relative necessity judgements from the approved artifacts
  and the scope answers, not the output of a prioritisation session with the
  team. [assumption]
- No proto-Unit carries an effort estimate. Capacity is contended and
  unquantified and there is no timeline, so sizing would be manufactured.
  [assumption]
- P12 is ranked Should rather than Must despite being the stated differentiator,
  because no evidence yet establishes that the quality is achievable.
  [assumption]
- P11's India half is blocked by an external dependency with no owner, so its
  MVP membership is conditional in practice even though [Q2] includes it.
  [assumption]
- The split between Must and Should above assumes the reduction order in
  `scope-document.md` is the one that would actually be taken if scope had to
  move. That has not been tested against a real constraint. [assumption]
