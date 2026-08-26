# Scope Document — Healthcare Receptionist MVP

## Purpose

Defines the in/out boundary for the initiative described in the approved intent
statement (`../intent-capture/intent-statement.md`), bounded by the
`../feasibility/feasibility-assessment.md` verdict and the constraints recorded
in `../feasibility/constraint-register.md`.

The scope below is what the seven answers in `scope-definition-questions.md`
decided. Where a decision carries a cost, the cost is stated rather than implied.

## In scope

### Capabilities

All four capabilities named in the intent statement are in the MVP [Q2]:

| Capability | Notes |
|---|---|
| Answer clinic calls 24/7, handling simultaneous callers | The baseline the whole initiative rests on |
| Book and reschedule appointments | Against the agent's own calendar, not a client EHR [Q1] |
| Patient intake | Structured capture over voice |
| Outbound reminder calls | Carries the heaviest regulatory load in the MVP — see "What this costs" |

### Platform

| Element | Decision | Source |
|---|---|---|
| Multi-tenancy | Full, from day one | [Q4] |
| Regions | Both US and India tenants at MVP | [Q3] |
| Provider abstraction | Every speech and telephony component replaceable per region | C-T1 in `../feasibility/constraint-register.md` |
| Compliance machinery | Region isolation, PII/PHI redaction, consent disclosure, immutable audit log | `BRIEF.md` Phase 1 position; C-R1 through C-R9 |
| Human handoff | With structured context — an acceptance requirement, not a fallback | C-T6; `../market-research/market-trends.md` |
| Operator surface | Internal configuration plus a read-only clinic view | [Q5] |

### Sequencing

**Walking-skeleton-first** [Q6]: a minimal end-to-end call — ring, answer,
converse, hang up — across the real vendor chain before any feature depth. This
matches the active `feature` scope's `skeleton: on` declaration, so the recorded
heuristic and the framework's execution agree rather than conflict.

## Out of scope

Explicitly excluded [Q7]. Naming these prevents them reappearing as assumed
scope later.

| Excluded | Why, and what it buys |
|---|---|
| Aerospace AOG and finance agent packs | Deferred to separate initiatives per `BRIEF.md`. The platform core is built vertical-agnostic so they remain cheap to add. |
| Payment handling of any kind | Keeps PCI DSS entirely out of scope — the single largest compliance regime avoided outright. |
| Clinical decision-making, triage or advice | The agent is administrative only. Supports the TCPA healthcare-exemption boundary (C-R5) and avoids clinical liability. |
| EHR / practice-management integration | Deferred to fast-follow [Q1]. The target systems are unknown, so it cannot be scoped — see "What this costs". |
| Clinic self-service configuration | The SaaS surface; `BRIEF.md` sequences it after the managed service proves out. |

## What this costs

Recording the price of the boundary above, so it is visible rather than
discovered later.

**The MVP is wide on infrastructure and narrow on the differentiator.**
`../market-research/competitive-analysis.md` identifies EHR integration as what
separates a healthcare product from a generic receptionist. Deferring it [Q1]
while taking the maximum on capabilities, regions and tenancy produces a large
platform delivering a product positioned closer to the horizontal receptionist
platforms than to the vertical position the intent statement describes. The
differentiator arrives with the fast-follow, not with the MVP.

**Scope against capacity.** There is no deadline and no budget ceiling, and
engineering capacity is contended with paid client delivery
(`../feasibility/feasibility-assessment.md`, "Pace and capacity"). The scope is
the largest available on every axis except EHR integration. **There is no forcing
function and a large build.** The walking skeleton partially mitigates this by
producing something demonstrable early; nothing else in this scope does.

**Both regions doubles the compliance surface.** `../feasibility/raid-log.md`
recorded this as R-03 with treatment Mitigate, to be resolved by choosing one
jurisdiction. [Q3] chooses both, so the treatment becomes **Accept**: a knowing
decision to carry both regulatory regimes through design.

**Outbound calling plus an India tenant makes DLT registration critical path.**
Together, [Q2] and [Q3] turn D-04 — DLT registration and 1600-series numbering —
from background work into a hard precondition for half the MVP. No provider
performs it on a customer's behalf, penalties escalate to ₹1M per instance with a
two-year cross-operator blacklist, and `../feasibility/raid-log.md` currently
records it with no owner. **It needs an owner and a start date before India
development is meaningful.**

## Open question the pilot must answer

**Whose calendar is the source of truth?** With no EHR integration [Q1] but
booking, rescheduling and outbound reminders all in scope [Q2], the agent's own
calendar becomes the appointment system of record. A clinic already running a
practice-management system will not move its calendar to ours. So the MVP either
serves clinics with no existing system, or creates double-entry between two
calendars.

This is not resolvable by design work. It is a question for the pilot
conversation recorded as D-01 in `../feasibility/raid-log.md`, and it materially
affects who the MVP can be sold to.

## Minimum viable scope, if the boundary needs to move

Recorded now so a later scope reduction is a decision rather than an improvisation.
In descending order of what could be cut with least damage:

1. **Outbound reminder calls** — removes DLT registration, 1600-series numbering,
   TCPA marketing constraints, and 7-day consent expiry from the MVP entirely.
   The largest compliance reduction available. Costs the no-show-reduction success
   metric.
2. **The India tenant** — halves the compliance surface and removes the
   India-specific vendor and regulatory work. Costs the market the incumbents
   ignore, which is a core part of the differentiation argument.
3. **Full multi-tenancy**, reduced to tenant-aware — defers isolation machinery
   one pilot clinic does not exercise. Costs a later retrofit, which with PHI is a
   compliance surface rather than only an engineering one.
4. **Patient intake** — the least entangled capability to defer.

The read-only clinic view is deliberately not on this list: without it the clinic
cannot see value and the success metrics cannot be measured.

## Assumptions & Open Questions

- No clinic has been consulted, so the boundary above is drawn from the intent
  statement and the brief rather than from a customer's requirements.
  [assumption]
- Whether the agent's own calendar is acceptable as the appointment system of
  record is unknown and materially affects who the MVP can serve. [assumption]
- The fast-follow EHR integration cannot be scoped, sized or sequenced until D-01
  identifies the target systems. [assumption]
- No effort or duration estimate accompanies this scope; capacity is contended
  and unquantified, so any figure would be manufactured. [assumption]
- Whether an India pilot is viable at all depends on D-04 starting early enough,
  and D-04 currently has no owner. [assumption]
