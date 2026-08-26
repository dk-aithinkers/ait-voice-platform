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
## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
