# User Stories — Necessity Assessment

## Decision: EXECUTE

## Rationale

User stories add real value here, and the stage's own skip criteria do not apply.

The skip criteria are pure refactoring, isolated bug fixes, infrastructure-only
work, and developer tooling. This initiative is none of those: it is a
user-facing product whose primary interface is a live conversation with a member
of the public.

## Factors considered

| Factor | Finding |
|---|---|
| User-facing scope | Substantial. `../requirements-analysis/requirements.md` carries seven functional requirement groups, all of which are exercised by a person — a patient on a call, clinic staff reading outcomes, or an operator configuring an agent. |
| Multiple personas | Four distinct actors with different goals and different levels of consent to being there: a patient who did not choose to speak to software, front-desk staff, a practice owner, and an internal operator. |
| Complex business logic | Yes. The escalation branch alone (FR5) has six requirements, a staffed/unstaffed fork, and a category of utterance that must be recognised and refused rather than answered. |
| Cross-team coordination | Not applicable — one engineer. This is the one execute-criterion that does not hold, and it does not change the decision. |
| Requirements sufficiency | Requirements state what the system shall do. They do not capture *why a person is calling* or what a bad experience looks like from their side, which is where a voice product succeeds or fails. |

## Where stories will add the most value

1. **The patient's experience of the escalation path.** Requirements specify the
   mechanics; a story captures the caller's actual position — someone who wanted
   a person, got software, and needs a way out that does not feel like a dead
   end.
2. **The clinic's first week.** Whether this product is kept depends on what
   staff see after go-live, and no requirement expresses that as a goal.
3. **The failure cases.** `../../ideation/market-research/market-trends.md` found
   acceptance is contingent on the presence of a human. The stories that matter
   most are the ones where the agent cannot do the job.

## What stories will not add

Stories will not restate the compliance requirements. NFR3's redaction and
retention obligations, and the disclosure requirements in FR1, are system
properties rather than user goals — writing "As a patient, I want my data
redacted" would be a worse expression of an already-precise requirement, and this
project has a standing practice against producing structure that carries no
information.
