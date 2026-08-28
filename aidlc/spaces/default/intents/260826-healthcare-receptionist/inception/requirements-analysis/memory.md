<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations

- 2026-08-28T13:28:46Z — applied the practice learned at practices discovery proactively: presented all seven questions with a recommended answer and its reasoning rather than asking cold, after four consecutive deferrals in the previous stage showed that dense technical questions produce deferrals rather than decisions
- 2026-08-28T13:28:46Z — treated the deferred language decision as producing an architectural requirement rather than a gap: FR7.3 makes the language set configuration so the pilot answer can arrive without rework
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations

- 2026-08-28T13:28:46Z — left the three success-metric targets as explicit TBD markers with full measurement definitions rather than inventing provisional numbers; the project practice forbids figures the evidence cannot support, and a definition is what acceptance criteria actually need
- 2026-08-28T13:28:46Z — stated no throughput figure in NFR5 despite capacity being a normal NFR, because no volume forecast exists anywhere in the workflow
- 2026-08-28T13:28:46Z — expressed retention as obligations rather than durations (a short window, the clinic's record-keeping period) because the real figures need counsel and a clinic policy that do not exist
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs

- 2026-08-28T13:28:46Z — recommended 99.5 percent availability against the reflex 99.9, because a higher target implies on-call response and redundancy one engineer on residual time cannot provide, and committing to it would be a promise the team assessment says cannot be kept
- 2026-08-28T13:28:46Z — paired that target with a degraded-mode obligation (NFR2.2) so an outage routes to the clinic's existing path rather than a dead line; without it the availability number would concede exactly the problem the product exists to solve
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions

- 2026-08-28T13:28:46Z — baselining the success metrics needs two weeks of observation at a pilot clinic before go-live, which is a scheduling dependency on D-01 that should be planned rather than discovered afterwards
- 2026-08-28T13:28:46Z — FR4.4 assumes a machine-readable record of regulatory registration status; no such record exists and it must be designed
- 2026-08-28T13:28:46Z — NFR6.2 states the non-voice fallback obligation without prescribing a mechanism, because R-10 records the choice as undecided
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
