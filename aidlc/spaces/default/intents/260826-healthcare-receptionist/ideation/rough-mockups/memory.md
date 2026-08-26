<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations

- 2026-08-26T14:44:18Z — treated this as neither a UI nor a non-UI initiative: real screen work is in scope but the primary interface is a telephone conversation, so conversation design was framed as the main surface and the human was asked to confirm or correct that before anything was drawn
- 2026-08-26T14:44:18Z — resolved the Q1/Q2/Q3 ambiguity (full screen treatment requested, but screen set and audience both undecided) by treating the approved scope document as the authority where the answers were silent, rather than re-asking a question the human had already declined to settle
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations

- 2026-08-26T14:44:18Z — pre-filled the questions file mode as guided for the second time in this workflow; the confirmation guard refused the answer, which was correct, and the mode was then asked properly
- 2026-08-26T14:44:18Z — omitted a computed hours-saved figure from the clinic view despite it being one of the three success metrics, because no baseline exists and displaying it would be the manufactured figure this project already forbids
- 2026-08-26T14:44:18Z — drew no per-component empty, loading or error states and no mobile layouts; both belong to mid-fidelity work and drawing them here would assert precision the stage does not have
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs

- 2026-08-26T14:44:18Z — recorded the wireframes as brand-neutral in fact despite the human answering that brand guidelines exist, because none were supplied; claiming a brand had been applied would have been false and the gap is actionable before refined mockups
- 2026-08-26T14:44:18Z — designed the clinic view to serve both candidate audiences from one screen rather than picking one, since Q3 is blocked on the pilot conversation; marked provisional rather than presented as settled
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions

- 2026-08-26T14:44:18Z — how the agent determines whether a human is available to receive a transfer is undecided, and the entire escalation branch depends on it; scope includes 24/7 answering so for most hours the answer is no
- 2026-08-26T14:44:18Z — the callback promise commits clinic staff time that no clinic has agreed to, because no pilot clinic exists; it should not be spoken to a patient before that agreement
- 2026-08-26T14:44:18Z — the voice channel excludes deaf and hard-of-hearing callers and those the recogniser handles poorly, and Q5 deferred the non-voice fallback; for a healthcare product the consequence is a patient who cannot reach their clinic
- 2026-08-26T14:44:18Z — whether call audio is exposed in the clinic view is unresolved and is an NFR-design decision, since raw voice is a listed PHI identifier
- 2026-08-26T14:44:18Z — language selection at call start is undesigned: whether the caller chooses, the agent detects, or it is configured per clinic is not decided, and Indic code-switching is the stated differentiator
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
