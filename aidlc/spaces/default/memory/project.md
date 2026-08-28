# Project-Level Rules

> Project-specific specialisation and corrections. Loaded after `org.md` and
> `team.md` as strict-additive guidance; contradictions with broader policy
> are rejected. Populated by practices-discovery and the self-learning loop.
>
> Use sparingly: most teams don't need a project layer. Reach for it
> only when this specific project needs stable, durable guidance beyond the
> team practice (for example, package-specific release checks or an additional
> regression suite for a legacy component).

## Way of Working

<!-- Project-specific specialisation. Example: -->
<!-- This monorepo requires package-scoped branch names and a package owner -->
<!-- review in addition to the team's normal merge policy. -->

## Walking Skeleton

<!-- Project-specific specialisation. Example: -->
<!-- The walking skeleton must exercise the legacy service adapter as well -->
<!-- as the new service boundary. -->

## Testing Posture

<!-- Project-specific specialisation. -->

## Deployment

<!-- Project-specific specialisation. -->

## Code Style

<!-- Project-specific specialisation. -->

## Tech Stack

<!-- Technology choices locked for this project. -->

## Decided

<!-- Decisions made in earlier stages that should not be re-asked. -->
<!-- Format: DECIDED: [decision] (Stage [slug], [date]) -->

## Scope Overrides

<!-- Custom scope rules for this project. -->

- ALWAYS record a scope reduction order at the moment scope is set, naming what would be cut first, in what sequence, and what each cut costs. Scope reductions are decided under pressure — a deadline, a capacity squeeze, a blocked dependency — which is the worst moment to reason clearly about which capability carries the least value and the most burden. Writing the order down while the trade-offs are still being examined turns a later cut into a decision against a prepared list rather than an improvisation, and makes the cost of each cut visible to whoever has to approve it. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:scope-definition:8012859cfe728829e79633ecc04907627a2b04657634ef39b6643a9aa88bc9f0 -->
## Forbidden

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: NEVER [behavior] (affirmed [date]) -->
<!-- Example: NEVER throw exceptions across service layer boundaries (affirmed 2026-05-17) -->

## Mandated

<!-- Populated by practices-discovery affirmation gate. -->
<!-- Format: ALWAYS [behavior] (affirmed [date]) -->
<!-- Example: ALWAYS use Result<T,E> for fallible operations in service layer (affirmed 2026-05-17) -->

- ALWAYS verify a confirmation's audit receipt before treating a questions-file answer as human-confirmed. A filled `[Answer]:` tag is not evidence of sign-off: a prior session can write one itself, and the confirmation guard will have refused to record it. Check for the matching receipt (for a consolidated summary, `SUMMARY_CONFIRMATION_RECORDED`) and treat a `DECISION_RECORDED` followed by `ERROR_LOGGED` with no receipt as an unconfirmed answer that must be reset and re-presented to the human. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:intent-capture:f464affc27c2574b7bb72a0b03ee39ae4425a568f4297c474efb92d97d7796a7 -->
- ALWAYS refuse to produce a figure the evidence cannot support, and say plainly why instead. When a stage lists a quantitative output (market size, obtainable share, cost, coverage, volume) but the inputs are missing or irreconcilable — analyst estimates spanning multiples, no denominator, no price point, no agreed target — state the gap and what would close it rather than deriving a number from assumptions. A stated gap is actionable; a manufactured figure conveys false precision to whoever plans against it. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:market-research:5805b5c5e4b6c8e76cd882776bc4f8fcde721352ef834c6fe64c7e41387c73e9 -->
- ALWAYS read gate-fired sensor results after opening the gate and before presenting the approval question. Gate-fired sensors run at gate-start, so a check made earlier in the stage proves nothing — it will report no results because none have run yet. An advisory binding lets a failed sensor through silently, so the approval can be presented on artifacts that failed their automated checks unless the results are read at the right moment. Quote any failure to the human as part of the completion summary rather than approving over it. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:feasibility:2d48404f0069a50770c03ef97668152fe6d3d6901e308d6b2ff610a0df69806b -->
- ALWAYS state why a template section does not apply rather than filling it in, when the artifact it asks for would convey structure the project does not have. A RACI matrix across two people, a mob composition for one engineer, a remediation plan with no gaps to remediate — each looks like diligence and carries no information, and a later reader cannot tell the difference between a section that was considered and dismissed and one that was completed mechanically. Naming the absence and its consequence is the finding; producing the empty shape hides it. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:team-formation:4fd938469d448a4a599aaedacf7847dd973c2c7602d4d9df9aabffeeda99126b -->
- ALWAYS describe what an artifact actually contains rather than what was intended for it. This applies in two directions. When an answer says an input exists — brand guidelines, a design system, a dataset — but it never reached you, record what was actually done and name the gap, rather than writing as though the input had been applied. And when a stage requires several elements per section, verify each section carries all of them before writing a preamble that claims they do; a summary asserting complete coverage over partly-complete content is harder for a reader to catch than the omission itself, because the summary tells them not to look. (learned 2026-08-26) <!-- cid:260826-healthcare-receptionist:rough-mockups:81b6c0270c5a59dbbfcb962059eba4e0a407cf19b5e058446bbdfa1d2f2a03c4 -->
- ALWAYS mark a superseded assessment as superseded and name what replaced it, rather than editing the original away. When later work invalidates a recorded score, estimate or judgement — a risk rated before the facts were known, a constraint that turned out not to bind — the change in understanding is itself information a later reader needs. Silently rewriting the entry produces a register that looks like it was always right and hides the moment the team learned something; leaving the original visible beside its replacement shows what changed and why. (learned 2026-08-28) <!-- cid:260826-healthcare-receptionist:approval-handoff:b7ff2c86dff38e0c55748ba2918ede513485b4587b910b09e0853132009efbff -->
- ALWAYS record corrections alongside decisions in any log that claims to describe how a phase went. A decision log listing only the clean path misrepresents the work: the guard that refused an unconfirmed answer, the sensor failure approved over, the cost understated at a gate, the artifact that claimed more than it contained — each is part of the honest history and each is what a later reader needs in order to trust the rest. Include your own errors, not only the ones the process caught. (learned 2026-08-28) <!-- cid:260826-healthcare-receptionist:approval-handoff:7acc62348bf29aec54086c76f6fb1a9e5287481e07fb2c81b3df282acd73ea9b -->
## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
