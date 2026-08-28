# Initiative Brief — Healthcare Receptionist Voice Agent

**Phase gate:** Ideation → Inception · **Decision: GO as approved** [Q1]

## Intent and problem

Clinic front-desk staff are overloaded with repetitive scheduling calls, and that
overload causes burnout and turnover. Staff time is the leading value story;
captured calls and appointments are a welcome side effect rather than the headline
claim. The customer segment follows AI Thinkers' existing healthcare
relationships rather than a segment chosen in the abstract.
(`../intent-capture/intent-statement.md`)

**The trigger is market opportunity** — voice AI quality has crossed the threshold
where patients accept it — not a specific client request. That claim is supported
with one important qualification, below.

## Market validation

`../market-research/market-trends.md` and
`../market-research/competitive-analysis.md` established four things and declined
to establish a fifth.

**Established:**

- **Growth direction is consistent** across analyst sources at roughly 38% CAGR,
  with healthcare the fastest-growing vertical inside Indian conversational AI at
  37.79%.
- **Patient acceptance is real but conditional.** ~72% of patients report comfort
  with voice assistants for routine scheduling — but an independent survey found
  *the difference between the most and least accepted scenario is the presence of
  a human, not the technology*. This is why human handoff is designed as an
  acceptance requirement, not a fallback.
- **The differentiator is narrower than assumed.** General multilingual support is
  table stakes — a horizontal competitor already ships 10+ languages with
  automatic detection at SMB pricing. What is genuinely scarce is Indic-language
  and mid-sentence code-switching at telephony audio quality, which no vendor
  benchmarks and none of the three named competitors claims.
- **US practice consolidation cuts against the SMB framing.** Independent
  practices are down to 120,900, with 63.9% of practices corporate-owned.

**Deliberately not established: market size.** 2026 analyst estimates for the same
category span roughly 4× ($651M to $2.68B), no count of Indian private clinics was
found, and no India price point exists. No obtainable-market figure is offered
because none could be derived rather than invented.

**On whether this justifies the investment, [Q3] recorded no preference.** This
brief therefore states what the research supports and leaves the judgement to
whoever funds it: the problem is real, the growth direction is real, the India
position is genuinely underserved, and the differentiating capability is
unvalidated.

## Feasibility and risk

**Verdict: technically feasible. The binding constraint is not technology — it is
that the initiative is not yet specified enough to build against.**
(`../feasibility/feasibility-assessment.md`)

Every required capability has a demonstrated implementation path, three vendors
already ship comparable products, no skill gap blocks the work, and the Python
stack matches the orchestration candidates.

**The four highest risks** (`../feasibility/raid-log.md`, as updated at this gate):

| ID | Risk | Severity | Treatment |
|---|---|---|---|
| R-01 | Indic code-switching quality — the differentiator — is entirely unvalidated; no vendor publishes an Indian-accent or 8kHz benchmark | High | Mitigate via a bake-off on real recordings (D-02) |
| R-03 | Both regulatory regimes bind at once, roughly doubling the compliance surface | High | **Accept** — a knowing consequence of choosing both regions |
| R-04 | Compliance architecture will be frozen before counsel reviews it | High | Accept, knowingly |
| **R-10** | **The voice channel excludes deaf and hard-of-hearing patients, and those the recogniser handles poorly. No fallback decided.** | High | **Mitigate — added at this gate** [Q2] |

R-07 (capacity stalls the work) is **superseded**: it was scored before team
formation established the real position, which is recorded as an issue rather
than a risk.

## Scope boundary

**In:** all four capabilities (24/7 answering, booking and rescheduling, patient
intake, outbound reminders); both US and India tenants; full multi-tenancy;
per-region provider abstraction; the compliance core; human handoff; call
analytics; internal configuration plus a read-only clinic view.

**Out:** the aerospace and finance packs; all payment handling (PCI DSS avoided
outright); all clinical decision-making, triage or advice; EHR integration
(fast-follow); clinic self-service.

**What the boundary costs**, per `../scope-definition/scope-document.md`: the MVP
is **wide on infrastructure and narrow on the differentiator**. Deferring EHR
integration removes the capability that separates a healthcare product from a
generic receptionist, while taking the maximum on everything else. A reduction
order is recorded — outbound reminders first, then the India tenant, then full
multi-tenancy, then intake — so a later cut is a decision against a prepared list.

## Concept and design

`../rough-mockups/user-flow.md` and `../rough-mockups/wireframes.md`, confirmed at
this gate as matching the intent [Q4].

The substantive output is a **complete failure policy**: one recovery attempt,
then transfer to a human during staffed hours, then take a message and promise a
callback when unstaffed. Two consequences carry into Inception — the callback
promise is an obligation on the clinic that no clinic has agreed to, and captured
messages become a queue somebody must watch.

The greeting is simultaneously the most regulated and most experience-critical
moment in the product: AI disclosure and recording disclosure are Firm constraints
and must be the first thing every patient hears.

## Delivery capacity

**One engineer, on time left over after client delivery, with no external help,
against nine Must-ranked proto-Units across two regulatory regions.**
(`../team-formation/team-assessment.md`)

Recorded as an **issue rather than a risk** — it is the current state, not
something that might occur. All four required skill areas are present, so nothing
waits on learning; the finding is concentration rather than absence, with a bus
factor of one and written artifacts as the only knowledge redundancy.

There is no deadline and no budget ceiling. **No effort, duration or cost estimate
appears anywhere in this brief**, because capacity is contended and unquantified
and any figure would be manufactured.

## Go/no-go recommendation

**Decision recorded: GO as approved, full scope** [Q1].

This brief does not recommend against that decision. It records the terms it is
taken on:

- The scope is the largest available on every axis except EHR integration, against
  one engineer on residual time, with **no forcing function**.
- The differentiating capability is **unvalidated**, and validating it depends on
  real call recordings that depend on a pilot clinic that does not exist.
- Half the MVP (the India tenant's outbound calling) is **blocked by an external
  dependency with no owner** — DLT registration, where no provider acts on a
  customer's behalf and penalties reach ₹1M per instance.
- The walking skeleton is the only mitigation currently in the plan for the
  capacity gap, and it is a good one: it produces something demonstrable early,
  which matters more than usual when there is no date to create momentum.

## The top open item

**D-01 — a conversation with a prospective pilot clinic — is the critical path,
and [Q5] left the first action after this gate undecided.**

One conversation resolves four things: which EHR systems to integrate with, the
launch jurisdiction, the unnamed stakeholder, and whether a clinic will accept the
agent's own calendar as the appointment system of record. It also gates D-02, the
accuracy bake-off, which needs real call recordings.

It requires **no engineering capacity at all**, which is exactly why it is worth
naming here: it is the one item a capacity constraint does not touch, and nothing
in the workflow will produce it on its own.

## Handoff to Inception

| Item | State entering Inception |
|---|---|
| Intent and problem | Approved, stable |
| Scope boundary | Approved, with a recorded reduction order |
| Backlog | 15 proto-Units, MoSCoW-ranked |
| Constraints | 22 recorded across technical, organisational, regulatory |
| Risks | 10, four at High severity |
| Design | Call flows and two screen surfaces, confirmed |
| Capacity | One engineer, residual time — recorded as an issue |
| Open critical path | D-01 (unsequenced), D-04 (unowned) |

Inception opens with practices discovery and requirements analysis, neither of
which depends on D-01. Two questions carried forward specifically want answers
there: how to compensate for the absence of code review on PHI-handling
components, and how to make the success metrics measurable enough to serve as
acceptance criteria.

## Assumptions & Open Questions

- No clinic has been consulted. Every requirement in this brief is inferred from
  the intent statement and the project brief rather than observed. [assumption]
- The market case is recorded as [Q3] left it — no preference expressed — rather
  than resolved on the funder's behalf. [assumption]
- Whether the agent's own calendar is acceptable as the appointment system of
  record is unknown and determines who the MVP can serve. [assumption]
- D-04 (DLT registration) has no owner and gates half the MVP. [assumption]
- The non-voice fallback for callers the voice channel cannot serve is undecided
  (R-10). [assumption]
- No effort, duration or cost figure is offered anywhere. [assumption]
