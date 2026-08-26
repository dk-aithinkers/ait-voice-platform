# Feasibility & Constraint Analysis — Questions

**Mode:** guided

## Context

These questions build on the approved intent statement
(`../intent-capture/intent-statement.md`) and the approved market research
(`../market-research/competitive-analysis.md`, `market-trends.md`,
`build-vs-buy.md`).

Three items were deliberately carried into this stage and appear below: the
launch jurisdiction (Q3), the orchestration spike (Q7), and the
practice-management/EHR systems your clients run (Q1) — the last of which the
competitive analysis identified as the single most consequential unknown.

Every question offers an explicit "not yet known" option. Several of these are
things nobody could reasonably know yet, and recording that honestly is more
useful than a guess that later hardens into a requirement.

---

## Q1. Which practice-management or EHR systems do AI Thinkers' healthcare clients actually run?

`competitive-analysis.md` identifies this as the gap that blocks the
healthcare-depth half of our positioning: Sully.ai's stated moat is 50+ EHR
integrations, and we cannot scope ours without knowing the targets.

A. Known and small in number — one or two systems cover most clients.
B. Known but varied — several different systems across the client base.
C. Partially known — we know some clients' systems but have not surveyed properly.
D. Not known — this needs a conversation with the clients before it can be answered.
E. No EHR integration in the MVP — the agent will run standalone with its own calendar, and integration comes later.
X. Other (please specify)

[Answer]: D. Not known — this needs a conversation with the clients before it can be answered.

_Recorded note: the human answered "don't know", recorded as the explicit not-known option._

---

## Q2. What is the team's current technical stack and skill profile?

Nothing recorded so far establishes what the engineering team actually works in.
This drives whether the orchestration and platform choices are realistic.

A. Primarily Python — comfortable with async services, ML/AI tooling.
B. Primarily TypeScript/Node — comfortable with web services and real-time APIs.
C. Both Python and TypeScript in regular use across the team.
D. Primarily other (Java, Go, .NET) — voice/AI work would be new ground.
E. Not yet defined — team composition for this project is not settled.
X. Other (please specify)

[Answer]: A. Primarily Python — comfortable with async services, ML/AI tooling.

---

## Q3. Which jurisdiction should the first deployment target?

Raised as a Major finding at intent capture and deliberately left open by the
market research. `docs/vendors.md` establishes that no single vendor serves both
markets, so this decision drives vendor selection, data residency, and the
compliance work in the platform core.

A. India first (DPDP) — lighter launch burden, existing relationships, the market incumbents ignore.
B. US first (HIPAA) — higher willingness to pay, compliance work reusable for the finance pack later.
C. Both simultaneously — the platform is dual-market by design and both tenants launch together.
D. Not yet known — it depends on which client agrees to pilot first, and that conversation has not happened.
X. Other (please specify)

[Answer]: D. Not yet known — it depends on which client agrees to pilot first, and that conversation has not happened.

---

## Q4. What are the budget and timeline constraints?

Feasibility assessment needs a boundary to assess against. Nothing recorded so
far establishes one.

A. Firm deadline — there is a date this must be demonstrable by.
B. Firm budget ceiling — a defined spend limit, timeline flexible.
C. Both defined — a budget and a date.
D. Neither is fixed — this is funded from ongoing services work and paced accordingly.
E. Not yet defined.
X. Other (please specify)

[Answer]: D. Neither is fixed — this is funded from ongoing services work and paced accordingly.

---

## Q5. What cloud accounts and infrastructure does AI Thinkers already run?

`docs/vendors.md` notes AWS offers an account-wide BAA covering HIPAA-eligible
services at no extra fee, which materially affects the US compliance path.

A. AWS already in use, with an organisation and existing accounts.
B. AWS in use but minimally — no organisation structure or established practice.
C. A different primary cloud (Azure, GCP) is in use.
D. Mixed / varies by client engagement.
E. Not yet defined — no established cloud footprint for this project.
X. Other (please specify)

[Answer]: A. AWS already in use, with an organisation and existing accounts.

---

## Q6. Are there organisational blockers or competing priorities?

A. No — this project has clear runway.
B. Yes — the team is shared with client delivery work and capacity is contended.
C. Yes — other constraints (hiring, other product commitments, seasonal client load).
D. Not yet known.
X. Other (please specify)

[Answer]: B. Yes — the team is shared with client delivery work and capacity is contended.

---

## Q7. Should the orchestration spike run before or after this stage's assessment?

`build-vs-buy.md` recommends LiveKit but makes it explicitly conditional on a
time-boxed spike proving Exotel bidirectional streaming works against it. Until
that spike runs, the orchestration decision is a recommendation, not a finding.

A. Run the spike before Inception — treat the orchestration choice as unresolved until it passes, and record it as a blocking dependency.
B. Run the spike during Inception, in parallel with requirements work — accept the risk that a failure forces rework.
C. Skip the spike — accept the LiveKit recommendation on the documented evidence and move on.
D. Not yet decided — record it as a risk and let delivery planning schedule it.
X. Other (please specify)

[Answer]: B. Run the spike during Inception, in parallel with requirements work — accept the risk that a failure forces rework.

_Recorded note: the human first answered "not sure"; B was confirmed after the orchestrator noted that the spike's urgency depends on the unresolved jurisdiction (Q3) and that contended capacity (Q6) argues against blocking._

---

## Q8. How should compliance expertise be obtained?

`docs/vendors.md` states plainly that its compliance section is research, not
legal advice, and that a US healthcare-compliance attorney and an Indian
data-protection/telecom counsel need to review before architecture is frozen.
The intent statement records that external compliance advisors were deliberately
not included as stakeholders.

A. Engage counsel before architecture is frozen, as the vendor research recommends.
B. Engage counsel only when a pilot client is named and the jurisdiction is settled.
C. Proceed on documented research for the MVP; engage counsel before any real patient data is handled.
D. Not yet decided — record it as a risk in the RAID log.
X. Other (please specify)

[Answer]: C. Proceed on documented research for the MVP; engage counsel before any real patient data is handled.

---

## Consolidated Summary Confirmation

Summary of all answers:

- The practice-management/EHR systems the clients run are **not known**, and answering requires a conversation with those clients. [Q1]
- The team works **primarily in Python**, comfortable with async services and ML/AI tooling. [Q2]
- The **launch jurisdiction is not yet known**; it depends on which client agrees to pilot, and that conversation has not happened. [Q3]
- **Neither budget nor timeline is fixed.** The work is funded from ongoing services revenue and paced accordingly. [Q4]
- **AWS is already in use**, with an organisation and existing accounts. [Q5]
- The **team is shared with client delivery work** and capacity is contended. [Q6]
- The orchestration spike runs **during Inception, in parallel** with requirements work, accepting bounded rework risk. [Q7]
- Compliance proceeds on **documented research for the MVP**, with counsel engaged before any real patient data is handled. [Q8]

**Root-cause convergence — the finding that matters most.** Q1 and Q3 are not two
independent unknowns. Both are blocked on the same missing event: a conversation
with a prospective pilot clinic. Intent capture already recorded that no pilot
clinic is named. So a single action — selecting and talking to one client —
would resolve the EHR question, the jurisdiction question, and give the
stakeholder map a real party instead of a role. Nothing else on the open list
unlocks three items at once. This is recorded as the critical-path dependency in
the RAID log.

**Tension the answers create, which must be recorded as a risk.** Q8 places the
compliance-counsel gate before real patient data is handled. But `BRIEF.md`
states that region pinning, redaction, the consent engine and the audit log are
Phase 1 architecture — "cheap now, brutally expensive to retrofit" — and
`docs/vendors.md` recommends counsel review *before architecture is frozen*.
Those two points are not the same moment: architecture will be frozen well before
patient data flows. Q8 is therefore a deliberate, reasonable cost decision that
**accepts rework risk on the compliance architecture**, and it is recorded that
way rather than as a resolved question. It is not treated as a contradiction —
the human's choice stands — but the gap between the two moments is a risk with a
named owner in the RAID log.

**Consequences worth stating plainly:**

- Q4 and Q6 together mean feasibility is assessed **against contended capacity,
  not against a deadline**. There is no date to be late for; the binding
  constraint is engineering attention competing with paid client work.
- Q2 and the orchestration recommendation in `build-vs-buy.md` are a **good fit**:
  the candidate frameworks are Python-first, so the recommendation does not
  require the team to work against its stack.
- Q5 helps the US path materially — an account-wide AWS BAA covers HIPAA-eligible
  services at no additional fee — but `docs/vendors.md` records that AWS has **no
  India telephony presence** and that its streaming PII redaction **does not cover
  Hindi or any Indic language**. Existing AWS accounts therefore help with
  hosting, models and storage, and do not help with the India voice path.

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
