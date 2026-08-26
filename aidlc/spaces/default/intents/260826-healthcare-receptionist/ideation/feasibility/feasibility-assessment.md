# Feasibility Assessment — Healthcare Receptionist Voice Agent

## Verdict

**Technically feasible. The binding constraint is not technology — it is that the
initiative is not yet specified enough to build against.**

Every technical capability the approved intent statement
(`../intent-capture/intent-statement.md`) requires has a demonstrated
implementation path, and the market research
(`../market-research/competitive-analysis.md`) shows three vendors already
shipping comparable products. Nothing here needs invention.

What is missing is decisions, not capability. Two of the eight answers to this
stage's questions were "not known" [Q1][Q3], and both resolve through the same
action. That is assessed below as the critical path.

**Confidence: medium.** This assessment rests on `docs/vendors.md`, on the
approved market research, and on the answers recorded in
`feasibility-questions.md`. Nothing has been validated by hands-on evaluation, and
no clinic has been consulted.

## Technical viability by capability

| Capability | Viable? | Basis | Residual risk |
|---|---|---|---|
| 24/7 call answering with simultaneous handling | Yes | Demonstrated by all three vendors in `../market-research/competitive-analysis.md` | Low |
| Real-time speech pipeline at conversational latency | Yes | `docs/vendors.md` records independently measured time-to-first-audio of 188–337ms across five TTS vendors, and ~300ms streaming speech-to-text | Low for English; unverified for Indian-accented telephony audio |
| Appointment booking and rescheduling | Yes, standalone | Straightforward against a calendar the agent owns | **High if it must write to a client EHR** — the target systems are unknown [Q1] |
| Patient intake | Yes | Structured data capture over voice is well-trodden | Medium — accuracy on names, dates and identifiers over 8kHz audio is unmeasured |
| Outbound reminder calls | Yes, with regulatory work | `docs/vendors.md` records the TCPA healthcare exemption as favourable for appointment reminders, and India's 1600-series requirement as mandatory | Medium (US), High (India — registration is a precondition, not a task) |
| Indic language and code-switching | Partially | Vendors claim it; `docs/vendors.md` records that **no vendor publishes an Indian-accent or 8kHz telephony benchmark** | **High — this is the differentiator and it is unvalidated** |
| Multi-tenancy | Yes, built | `../market-research/build-vs-buy.md` establishes no managed platform provides it, so it is in-house work on a known pattern | Low technically, moderate in effort |
| Region-isolated deployment with per-region vendors | Yes | The central finding of `docs/vendors.md`; constrains vendor choice rather than feasibility | Medium — doubles vendor management surface |
| Human handoff with context | Yes | `../market-research/market-trends.md` finds acceptance is contingent on it, raising its priority | Low technically; the handoff destination is undecided |

**The one capability rated High-risk that is also a differentiator is Indic
code-switching quality.** It is claimed by vendors, unmeasured by anyone, and
central to the positioning. `docs/vendors.md` already calls a bake-off on real
call recordings the single biggest open risk in vendor selection. This assessment
concurs and does not soften it.

## Team and platform fit

**Stack fit is good.** The team works primarily in Python [Q2], and the
orchestration candidates evaluated in `../market-research/build-vs-buy.md` are
Python-first. The recommendation does not ask the team to work against its
stack — a meaningful de-risking, because a framework mismatch here would have
been expensive and is a common way voice projects stall.

**Cloud fit is good for one market and irrelevant to the other.** AWS is already
in use with an organisation and existing accounts [Q5]. For the US path this is
materially valuable: `docs/vendors.md` records that AWS offers an account-wide
BAA covering HIPAA-eligible services at no additional fee and with self-serve
execution, which removes a procurement step that gates several competitors'
customers.

For the India path it helps considerably less than it appears. `docs/vendors.md`
records that AWS has **no India telephony presence** — Connect has no ap-south-1
region and India is absent from AWS's telecom coverage entirely — and that AWS
Transcribe's streaming PII redaction **covers only English variants and Spanish,
not Hindi or any Indic language**, and cannot be combined with multi-language
identification in any case. So on AWS, for Indian calls, you can have
code-switching or automated redaction, not both.

That is a genuine architectural constraint rather than a preference, and it
should reach NFR design intact: **existing AWS accounts help with hosting,
models and storage; they do not help with the India voice path.**

## Compliance viability

Compliance is assessed as **achievable but front-loaded**, consistent with the
position `BRIEF.md` already takes.

The favourable findings: HIPAA is self-attested rather than certified, so a US
pilot does not wait on an audit body — it waits on a clean chain of executed
Business Associate Agreements. `docs/vendors.md` records that several relevant
vendors offer self-serve BAAs without a sales cycle or premium. The TCPA
healthcare exemption is genuinely favourable for appointment reminders. DPDP does
not mandate data localisation.

The unfavourable findings: a BAA does not flow down to subcontractors, so every
vendor touching call audio, transcripts or caller identity needs its own — one
gap breaks the chain. Call audio is protected health information twice over, by
content and because voice is itself a listed identifier. And the India-market
vendors with the best language capability have **no HIPAA posture as a
category**, which is precisely why per-region vendor selection is a requirement
rather than a design choice.

**The timing gap is the live compliance risk.** Counsel is to be engaged before
real patient data is handled [Q8], but `BRIEF.md` states that region pinning,
redaction, the consent engine and the audit log are Phase 1 architecture, "cheap
now, brutally expensive to retrofit." Architecture will be frozen well before
patient data flows. This is a deliberate cost decision and it stands; it is
recorded as risk R-04 in `raid-log.md` rather than resolved here.

## Critical path

**Selecting and talking to one prospective pilot clinic is the highest-value next
action available, and nothing else comes close.**

Two of this stage's answers are "not known" [Q1][Q3], and intent capture recorded
that no pilot clinic is named. All three trace to the same absent event. One
conversation would:

1. Identify the practice-management/EHR systems to integrate with — which
   `../market-research/competitive-analysis.md` names as the gap blocking the
   healthcare-depth half of the positioning
2. Settle the launch jurisdiction — which determines vendor selection, data
   residency, and which compliance regime the platform core is built against
3. Convert the pilot clinic from a stakeholder role into a named party with real
   requirements

No other open item unlocks three things at once. Every subsequent stage produces
better output with these answers than without them, and requirements analysis in
particular will be working from assumptions until they exist.

## Pace and capacity

There is no deadline and no budget ceiling [Q4]; the work is funded from ongoing
services revenue, and the team is shared with client delivery [Q6]. Feasibility is
therefore assessed **against contended engineering attention, not against a
date**.

Two practical consequences. Blocking the workflow on engineering tasks is
expensive when engineers are on client work — which is why the orchestration spike
was scheduled in parallel rather than as a gate [Q7]. And no delivery estimate is
offered anywhere in this assessment: with capacity contended and unquantified, any
duration figure would be invented rather than derived.

## Assumptions & Open Questions

- No clinic has been consulted. Every requirement is inferred from the intent
  statement and the brief rather than observed. [assumption]
- Indic code-switching quality — the central differentiator — is unvalidated, and
  no published benchmark exists for Indian-accented or 8kHz telephony audio from
  any vendor. [assumption]
- Whether the agent must write into a client EHR, or can own its own calendar for
  the MVP, is undetermined and materially changes difficulty. [Q1]
- Vendor compliance postures are as recorded in `docs/vendors.md`, which states
  they must be confirmed directly with each vendor before contracting.
  [assumption]
- The compliance analysis here is derived from research, not legal advice, and
  `docs/vendors.md` states counsel review is required in both jurisdictions.
  [assumption]
- No effort, duration or cost estimate is offered; capacity is contended and
  unquantified, so any figure would be manufactured. [assumption]
- Whether the human-handoff destination is the clinic's existing phone system or
  ours is undecided, and it affects both the integration surface and the
  acceptance property identified in `../market-research/market-trends.md`.
  [assumption]
