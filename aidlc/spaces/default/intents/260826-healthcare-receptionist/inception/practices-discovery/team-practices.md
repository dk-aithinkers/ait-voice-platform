# Team Practices

Affirmed at practices-discovery (Inception). This project is a solo,
greenfield build with no second reader by default (`skill-matrix.md`), so the
practices below lean on machine-checked gates wherever a human reviewer would
otherwise have caught the mistake. Three specialists reviewed the lead's
draft independently; the human resolved the open trade-offs through an
eight-question interview, answered by accepting a full set of orchestrator
recommendations after review (see `evidence.md` for the exact provenance).

## Way of Working

- Trunk-based development on `main`, short-lived feature branches,
  squash-merge per Bolt. Org default; a team of one has no branch-contention
  problem to solve, and nothing in the project context argues against it.
- Construction worktrees: base `main`, merge target `main` — org default.
- Quality gates block the merge; a failed gate stops it. A gate may be
  overridden only with an in-repo written waiver carrying a justification and
  an expiry date — an unrecorded override is treated the same as approving
  over a failed sensor silently, which this team has already learned not to
  do. On this repository the required-check enforcement applies to the
  repository owner as well: a branch-protection rule the only committer can
  bypass unrecorded is not a gate, it is a suggestion.
- Because there is no second human reader, the merge gate — not a pull
  request review — is the reviewer. Pre-commit hooks (formatting, lint,
  secret scanning) run locally as a first pass; CI status checks are what
  actually stand in for the missing review, and are required on every merge
  including the owner's own.
- Whether specific disciplines beyond the gate (e.g., pairing with an AI-DLC
  agent, or its reviewer stages substituting for human review on selected
  components) are used case by case is left to Construction; nothing here
  mandates a specific substitute beyond the gate itself.

## Walking Skeleton

- Build a thin end-to-end slice first — ring, answer, converse, hang up —
  across the real vendor chain, before any feature depth. Already decided at
  scope definition (`scope-document.md`) and matches the active `feature`
  scope's `skeleton: on` declaration; not reopened at this stage.
- Per org default: Bolt 1 (the skeleton) is solo and gated, and the human
  explicitly approves it before any further Bolt runs.
- **Construction Autonomy Mode** (continue autonomously vs. gate every Bolt
  afterward) is not decided here — the org's own sequencing puts that choice
  at the ladder prompt the orchestrator fires after Bolt 1 ships, not at
  practices-discovery. It stays open until that prompt.
- A Bolt whose acceptance criterion is a manual action rather than a test
  (Bolt 1's live call being the clearest case) records that evidence
  explicitly: the call's date, the path exercised, the observed turn latency,
  and the outcome, written into the Bolt's record. Coverage and CI-green are
  not a substitute for that record — they certify a different thing.

## Testing Posture

- **Methodology**: custom
- **Ordering**: for the compliance core and any component that reads,
  writes, redacts, or routes PHI, write the failing test first and implement
  against it, gated on branch coverage and a named test corpus that must
  pass before merge; for every other component, implement each testable
  layer and then write and run that layer's tests, gated on line coverage.
  The split exists because PHI-touching code has no second reader and a
  test-after suite written by the same person on the same day tends to agree
  with a mistaken implementation; everywhere else that risk is accepted.
- **Active Test Strategy**: Standard, per `aidlc-state.md` — roughly 5-8
  tests per component, unit and integration, pyramid proportions within
  that. The `feature` scope's 80% floor and CI-before-merge are additive on
  top, not a replacement for it.
- **Coverage shape**: measured and gated **per package**, not as one
  repository-wide number, so the compliance core cannot hide behind a
  well-covered booking layer's average. The compliance core (P3) reports and
  gates on **branch** coverage, since every Hard regulatory constraint here
  (BAA gating, jurisdiction routing, consent expiry) is a branch, reachable
  by line coverage without ever being taken. The `feature` scope's 80% line
  floor applies as the minimum everywhere else. Vendor transport adapters
  (telephony/STT/TTS SDK glue) are excluded from the coverage denominator by
  an explicit, named list; anything excluded must instead carry a contract
  test or a recorded-fixture replay test — an exclusion with no replacement
  obligation is how a coverage gate becomes decorative.
- **PHI-touching standard**: tests written before implementation, branch
  coverage rather than line, and a named test corpus (including
  code-switched Hinglish samples) that must pass before merge. Coverage
  alone certifies nothing about whether a redaction routine is correct;
  100% coverage of wrong redaction is still wrong redaction, which is why
  the corpus is the binding artifact, not the cadence by itself.
- **Test data**: synthetic fixtures only in the repository and in CI. A CI
  runner and a development workstation are both outside the compliance
  boundary, and the CI vendor carries no BAA. A defined, separately
  controlled place exists for the real recordings the Indic accuracy
  bake-off needs — treated as its own PHI environment with its own access
  controls, never as part of the repository or CI. See `discovered-rules.md`
  for the binding form of this rule.
- Automated checking here means CI jobs this team writes, not something the
  framework supplies for free: the shipped `linter` and `type-check` sensors
  match TypeScript/JavaScript only and will not fire on this Python runtime
  (`.claude/sensors/aidlc-linter.md`, `.claude/sensors/aidlc-type-check.md`).
  "Automated checks" as a compensating control means Ruff, mypy/pyright, and
  the security scan set below, run in CI — not an inherited framework check.

## Deployment

- Deploy on merge to staging environments — org default.
- Production deploys are gated by an **audited machine check**, not by a
  human sign-off: tests, security/dependency/IaC scans, and a BAA-register
  check (every vendor in the live PHI path has an executed BAA on record)
  must all pass before a production deploy proceeds. With one engineer,
  "manual approval" degrades to self-approval, and self-approval is not a
  control — the machine gate is what replaces the tech-lead-plus-product-owner
  sign-off the org default assumes exists.
- A gate override is permitted only as a written, in-repo waiver carrying a
  justification and an expiry date; a silent override is never acceptable,
  consistent with the Way of Working rule above.
- AWS is already in use, with dual-region operation (US and India tenants,
  C-T1) as an approved platform decision. Per-region deployment cadence
  (whether both regions ship together, or the India tenant — currently
  blocked by an unowned DLT/1600-series dependency, D-04 — deploys on a
  separate track) is not established by this stage and is left open for
  delivery-planning.
- CI authenticates to AWS via OIDC federation to a scoped role, not
  long-lived access keys stored as CI secrets.

## Code Style

- Formatter, linter, CI platform, and the operator surface's (P9) stack and
  repository layout were flagged during review as decisions Bolt 1 cannot
  avoid, but none of them was asked or decided in this stage's interview.
  They remain open and should be resolved before or during Bolt 1 rather
  than assumed; this section does not assert an answer for them.
- Naming follows language idiom (snake_case for Python); not reopened — no
  reviewer or interview finding argued for a project override.
- Three code conventions are **binding rules**, affirmed by the human as
  such rather than left as guidance, because on a project where conventions
  and machine checks are the only review, these three carry real cost if got
  wrong:
  - **Provider boundary.** Vendor SDK imports are quarantined behind a
    provider boundary — no vendor vocabulary (vendor class or field names)
    appears in domain types, and no vendor SDK is imported outside that
    boundary. This protects the per-region, per-vendor swappability that
    C-T1 makes a Hard constraint, and converts it from a written outcome
    into something a build can fail on.
  - **Tenant context.** Tenant context is passed explicitly as a first
    parameter to every data-access function — never carried ambiently. A
    missing tenant filter here is a cross-tenant PHI disclosure, not a
    defect, and an explicit parameter turns an omission into a type error
    instead of a runtime discovery.
  - **PHI handling.** PHI-carrying values are carried in a wrapper type
    whose representation redacts, and a single logging façade refuses PHI
    values rather than merely discouraging them. This converts the most
    likely accidental breach — an f-string that interpolates a transcript
    into a log line — into a build failure.
  - See `discovered-rules.md` for the `## Mandated`/`## Forbidden` form of
    these three conventions.
