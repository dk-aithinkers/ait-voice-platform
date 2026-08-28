# Initiative Approval & Handoff — Questions

**Mode:** guided

## Context

This is the phase gate. It compiles all nine Ideation artifacts into an
initiative brief and a decision log, runs the Ideation → Inception traceability
check, and asks for a go/no-go.

The stage template asks several questions that six stages of answers have already
settled or made unanswerable, and per this project's practice those are recorded
as resolved rather than re-asked:

| Template question | Status |
|---|---|
| Do all stakeholders agree on the intent and scope? | Answered by structure — the intent statement records that Deepak decides scope and priority, with engineering influencing. There is no wider stakeholder body to poll, and no pilot clinic exists to consult. |
| Is there budget/resource commitment? | Answered — no budget ceiling and no deadline; funded from services revenue, delivered by one engineer on residual time. |
| Are mobs staffed and scheduled? | Not applicable — a team of one, per `../team-formation/mob-composition.md`. |

What genuinely remains open is whether to proceed, and on what terms. That is
what the questions below ask.

---

## Q1. Go or no-go on the initiative as it stands?

`../team-formation/team-assessment.md` records the scope-versus-capacity gap as
an issue rather than a risk, and lists three options: proceed as approved, reduce
scope using the prepared order, or add capacity (excluded).

A. Go as approved — proceed into Inception with the full scope.
B. Go with reduced scope — apply the reduction order in `../scope-definition/scope-document.md` before Inception begins.
C. Go, but pause after Inception — complete the design work, then re-decide before any code is written.
D. No-go — stop here and revisit when a pilot clinic or more capacity exists.
X. Other (please specify)

[Answer]: A. Go as approved — proceed into Inception with the full scope.

---

## Q2. Have the critical risks been acknowledged, and are their treatments right?

`../feasibility/raid-log.md` carries four High-severity items. Scope definition
and team formation have since changed two of them.

A. Yes — the risks and treatments in the RAID log are accepted as they stand, with the two corrections this stage records (R-03 to Accept, R-07 understated).
B. Yes, with the non-voice access gap promoted to a named risk — the reviewer at rough mockups recommended it and it is currently only an assumption in a wireframe file.
C. Not yet — some treatment is wrong and should be revisited before handoff.
D. Not yet reviewed in enough detail to say.
X. Other (please specify)

[Answer]: B. Yes, with the non-voice access gap promoted to a named risk.

---

## Q3. Does the market research support the investment?

`../market-research/market-trends.md` declined to produce a market size, reporting
a 4× spread across analyst estimates, and `../market-research/competitive-analysis.md`
found the differentiator narrower than assumed.

A. Yes — the growth direction and the underserved India position are enough to justify proceeding at this cost.
B. Yes, but the case rests on the India market, which makes the unowned DLT registration dependency more urgent than its RAID entry suggests.
C. Not really — the research supports the problem being real but not that we are the ones to solve it. Proceeding anyway on other grounds.
D. Not yet decided.
X. Other (please specify)

[Answer]: D. Not yet decided.

_Recorded note: the human expressed no preference among the offered options. Recorded as the not-yet-decided option rather than resolved on their behalf._

---

## Q4. Do the rough mockups and call flows reflect what you intended to build?

A. Yes — the flows and screens match the intent.
B. Mostly — with reservations recorded in the decision log rather than changed now.
C. No — something is materially wrong and should be fixed before Inception.
D. Not reviewed in enough detail to say.
X. Other (please specify)

[Answer]: A. Yes — the flows and screens match the intent.

---

## Q5. What should the first action after this gate be?

Inception opens with practices discovery and requirements analysis, neither of
which needs the pilot conversation. But D-01 unblocks four things and needs no
engineering capacity.

A. Start D-01 — the pilot clinic conversation — before or alongside Inception, treating it as the real first action.
B. Proceed straight into Inception; D-01 happens when it happens.
C. Proceed into Inception, but treat D-01 as a hard gate before Construction begins.
D. Not yet decided.
X. Other (please specify)

[Answer]: D. Not yet decided.

---

## Consolidated Summary Confirmation

Summary of all answers:

- **Go as approved.** Proceed into Inception with the full scope. [Q1]
- Risks accepted, **with the non-voice access gap promoted to a named risk** in the RAID log. [Q2]
- Whether the market research supports the investment: **no preference expressed**, recorded as undecided. [Q3]
- The mockups and call flows **match the intent**. [Q4]
- The first action after this gate is **not yet decided**. [Q5]

**The combination worth naming.** [Q1] proceeds at full scope; [Q5] leaves the
first action unsequenced. The critical-path item — D-01, the pilot clinic
conversation — is the thing that resolves the EHR question, the launch
jurisdiction, the unnamed stakeholder, and the calendar-source-of-truth question,
and it consumes no engineering capacity at all. Leaving it unsequenced does not
make it less critical; it makes it likelier not to happen, because nothing in the
workflow will produce it. Recorded in the brief as the top open item rather than
resolved here.

**Actions this stage takes as a result of [Q2]:**

1. The non-voice access gap becomes a named risk in
   `../feasibility/raid-log.md` — a caller who is deaf, hard of hearing, or whose
   speech the recogniser handles poorly cannot use the service at all, and no
   fallback has been decided.
2. R-03 changes treatment from Mitigate to **Accept**, because [Q3 of scope
   definition] chose both regulatory regions rather than resolving the
   jurisdiction.
3. R-07 is re-scored. It was assessed Medium before team formation established
   one engineer on residual time; `../team-formation/team-assessment.md`
   supersedes it and records the gap as an issue rather than a risk.

**On [Q3], the brief states what the research established rather than a verdict.**
No preference was expressed, so the initiative brief does not manufacture one. It
records what is factually true: `../market-research/market-trends.md` found a
consistent high-growth direction and could not produce a defensible market size,
and `../market-research/competitive-analysis.md` narrowed the differentiator from
"multilingual" to Indic code-switching, which remains unvalidated. Whether that
supports the investment is a judgement the person funding it makes.

**[Q4] confirms the design artifacts**, which matters because Refined Mockups in
Inception builds directly on them rather than starting over.

Does this all look correct before I generate the initiative brief, the decision
log and the phase verification?

- Looks correct
- Request changes

[Answer]: Looks correct
