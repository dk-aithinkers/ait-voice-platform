# Scope Definition & Prioritization — Questions

**Mode:** guided

## Context

These build on the approved intent statement
(`../intent-capture/intent-statement.md`), the feasibility assessment
(`../feasibility/feasibility-assessment.md`), the constraint register
(`../feasibility/constraint-register.md`) and the RAID log
(`../feasibility/raid-log.md`).

`BRIEF.md` proposes the MVP as "platform core plus the healthcare receptionist
pack, deployable to both a US and an India tenant". Feasibility found that
several parts of that are much more expensive than others, and that two of the
inputs it depends on are unknown. These questions decide where the boundary
actually falls.

Every question offers a "not yet decided" option.

---

## Q1. Does the MVP include writing into a client's practice-management/EHR system?

The target systems are unknown [feasibility Q1], and `raid-log.md` records this
as R-02 with High severity. `competitive-analysis.md` identifies EHR integration
as the moat that separates a healthcare product from a generic receptionist.

A. Yes — EHR integration is in the MVP. Accept that scope cannot be fixed until D-01 resolves the target systems.
B. No — the agent owns its own calendar for the MVP; EHR integration is a fast-follow. Buildable today, concedes healthcare depth until later.
C. Read-only first — the agent reads availability from the EHR but writes nothing, as a lower-risk half-step.
D. Not yet decided — depends entirely on what D-01 reveals.
X. Other (please specify)

[Answer]: B. No — the agent owns its own calendar for the MVP; EHR integration is a fast-follow. Buildable today, concedes healthcare depth until later.

---

## Q2. Which of the four capabilities are must-have for the MVP?

The intent statement names four: answer calls 24/7, book and reschedule
appointments, patient intake, and outbound reminder calls.

`constraint-register.md` records that outbound calling carries by far the
heaviest regulatory load — C-R5 (no marketing content, US), C-R6 (1600-series
numbering plus DLT registration, India), C-R9 (7-day consent expiry, India) —
and `raid-log.md` records D-04 as a precondition rather than a task.

A. All four — the full pack as described in the intent statement.
B. Three — answering, booking/rescheduling and intake. Outbound reminders deferred, removing the heaviest regulatory burden from the MVP.
C. Two — answering and booking/rescheduling only. The tightest possible slice that still solves front-desk overload.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. All four — the full pack as described in the intent statement.

---

## Q3. Does the MVP deploy to one tenant region or both?

`raid-log.md` records R-03: with the jurisdiction undecided, both regulatory
regimes must be treated as potentially binding, roughly doubling the compliance
surface carried through design.

A. Both US and India at MVP, as `BRIEF.md` proposes.
B. One region at MVP, chosen when D-01 resolves — but the platform is built region-pinnable from day one so the second is configuration rather than rework.
C. One region at MVP, chosen now, with region-pinning deferred until a second market is real.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Both US and India at MVP, as `BRIEF.md` proposes.

---

## Q4. Does the MVP need multi-tenancy from day one?

`build-vs-buy.md` establishes multi-tenancy must be built in-house (C-T4) because
no managed platform provides it, and `BRIEF.md` calls it the substrate of both
business models. But the MVP serves one pilot clinic.

A. Yes — build multi-tenancy from the start. It is the substrate; retrofitting tenant isolation is expensive and error-prone.
B. No — single-tenant for the pilot, multi-tenancy when the second client is real. Faster to a working pilot.
C. Tenant-aware but not multi-tenant — carry a tenant identifier through the data model and isolate later, as a middle path.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Yes — build multi-tenancy from the start. It is the substrate; retrofitting tenant isolation is expensive and error-prone.

---

## Q5. What operator surface does the MVP need?

`BRIEF.md` sequences the business model as managed service first, SaaS second,
and notes the dashboard built for the first is the foundation of the second.

A. Internal only — your team configures agents; the clinic gets a working phone number and nothing else.
B. Internal configuration plus a read-only clinic view — the clinic sees calls, transcripts and bookings but changes nothing.
C. Clinic self-service — the clinic configures greetings, hours and routing itself.
D. Not yet decided.
X. Other (please specify)

[Answer]: B. Internal configuration plus a read-only clinic view — the clinic sees calls, transcripts and bookings but changes nothing.

---

## Q6. Which sequencing heuristic should order the build?

`workflow-planning-guide.md` offers four. `raid-log.md` places the highest
severity on R-01 (Indic code-switching unvalidated) and R-02 (EHR integration
unknown).

A. Risk-first — sequence the highest-uncertainty work early so decisions are calibrated before dependent work commits.
B. Walking-skeleton-first — a minimal end-to-end call (ring, answer, converse, hang up) before any feature depth.
C. Value-first — ship what solves front-desk overload soonest.
D. Not yet decided — let delivery planning choose.
X. Other (please specify)

[Answer]: B. Walking-skeleton-first — a minimal end-to-end call (ring, answer, converse, hang up) before any feature depth.

_Recorded note: the human first answered "not sure"; B was confirmed after the orchestrator noted that the active `feature` scope declares `skeleton: on` (so a skeleton Bolt runs regardless) and that risk-first is partly blocked because the R-01 bake-off depends on D-01._

---

## Q7. What is explicitly out of scope for this initiative?

Naming exclusions prevents scope creep later. Select all that should be
explicitly excluded.

A. The aerospace AOG and finance packs — deferred to separate initiatives, as `BRIEF.md` proposes.
B. Payment handling of any kind — keeps PCI DSS entirely out of scope.
C. Clinical decision-making, triage or advice — the agent handles administrative calls only.
D. All of A, B and C.
X. Other (please specify)

[Answer]: D. All of A, B and C.

---

## Consolidated Summary Confirmation

Summary of all answers:

- **No EHR integration in the MVP.** The agent owns its own calendar; integration is a fast-follow. [Q1]
- **All four capabilities are in:** 24/7 answering, booking and rescheduling, patient intake, and outbound reminder calls. [Q2]
- **Both US and India tenants at MVP**, as `BRIEF.md` proposes. [Q3]
- **Full multi-tenancy from day one.** [Q4]
- **Operator surface:** internal configuration plus a read-only clinic view. [Q5]
- **Sequencing:** walking-skeleton-first. [Q6]
- **Explicitly out of scope:** the aerospace AOG and finance packs, all payment handling, and any clinical decision-making, triage or advice. [Q7]

**The shape these answers create.** The one capability that is genuinely blocked
was cut, and the maximum was taken on everything else. The result is an MVP that
is **wide on infrastructure and narrow on the differentiator**:
`../market-research/competitive-analysis.md` identifies EHR integration as what
separates a healthcare product from a generic receptionist, and with it deferred
the MVP sits closer to the horizontal platforms than to the vertical position the
intent statement describes. This is a legitimate strategy — build the platform
properly, defer only what cannot be specified — but it is recorded plainly rather
than left implicit.

**Scope-versus-capacity validation, which this stage is required to run.** There
is no deadline and no budget ceiling, and engineering capacity is contended with
paid client delivery. Against that, the scope is the largest available on every
axis except EHR integration. **There is no forcing function and a large build.**
That combination is recorded as a risk rather than resolved here; the walking
skeleton [Q6] partially mitigates it by producing something demonstrable early.

**A consequence that needs a decision before the pilot, not after.** With no EHR
integration [Q1] but booking, rescheduling and outbound reminders all in scope
[Q2], the agent's own calendar becomes the source of truth for appointments. A
clinic already running a practice-management system will not move its calendar,
so the MVP either serves clinics without an existing system, or creates
double-entry between our calendar and theirs. This is a real operational question
for the pilot and is carried into the scope document as an open question.

**D-04 is now on the critical path.** Outbound calling [Q2] plus an India tenant
[Q3] together make DLT registration and 1600-series numbering a hard
precondition for half the MVP, not background work. `../feasibility/raid-log.md`
records it with no owner and notes penalties escalating to ₹1M per instance. It
needs an owner and a start date.

**R-03 changes treatment.** `../feasibility/raid-log.md` recorded the dual-regime
compliance surface as Mitigate, to be resolved by choosing a jurisdiction. [Q3]
chooses both, so its treatment becomes **Accept** — a knowing decision to carry
roughly double the compliance surface through design.

**Consistent and helpful:** excluding payment handling [Q7] keeps PCI DSS
entirely out of scope, and excluding clinical advice [Q7] supports the TCPA
healthcare-exemption boundary that constraint C-R5 depends on. The
walking-skeleton choice [Q6] also matches the active `feature` scope's
`skeleton: on` declaration, so the plan and the execution agree.

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
