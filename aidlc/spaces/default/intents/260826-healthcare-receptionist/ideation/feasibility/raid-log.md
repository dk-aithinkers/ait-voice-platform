# RAID Log — Risks, Assumptions, Issues, Dependencies

## Purpose and scoring

Live register for the initiative described in the approved intent statement
(`../intent-capture/intent-statement.md`), drawing on the approved market
research (`../market-research/competitive-analysis.md`,
`../market-research/market-trends.md`, `../market-research/build-vs-buy.md`), the
answers in `feasibility-questions.md`, and `feasibility-assessment.md`.

Likelihood and impact are scored **High / Medium / Low**. Severity is their
combination, and treatment is one of **Mitigate / Transfer / Accept / Avoid**.

Owner is recorded as the decision-maker named at intent capture, or `Unassigned`
where no owner has been established — never invented.

## Risks

| ID | Risk | Likelihood | Impact | Severity | Treatment | Owner |
|---|---|---|---|---|---|---|
| R-01 | **Indic code-switching quality does not meet the bar in practice.** It is the central differentiator, every vendor claim is unvalidated, and `docs/vendors.md` records that no vendor publishes an Indian-accent or 8kHz telephony benchmark. | Medium | High | **High** | Mitigate — run an accuracy bake-off on real Indian call recordings at 8kHz before vendor selection is frozen. `docs/vendors.md` already names this the single biggest open risk in vendor selection. | Deepak |
| R-02 | **The agent must write into a client EHR, and that system is hard or closed to integrate with.** Difficulty is unknowable until the systems are named. | Medium | High | **High** | Mitigate — resolve through D-01 below. Fall back to a standalone calendar for the MVP if integration proves disproportionate. | Deepak |
| R-03 | **Building against both regulatory regimes at once.** With the jurisdiction undecided [Q3], both the US and India constraint sets in `constraint-register.md` must be treated as potentially binding, roughly doubling the compliance surface carried through design. | High | Medium | **High** | Mitigate — resolve through D-01. Until then, accept the cost of dual-regime design rather than guessing a jurisdiction. | Deepak |
| R-04 | **Compliance architecture is frozen before counsel reviews it.** Counsel is engaged before real patient data flows [Q8], but `BRIEF.md` places region pinning, redaction, consent and audit in Phase 1 as "brutally expensive to retrofit". The two moments are not the same. | High | Medium | **High** | Accept, knowingly — a deliberate cost decision recorded at [Q8]. Reduce exposure by keeping Phase 1 compliance decisions conservative and reversible where cheap. | Deepak |
| R-05 | **The orchestration spike fails and forces rework.** The LiveKit recommendation in `../market-research/build-vs-buy.md` is explicitly conditional on proving Exotel bidirectional streaming, and the spike runs in parallel with Inception [Q7]. | Low | Medium | Medium | Accept — exposure is bounded to design decisions, not requirements. Its urgency rises sharply if D-01 resolves the jurisdiction to India. | Unassigned |
| R-06 | **India regulatory registration delays or blocks the India pilot.** DLT registration and 1600-series numbering are mandatory, carried in-house (C-O6), and are a precondition rather than a task. | Medium | Medium | Medium | Mitigate — begin registration as soon as India is confirmed as a target market, not when the agent is ready to call. | Unassigned |
| R-07 | **Contended capacity stalls the work indefinitely.** No deadline [Q4] and shared client-delivery capacity [Q6] together remove both the forcing function and the dedicated attention. | Medium | Medium | Medium | Accept — an explicit consequence of funding the work from services revenue. Visible progress through approval gates is the substitute for a deadline. | Deepak |
| R-08 | **US practice consolidation makes the accessible-price position unsellable.** `../market-research/market-trends.md` records independent practices down to 120,900 with 63.9% of practices corporate-owned, and corporate buyers procure like enterprises. | Medium | Medium | Medium | Mitigate — test against the actual client base rather than the general market; the intent statement scopes the customer to existing relationships. | Deepak |
| R-09 | **No BAA-capable vendor exists for the best Indian language capability.** `docs/vendors.md` records that Rumik, Sarvam, Gnani, Exotel and Reverie have no HIPAA posture as a category, so a US clinic serving Indian-language speakers cannot use the best-in-class tooling. | Medium | Low | Low | Accept — a known limit of the vendor landscape, and the reason C-T1 exists. Revisit only if a US client requires Indic language support. | Unassigned |

## Assumptions

| ID | Assumption | Validation owner | Status |
|---|---|---|---|
| A-01 | AI Thinkers' existing healthcare clients want this and at least one will pilot | Deepak | Unvalidated — no clinic consulted |
| A-02 | Front-desk overload is the problem clinics would actually pay to solve, and staff hours saved is the metric they care about | Deepak | Unvalidated — inherited from intent capture [Q1][Q10 of intent capture] |
| A-03 | Patient acceptance of voice agents is high enough for routine scheduling | Deepak | Partially supported — `../market-research/market-trends.md` cites ~72% comfort, but from vendor-published sources, and finds acceptance contingent on human availability |
| A-04 | Vendor compliance postures are as recorded in `docs/vendors.md` | Unassigned | Unvalidated — that document states each must be confirmed directly with the vendor before contracting |
| A-05 | Success metrics can be made measurable once a pilot clinic provides baseline data | Deepak | Unvalidated — carried from intent capture; no numeric targets exist |
| A-06 | Python-first orchestration suits the team | Deepak | Supported — [Q2] and the framework landscape agree |
| A-07 | DPDP does not mandate data localisation | Unassigned | Low-to-medium confidence per `docs/vendors.md`; requires Indian counsel |
| A-08 | Willingness to pay for Indic code-switching exists | Unassigned | Unvalidated hypothesis from `../market-research/competitive-analysis.md` |

## Issues

Issues are problems that already exist, as distinct from risks that might occur.

| ID | Issue | Impact | Treatment | Owner |
|---|---|---|---|---|
| I-01 | **The initiative has no named pilot clinic.** Recorded at intent capture and unchanged since. It leaves the stakeholder map with a role and no party, and blocks D-01. | Blocks resolution of the two largest unknowns | Select a candidate client and open the conversation | Deepak |
| I-02 | **Success metrics carry no numeric targets or measurement windows.** Carried forward from intent capture and flagged Major by the product-lead review. | Success is directional rather than testable; acceptance criteria cannot yet be written | Attach a number and a window to each metric before requirements use them as acceptance criteria | Deepak |
| I-03 | **No India-market price point was found**, so the hybrid pricing model has no India-side reference. | Pricing for one of two target markets is unanchored | Requires India-specific pricing research or a client conversation | Unassigned |

## Dependencies

| ID | Dependency | Blocks | Type | Owner |
|---|---|---|---|---|
| **D-01** | **A conversation with a prospective pilot clinic** | Q1 (EHR systems), Q3 (jurisdiction), I-01 (named stakeholder), and downstream R-02 and R-03 | External — requires a client, not engineering | Deepak |
| D-02 | Accuracy bake-off on real Indian call recordings at 8kHz | R-01; vendor selection for the India path | Internal — needs real call recordings, which likely depend on D-01 | Unassigned |
| D-03 | Orchestration spike proving Exotel bidirectional streaming against LiveKit | Confirms or reopens the recommendation in `../market-research/build-vs-buy.md` | Internal — engineering, scheduled during Inception [Q7] | Unassigned |
| D-04 | DLT registration and 1600-series numbering | Any India outbound calling | External — carrier portals, no provider does it for you | Unassigned |
| D-05 | Executed BAAs across the full vendor chain | Any US deployment handling real PHI | External — vendor contracting | Unassigned |
| D-06 | Compliance counsel review, both jurisdictions | Freezing the compliance architecture safely (see R-04) | External — legal engagement | Deepak |

## The one that matters most

**D-01 is the critical path.** It is the only item that unblocks three others at
once — the EHR question, the jurisdiction question, and the named-stakeholder
issue — and it also gates D-02, since the bake-off needs real call recordings.
It requires no engineering capacity, which matters given C-O1.

Every stage after this one produces better output with D-01 resolved than
without it.

## Assumptions & Open Questions

- Six entries carry `Unassigned` as owner because no owner has been established
  for them; they are not left blank and no owner has been invented.
  [assumption]
- Likelihood and impact scores are the orchestrator's judgement from the
  approved artifacts and `docs/vendors.md`, not the output of a scoring workshop
  with the team. [assumption]
- This log is a snapshot at the end of feasibility. It is intended to be
  maintained through Inception and Construction, not frozen here. [assumption]
- No risk here has a quantified cost or delay impact, because no budget, timeline
  or capacity baseline exists to quantify against [Q4][Q6]. [assumption]
