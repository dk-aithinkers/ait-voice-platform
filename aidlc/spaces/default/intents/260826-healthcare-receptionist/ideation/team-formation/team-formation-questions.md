# Team Formation & Mob Planning — Questions

**Mode:** guided

## Context

These build on the approved scope document
(`../scope-definition/scope-document.md`), the intent backlog
(`../scope-definition/intent-backlog.md`) and the feasibility assessment
(`../feasibility/feasibility-assessment.md`).

Three things are already established and are not re-asked: the team works
primarily in Python, capacity is contended with paid client delivery, and scope
and priority decisions rest with Deepak while engineering influences them.

What is not established is **who** — no individual, count, or allocation appears
anywhere in the workflow so far. That is what this stage needs.

**A clarification, because it could look like a contradiction.** Scope definition
excluded *partnering* — reselling, white-labelling, distribution deals. That was a
product decision. Bringing in a contractor or specialist to build the thing is
staffing, not partnering, and is not excluded by it. Q6 below asks about staffing
on that understanding.

---

## Q1. How many engineers are actually available for this work?

`scope-document.md` records the scope as the largest available on every axis
except EHR integration. Team size determines whether that is achievable at all.

A. One — effectively a solo build with AI assistance.
B. Two to three.
C. Four to six.
D. More than six.
E. Not yet decided — the team for this project has not been assembled.
X. Other (please specify)

[Answer]: A. One — effectively a solo build with AI assistance.

---

## Q2. What share of their time is genuinely available?

Feasibility recorded capacity as contended with paid client delivery, but not by
how much.

A. Full time — this is their primary assignment.
B. Roughly half — split between this and client work.
C. Whatever is left over — client work takes priority and this fills the gaps.
D. Varies unpredictably by client demand.
E. Not yet decided.
X. Other (please specify)

[Answer]: C. Whatever is left over — client work takes priority and this fills the gaps.

---

## Q3. Which of the required skills exist in the team today? (Select all that are genuinely present.)

Derived from `../scope-definition/intent-backlog.md`. Anything not selected is
recorded as a gap, not as a deficiency — gaps are normal and are what the
remediation plan is for.

A. Real-time voice or telephony engineering (streaming audio, WebSocket media, latency tuning).
B. Healthcare compliance engineering (PHI handling, audit logging, consent and redaction).
C. Cloud infrastructure and multi-region deployment on AWS.
D. Frontend for the operator dashboard and clinic view.
E. None of these are established in the team today.
X. Other (please specify)

[Answer]: A, B, C, D — all four skill areas are present today.

---

## Q4. Are there competing initiatives drawing on the same people?

A. Yes — specific named client projects compete for the same engineers.
B. Yes — general client delivery, not one specific project.
C. No — the people who would work on this are not committed elsewhere.
D. Not yet known.
X. Other (please specify)

[Answer]: B. Yes — general client delivery, not one specific project.

---

## Q5. Where is the team located, and does it span time zones?

Relevant because `mob-programming-guide.md` treats co-presence as a precondition
for mobbing, and the walking-skeleton Bolt benefits from it.

A. Single location, single time zone — co-located or fully overlapping.
B. Single country, distributed — substantial overlap.
C. Spans time zones with limited overlap.
D. Not yet decided.
X. Other (please specify)

[Answer]: X. Other — not applicable. Q1 establishes a team of one, so there is no distribution or time-zone overlap to assess.

---

## Q6. Is bringing in outside help on the table?

Staffing, not product partnering — see the clarification above.

A. No — this is built entirely with the existing team.
B. Yes for specialist gaps only — for example voice engineering or compliance, if Q3 shows those missing.
C. Yes, more broadly — contractors to add general capacity.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. No — this is built entirely with the existing team.

---

## Q7. How should the work actually be done, day to day?

`mob-programming-guide.md` describes mobbing as strongest where uncertainty is
high and knowledge needs spreading — which describes this project, since
`../feasibility/feasibility-assessment.md` records the whole voice domain as new
ground for the team.

A. Mob on the hard parts — the walking skeleton and anything novel — and work solo on well-understood pieces.
B. Mob throughout — maximise knowledge spread across a team new to voice.
C. Solo work with code review — conventional, lowest coordination overhead.
D. Not yet decided.
X. Other (please specify)

[Answer]: X. Other — mobbing is not available to a team of one. The human confirmed this stage should produce an honest assessment without a mob plan, stating plainly why mobbing does not apply and what replaces it for a solo build.

---

## Consolidated Summary Confirmation

Summary of all answers:

- **One engineer**, effectively a solo build with AI assistance. [Q1]
- **Whatever time is left over** after client delivery, which takes priority. [Q2]
- **All four required skill areas are present today**: real-time voice/telephony, healthcare compliance engineering, AWS cloud infrastructure, and frontend. [Q3]
- Contention is **general client delivery**, not one named project with an end date. [Q4]
- Team distribution and time zones are **not applicable** to a team of one. [Q5]
- **No outside help.** Built entirely with the existing team. [Q6]
- Mobbing is **not available** to a team of one; this stage produces an honest assessment rather than a mob plan. [Q7]

**The finding that dominates this stage.** The approved scope in
`../scope-definition/scope-document.md` is the largest available on every axis
except EHR integration — all four capabilities, both regulatory regions, full
multi-tenancy — and nine of the twelve in-scope proto-Units in
`../scope-definition/intent-backlog.md` are ranked Must. The delivery capacity
against it is **one person, on residual time, with no external help and no
deadline**.

This is not a risk that might occur. It is the current state, and it is a larger
gap than anything in `../feasibility/raid-log.md`. It is recorded as the headline
of `team-assessment.md` and as an issue rather than a risk, because it is already
true.

**A second-order consequence of [Q3].** All four skill areas being present is
genuinely favourable — no skill gap blocks the work, and no learning curve sits on
the critical path. But with [Q1] it also means the entire skill surface of the
project rests on one person. `team-topologies.md` treats bus factor as a primary
concern below five people; here it is one. Knowledge transfer has no recipient,
and `mob-programming-guide.md`'s "reduces bus factor to near zero" benefit is
structurally unavailable.

**What this does not change.** The scope was approved knowingly, the reduction
order is already recorded in `../scope-definition/scope-document.md`, and there is
no deadline to miss. A solo build on residual time is a legitimate way to run a
product experiment funded by services revenue. What changes is that the reduction
order is now the most useful artifact in the workflow rather than a contingency,
and D-01 — the pilot conversation, which needs no engineering capacity at all —
becomes even more clearly the highest-value next action.

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
