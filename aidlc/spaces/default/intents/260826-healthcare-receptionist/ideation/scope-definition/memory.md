<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations

- 2026-08-26T12:45:52Z — read the answer combination as a coherent strategy (build the platform properly, defer only what cannot be specified) rather than as an inconsistency, but recorded its shape explicitly: wide on infrastructure, narrow on the differentiator
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations

- 2026-08-26T12:45:52Z — used MoSCoW rather than WSJF or RICE for the backlog despite the stage naming all three; WSJF needs a cost of delay and RICE needs reach and effort, none of which exist here, so scoring would have produced arithmetic that looks rigorous and means nothing
- 2026-08-26T12:45:52Z — added a non-development section to the backlog for D-01, D-02, D-03 and D-04; they are not proto-Units and no engineering builds them, but the MVP does not ship without them and a backlog omitting them would misrepresent the work
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs

- 2026-08-26T12:45:52Z — ranked P12 (Indic code-switching) as Should rather than Must even though it is the stated differentiator, because R-01 leaves the achievable quality unevidenced; committing it as Must would assert a capability nobody has measured
- 2026-08-26T12:45:52Z — recorded a reduction order in the scope document rather than leaving it implicit, so a later scope cut is a decision against a prepared list instead of an improvisation under pressure
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions

- 2026-08-26T12:45:52Z — whose calendar is the appointment system of record: with no EHR integration but booking and reminders in scope, a clinic already running a practice-management system will not move its calendar, so the MVP either serves clinics without one or creates double-entry; only D-01 can answer it
- 2026-08-26T12:45:52Z — D-04 (DLT registration, 1600-series numbering) became critical path through the combination of outbound calling and an India tenant, and it is still unowned in the RAID log
- 2026-08-26T12:45:52Z — no forcing function and a large build: no deadline, no budget, contended capacity, maximum scope on every axis but one; the walking skeleton is the only mitigation currently in the plan
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
