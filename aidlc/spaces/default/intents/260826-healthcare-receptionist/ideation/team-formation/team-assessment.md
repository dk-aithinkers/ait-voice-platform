# Team Assessment

## The headline finding

**The approved scope and the available delivery capacity are not in the same
order of magnitude, and this is a present fact rather than a future risk.**

| | |
|---|---|
| **Approved scope** (`../scope-definition/scope-document.md`) | All four capabilities, both US and India regulatory regions, full multi-tenancy from day one, provider abstraction, compliance core, human handoff, analytics, and an operator surface |
| **Must-ranked proto-Units** (`../scope-definition/intent-backlog.md`) | 9 of 12 in-scope |
| **Available capacity** | One engineer [Q1], on residual time after client delivery [Q2], with no external help [Q6] |
| **Forcing function** | None — no deadline and no budget ceiling (`../feasibility/feasibility-assessment.md`) |

`../feasibility/feasibility-assessment.md` recorded a milder version of this as
R-07 ("contended capacity stalls the work") with Medium likelihood. That scoring
predates the team answers. With the capacity now quantified as one person on
leftover time, this is **recorded as an issue, not a risk** — a risk is something
that may occur; this is the current state.

This assessment does not recommend a course of action. The scope was approved
knowingly, and the choice of what to do about it belongs to the person who
approved it. What follows is what the options actually are.

## Capacity picture

**Team of one** [Q1], described as a solo build with AI assistance.

**Allocation is residual** [Q2]: client work takes priority and this fills the
gaps. Contention is general client delivery rather than a named project with an
end date [Q4], so it is continuous rather than a discrete conflict that resolves.

**No end date on the contention and no deadline on the work.** Together these
remove both the forcing function and the predictable windows that would let the
work be sequenced against known availability. Delivery planning will have to
sequence in small independent slices rather than long dependent chains, because
long chains assume sustained attention that residual time does not provide.

**No throughput figure is offered here.** Residual time is unquantified, no
velocity baseline exists, and no duration has been established anywhere in the
workflow. Any estimate would be manufactured.

## What is favourable

Recorded deliberately, because an assessment that only names problems is not an
assessment.

- **No skill gap blocks the work.** All four required skill areas — real-time
  voice and telephony, healthcare compliance engineering, AWS cloud
  infrastructure, and frontend — are present today [Q3]. Nothing sits on the
  critical path waiting for someone to learn it, and no hiring or contracting is
  needed to begin.
- **No coordination overhead.** A team of one has no handoffs, no merge
  contention, no standups, no alignment cost. `team-topologies.md`'s entire
  apparatus for managing inter-team communication is simply not needed.
- **AWS is already in use** with an organisation and existing accounts
  (`../feasibility/feasibility-assessment.md`), so the infrastructure skill has
  somewhere to land immediately.
- **The walking-skeleton sequencing already chosen**
  (`../scope-definition/scope-document.md`) suits solo work well: it produces
  something demonstrable early, which matters more than usual when there is no
  deadline to create momentum.

## What is unfavourable

- **Bus factor of one.** See `skill-matrix.md`. Every skill area rests on the
  same person, and there is no recipient for knowledge transfer.
- **No review.** Solo work has no second pair of eyes by default. This matters
  more than usual because the compliance core (P3) handles PHI, where an error
  is a breach rather than a bug.
- **Residual time and a large scope compound.** Neither alone would be
  remarkable. Together, with no deadline, they describe a build that can run
  indefinitely without visibly failing — which is harder to correct than a build
  that misses a date.
- **Two critical-path items still have no owner.** D-04 (DLT registration) and
  D-02 (the accuracy bake-off) are recorded in `../feasibility/raid-log.md` as
  Unassigned. With a team of one, "unassigned" resolves to the same person who is
  doing everything else.

## The options, stated plainly

Not recommendations. The scope decision belongs to whoever approved it.

1. **Proceed as approved.** Legitimate for a product experiment funded by
   services revenue with no deadline. The reduction order in
   `../scope-definition/scope-document.md` becomes the working document rather
   than a contingency, and progress is measured in shipped skeleton and Bolts
   rather than against a date.
2. **Reduce scope now, using the prepared order.** Cutting outbound reminder
   calls removes the entire India regulatory burden — DLT registration,
   1600-series numbering, consent expiry — and takes D-04 off the critical path
   entirely. Cutting the India tenant halves the compliance surface. Both are
   already sequenced in the scope document.
3. **Add capacity.** [Q6] excludes it, and this assessment does not reopen an
   answered question. Recorded only so the option set is complete.

The cheapest of these to act on is (2), because the analysis is already done.

## What needs no engineering capacity at all

Worth separating, because it is the part of the critical path that a capacity
constraint does not touch.

**D-01 — the pilot clinic conversation.** It resolves the EHR question, the
launch jurisdiction, the unnamed stakeholder, and the calendar-source-of-truth
question raised in `../scope-definition/scope-document.md`. It requires no
engineering time whatsoever, and every stage after this one produces better
output with it than without it. With capacity this constrained, doing the thing
that costs no capacity first is the clearest available move.

## Assumptions & Open Questions

- Residual availability is unquantified, so no throughput, velocity or duration
  figure is offered anywhere in this assessment. [assumption]
- [Q3] records all four skill areas as present. This assessment takes that at
  face value; depth within each area has not been evidenced and, with a team of
  one, cannot be cross-checked. [assumption]
- Whether the person available is the same person who decides scope and priority
  is not established, and it affects how quickly option (2) could be acted on.
  [assumption]
- The absence of code review on PHI-handling components is noted as unfavourable
  but no mitigation is proposed here; that belongs to practices discovery in
  Inception. [assumption]
- R-07 in `../feasibility/raid-log.md` was scored before the team answers existed
  and now understates the situation. This assessment supersedes that scoring but
  does not rewrite the RAID log. [assumption]
