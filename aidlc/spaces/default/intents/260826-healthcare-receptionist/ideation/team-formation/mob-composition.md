# Mob Composition

## Mobbing does not apply to this project

This artifact exists because the stage declares it. Its honest content is that
the practice it describes is unavailable here, and why — not a mob plan for a
team that has one member.

`../scope-definition/intent-backlog.md` is delivered by **one engineer** [Q1], on
residual time after client delivery [Q2], with no external help [Q6].
`mob-programming-guide.md` defines the practice as "the whole team working on the
same thing, at the same time, in the same space, at the same computer", built on
a driver and one or more navigators rotating every 10–15 minutes. A single person
cannot occupy both roles, and there is no rotation to run.

The stage's own condition anticipates this: *"Skip for solo developer or small
team projects."* The stage ran rather than being skipped because its capacity
analysis was worth having — that analysis is in `team-assessment.md`, and it
turned out to be the most consequential finding in the workflow so far. The mob
planning half is what does not apply.

## What mobbing would have provided, and what replaces it

Naming the benefits explicitly, because each one is a real gap now rather than an
absence of ceremony.

| Mobbing benefit (`mob-programming-guide.md`) | Available here? | What stands in its place |
|---|---|---|
| Review happens live, during development — no async review backlog | No | Nothing by default. See `skill-matrix.md`: the compliance core handles PHI, where an error is a breach. Compensating for this is a practices-discovery question in Inception. |
| Reduces bus factor to near zero | No | Written artifacts are the only knowledge redundancy this project has. The workflow's own outputs become load-bearing rather than procedural. |
| Fastest knowledge transfer across a team | Not applicable | There is no recipient. |
| Multiple perspectives on complex design decisions | No | The AI-DLC stage structure partially substitutes: each stage brings a different domain lens — architect, compliance, platform, delivery — and the reviewer passes provide a second reading of the artifacts. This reviews the *design*, not the code. |
| Collective learning in an unfamiliar domain | Not applicable | `../feasibility/feasibility-assessment.md` records the voice domain as new ground; that learning now accrues to one person. |

The one that matters most is the first. Mobbing's live review is the benefit this
project loses with the least available substitute, and it is lost precisely where
`../feasibility/constraint-register.md` records Hard constraints (C-R1, C-R2) on
PHI handling.

## How the work is actually organised

| Aspect | Reality |
|---|---|
| Team topology (`team-topologies.md`) | None of the four types applies at n=1. The nearest description is a stream-aligned team of one, owning the full lifecycle from ideation to production — which is accurate but carries none of the properties that make stream alignment work. |
| Interaction modes | Not applicable. No inter-team boundaries exist. |
| Cognitive load | Entirely on one person, across four skill areas and two regulatory regimes. `team-topologies.md` identifies "how many services does this team own" and "how many technology stacks must be maintained" as overload indicators; both are high here relative to team size. |
| Coordination overhead | Zero. The one genuine advantage of this composition. |
| Working mode | Solo throughout [Q7], with AI assistance. |

## What replaces mob ceremony in the delivery plan

Recorded here so delivery planning does not have to rediscover it.

- **The walking skeleton** (`../scope-definition/scope-document.md`) is the
  substitute for early collective calibration. Where a mob would build shared
  understanding by working together, a solo build establishes it by proving the
  chain end to end before depth is added.
- **Small independent slices** rather than long dependent chains. Residual,
  interrupted availability [Q2][Q4] makes long chains fragile; a slice that
  completes in one sitting survives an interruption, a chain does not.
- **The approval gates** are the only external checkpoint in the process. With
  no peer review and no standups, the gates are where an outside reader sees the
  work at all. That raises their value above their usual procedural role.
- **Written artifacts as knowledge redundancy**, per `skill-matrix.md`.

## Assumptions & Open Questions

- This artifact records the absence of a practice rather than a plan for it. If
  the team grows beyond one, mob composition should be revisited rather than
  assumed to remain inapplicable. [assumption]
- Compensating for the loss of live code review — particularly on PHI-handling
  components — is unresolved and deferred to practices discovery in Inception.
  [assumption]
- Whether the AI-DLC stage and reviewer structure meaningfully substitutes for
  multiple human perspectives on design is asserted here as partial, not
  demonstrated. It reviews artifacts, not implementation. [assumption]
- No RACI matrix is included. With one engineer and one decision-maker, every
  cell resolves to one of two people, and the matrix would convey structure that
  does not exist. [assumption]
