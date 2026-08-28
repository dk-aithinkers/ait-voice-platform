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

- NEVER adopt a telephony provider that cannot support bidirectional media (affirmed 2026-08-28)
streaming over WebSocket — this rules out classic IVR/TwiML-only providers (affirmed 2026-08-28)
for the voice pipeline. (source: C-T2, Hard, (affirmed 2026-08-28)
`../feasibility/constraint-register.md`, citing `docs/vendors.md`: (affirmed 2026-08-28)
forecloses Knowlarity, Kaleyra, MyOperator among others) (affirmed 2026-08-28)
- NEVER rely on AWS Transcribe's native redaction for Indian-language, (affirmed 2026-08-28)
code-switched calls — automated PII redaction and code-switching cannot be (affirmed 2026-08-28)
combined on that AWS path. (source: C-T5, Hard, (affirmed 2026-08-28)
`../feasibility/constraint-register.md`; Transcribe streaming redaction (affirmed 2026-08-28)
covers only English variants and Spanish) (affirmed 2026-08-28)
- NEVER include marketing or upsell content in outbound reminder calls — it (affirmed 2026-08-28)
would void the TCPA healthcare exemption the reminder agent depends on. (affirmed 2026-08-28)
(source: C-R5, Hard, US, `../feasibility/constraint-register.md`) (affirmed 2026-08-28)
- NEVER plan India-tenant registration (DLT, 1600-series numbering) as (affirmed 2026-08-28)
outsourceable — no provider performs it on a customer's behalf; it must be (affirmed 2026-08-28)
carried in-house. (source: C-O6, Hard, (affirmed 2026-08-28)
- NEVER place real call audio, transcripts, or caller identity in test (affirmed 2026-08-28)
fixtures, in the repository, or on a development workstation; test data (affirmed 2026-08-28)
for every PHI-touching component is synthetic. A CI runner and a (affirmed 2026-08-28)
development workstation are both outside the compliance boundary, and the (affirmed 2026-08-28)
CI vendor carries no BAA. (source: Q6-A of the practices-discovery (affirmed 2026-08-28)
interview, a testing corollary of C-R2) (affirmed 2026-08-28)
- NEVER use the repository or CI as the storage location for the real (affirmed 2026-08-28)
recordings the Indic accuracy bake-off (D-02) needs; a separately defined (affirmed 2026-08-28)
place holds them, treated as its own PHI environment with its own access (affirmed 2026-08-28)
controls. (source: Q6-B of the practices-discovery interview, a testing (affirmed 2026-08-28)
corollary of C-R2 and C-R1) (affirmed 2026-08-28)
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
- ALWAYS stop asking and offer a reasoned proposal when a human defers several questions in a row. Repeated deferral usually signals that the questions are too dense, too numerous, or too far from what the person has read to be adjudicated cold — not that the answers do not matter. Continuing to ask produces more deferrals and a record of decisions nobody made. Converting the remaining questions into one reviewable proposal, with the reasoning shown and each item still individually changeable, turns many cold decisions into a single informed one. Record clearly which answers originated as recommendations rather than as the human's own, so a later reader can weigh them accordingly. (learned 2026-08-28) <!-- cid:260826-healthcare-receptionist:practices-discovery:efb4e956f6e41170bf965bcb783d96e8e17aebb398623cc749f41e1c41e7c965 -->
- ALWAYS retain security logs for a minimum of one year and support breach (affirmed 2026-08-28)
reporting to India's Data Protection Board within 72 hours, for the India (affirmed 2026-08-28)
tenant — **applied only to logs that reference records by opaque (affirmed 2026-08-28)
identifier and event type; see the audit/security log rule below for how (affirmed 2026-08-28)
this is kept satisfiable alongside the erasure rule that follows it.** (affirmed 2026-08-28)
(source: C-R7, Hard, India, `../feasibility/constraint-register.md`) (affirmed 2026-08-28)
- ALWAYS erase personal data once its purpose is fulfilled, for the India (affirmed 2026-08-28)
tenant — no indefinite retention of call recordings or transcripts by (affirmed 2026-08-28)
default — **applied to the content store, which is kept separate from the (affirmed 2026-08-28)
security/audit log covered by the rule above so the two obligations apply (affirmed 2026-08-28)
to disjoint data.** (source: C-R8, Hard, India, (affirmed 2026-08-28)
`../feasibility/constraint-register.md`) (affirmed 2026-08-28)
- ALWAYS keep the immutable audit log and every security log free of PHI: (affirmed 2026-08-28)
entries reference the call, caller, and event by opaque identifier and (affirmed 2026-08-28)
type only, and never embed content. This is the resolution the human (affirmed 2026-08-28)
affirmed for the contradiction two independent reviewers found between the (affirmed 2026-08-28)
rule above (retain security logs at least one year) and the rule above it (affirmed 2026-08-28)
(erase personal data once its purpose is fulfilled) — both hold only if (affirmed 2026-08-28)
the retained log contains no personal data. The two log classes carry (affirmed 2026-08-28)
different retention policies and are enforced as separate infrastructure (affirmed 2026-08-28)
(separate sinks, separate IaC-defined retention), not merely as a written (affirmed 2026-08-28)
convention, so the separation is machine-checkable rather than (affirmed 2026-08-28)
memorized. Must hold from Bolt 1: retrofitting this after the audit (affirmed 2026-08-28)
schema has real entries means rewriting it under load. (source: Q1 of the (affirmed 2026-08-28)
practices-discovery interview, resolving C-R7 × C-R8 × (affirmed 2026-08-28)
`../scope-definition/intent-backlog.md`'s immutable-audit-log requirement (affirmed 2026-08-28)
for P3) (affirmed 2026-08-28)
- ALWAYS verify an executed BAA exists for a vendor before it is given access (affirmed 2026-08-28)
to call audio, transcripts, or caller identity — a BAA does not flow down to (affirmed 2026-08-28)
subcontractors, so each vendor in the chain needs its own. (source: C-R1, (affirmed 2026-08-28)
Hard, US, `../feasibility/constraint-register.md`) (affirmed 2026-08-28)
- ALWAYS treat call audio and transcripts as PHI, handled only within the (affirmed 2026-08-28)
compliance boundary — never as non-sensitive data, and never logged outside (affirmed 2026-08-28)
that boundary. (source: C-R2, Hard, US, (affirmed 2026-08-28)
`../feasibility/constraint-register.md`; voice is itself a listed (affirmed 2026-08-28)
identifier) (affirmed 2026-08-28)
- ALWAYS use 1600-series numbering with completed DLT registration for (affirmed 2026-08-28)
outbound commercial calls placed to India numbers. (source: C-R6, Hard, (affirmed 2026-08-28)
India, `../feasibility/constraint-register.md`; penalties escalate to ₹1M (affirmed 2026-08-28)
per instance with a two-year cross-operator blacklist) (affirmed 2026-08-28)
- ALWAYS expire commercial-call consent after 7 days, for the India tenant — (affirmed 2026-08-28)
the consent model must carry expiry rather than treating consent as (affirmed 2026-08-28)
durable. (source: C-R9, Hard, India, (affirmed 2026-08-28)
- ALWAYS build multi-tenancy in-house rather than adopting a managed voice (affirmed 2026-08-28)
platform's native tenancy. (source: C-T4, Hard, (affirmed 2026-08-28)
`../feasibility/constraint-register.md`, citing (affirmed 2026-08-28)
`../market-research/build-vs-buy.md`: no managed voice platform offers (affirmed 2026-08-28)
native multi-tenancy) (affirmed 2026-08-28)
- ALWAYS keep every speech and telephony component replaceable per deployment (affirmed 2026-08-28)
region — no design may hard-code a vendor or use a single global pipeline (affirmed 2026-08-28)
configuration. (source: C-T1, Hard, `../feasibility/constraint-register.md`, (affirmed 2026-08-28)
citing `docs/vendors.md`: no vendor covers US healthcare and India (affirmed 2026-08-28)
adequately) (affirmed 2026-08-28)
- ALWAYS quarantine vendor SDK imports behind a per-capability provider (affirmed 2026-08-28)
boundary, with no vendor vocabulary in domain types. Affirmed by the human (affirmed 2026-08-28)
as a binding code convention, not guidance, because it is the enforcement (affirmed 2026-08-28)
point the constraint above (C-T1) otherwise lacks — a written outcome with (affirmed 2026-08-28)
no build-time check is the weakest form a Hard constraint can take on a (affirmed 2026-08-28)
team with no second reader. (source: Q8-A of the practices-discovery (affirmed 2026-08-28)
interview, enforcing C-T1) (affirmed 2026-08-28)
- ALWAYS pass tenant context explicitly as the first parameter of every (affirmed 2026-08-28)
data-access function — never ambiently. A missing tenant filter is a (affirmed 2026-08-28)
cross-tenant PHI disclosure, not a defect, given multi-tenancy from day one (affirmed 2026-08-28)
(C-T4) and PHI in scope (C-R2); an explicit parameter turns the omission (affirmed 2026-08-28)
into a type error rather than a runtime discovery. (source: Q8-B of the (affirmed 2026-08-28)
practices-discovery interview, enforcing C-T4 × C-R2) (affirmed 2026-08-28)
- ALWAYS carry PHI-touching values in a wrapper type whose representation (affirmed 2026-08-28)
redacts, and route all logging through a single façade that refuses PHI (affirmed 2026-08-28)
values rather than discouraging them. Affirmed as binding because "never (affirmed 2026-08-28)
logged outside the compliance boundary" (C-R2) is otherwise unenforceable (affirmed 2026-08-28)
— this converts the single most likely accidental breach into a build (affirmed 2026-08-28)
failure. (source: Q8-C of the practices-discovery interview, enforcing (affirmed 2026-08-28)
C-R2) (affirmed 2026-08-28)
- ALWAYS write tests before implementation for PHI-touching code (any (affirmed 2026-08-28)
component that reads, writes, redacts, or routes PHI), gated on branch (affirmed 2026-08-28)
coverage and a named test corpus — including code-switched samples — that (affirmed 2026-08-28)
must pass before merge. (source: Q3 of the practices-discovery interview) (affirmed 2026-08-28)
- ALWAYS block a merge on a failed quality gate; an override requires an (affirmed 2026-08-28)
in-repo written waiver carrying a justification and an expiry date. (source: (affirmed 2026-08-28)
Q2 of the practices-discovery interview) (affirmed 2026-08-28)
- ALWAYS gate a production deploy on an audited machine check — tests, (affirmed 2026-08-28)
security/dependency/IaC scans, and a BAA-register check for every vendor in (affirmed 2026-08-28)
the live PHI path — passing; self-approval by the sole engineer is not (affirmed 2026-08-28)
treated as a control, and an override requires an in-repo written waiver (affirmed 2026-08-28)
carrying a justification and an expiry date. (source: Q7 of the (affirmed 2026-08-28)
practices-discovery interview) (affirmed 2026-08-28)
- ALWAYS include one bounded external technical review of the compliance core (affirmed 2026-08-28)
(P3), bundled into the compliance-counsel engagement already planned before (affirmed 2026-08-28)
real patient data touches the system. This is the only control identified (affirmed 2026-08-28)
during review that covers redaction correctness, consent correctness, and (affirmed 2026-08-28)
audit completeness — the three failure classes no automated scanner has an (affirmed 2026-08-28)
opinion about. (source: Q4 of the practices-discovery interview) (affirmed 2026-08-28)
- ALWAYS set a non-functional target the team can actually meet rather than the conventional figure for the category. Availability, latency, recovery-time and coverage targets have reflex answers — 99.9 percent, four nines, sub-second — that get adopted because they sound serious rather than because anyone checked whether the staffing, redundancy and on-call response they imply exist. A target nobody can hold is worse than a lower one stated honestly: it is a commitment the team will quietly miss, and it hides the real operating posture from whoever plans against it. Check the target against the capacity actually recorded for the project, and where a lower target is chosen, pair it with an explicit obligation that bounds what happens in the shortfall. (learned 2026-08-28) <!-- cid:260826-healthcare-receptionist:requirements-analysis:333b689cc70caac46c5b66ec1b95f4ce24d21b22de9bdb670c3b713a272721a0 -->
## Corrections

<!-- Project-specific corrections from human feedback. -->
<!-- Format: NEVER/ALWAYS [behavior] (learned [date]) -->
