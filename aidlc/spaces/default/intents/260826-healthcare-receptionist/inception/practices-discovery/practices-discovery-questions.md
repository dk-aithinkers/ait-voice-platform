# Practices Discovery — Interview

**Mode:** guided

## Context

This interview follows a lead draft and three independent specialist reviews
(quality, developer, security) written blind to each other. Their findings
replaced several of the draft's original questions with better ones, so what is
asked below is not the template's list.

**Two things are already decided and are not re-asked.** The walking-skeleton
stance — build a thin end-to-end slice first — was chosen at scope definition and
matches the active scope's declaration. Trunk-based development with squash-merge
per Bolt is the org practice and nothing about a team of one changes it.

**One item below is a defect rather than a preference.** Q1 resolves a
contradiction that two reviewers found independently; it cannot pass the gate
unresolved.

---

## Q1. The audit log contradiction — how should it be resolved?

Two promoted rules cannot both hold. India's DPDP requires security logs retained
at least one year (C-R7); it also requires personal data erased once its purpose
is fulfilled (C-R8); and the compliance core specifies an immutable audit log.
All three hold only if the audit log contains no personal data.

Found independently by the developer and security reviewers, who proposed the
same resolution.

A. Audit entries reference by opaque identifier and never embed content — retention and erasure then apply to disjoint data. Must hold from Bolt 1, because retrofitting means rewriting the audit schema.
B. Two log classes with different retention policies, enforced in infrastructure — a stronger version of A that makes the separation machine-checkable.
C. Something else — describe it.
D. Not yet decided — but note this blocks the gate.
X. Other (please specify)

[Answer]: B. Two log classes with different retention policies, enforced in infrastructure — a stronger version of A that makes the separation machine-checkable.

_Recorded note: first answered `D. Not yet decided`. The human then asked the orchestrator to recommend all eight answers for review. This is the orchestrator's recommendation, the human accepted the full set of eight recommendations after reviewing them._

---

## Q2. Do quality gates block a merge, or only warn?

With no second reader, automated gates are the only reviewer this project has.
The developer review found that the framework's own linter and type-check sensors
match only TypeScript and JavaScript, so **on a Python runtime neither fires**.
Automated checking here means CI jobs you write, not something inherited.

A. Blocking — a failed gate stops the merge, no exceptions.
B. Blocking, with an in-repo written waiver carrying a justification and an expiry date.
C. Warning only — visible but never blocking, given one person and contended time.
D. Not yet decided.
X. Other (please specify)

[Answer]: B. Blocking, with an in-repo written waiver carrying a justification and an expiry date.

_Recorded note: orchestrator recommendation after the human deferred, the human accepted the full set of eight recommendations after reviewing them._

---

## Q3. Does code touching PHI get a higher bar than the rest?

The security review tiered what automation can substitute for. Secrets, dependency
CVEs and injection patterns are fully covered. PHI reaching a log sink is covered
only if PHI values are nominally distinguishable. Redaction correctness, consent
expiry, audit completeness and PHI in tracebacks are **not covered at any tooling
budget** — and those are exactly the compliance core.

A. Yes — PHI-touching code gets a stricter standard: tests written before implementation, branch coverage rather than line, and a named test corpus that must pass before it merges.
B. Yes, but lighter — a higher coverage bar only, no cadence change.
C. No — one standard everywhere; a split standard is one more thing to remember.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Yes — PHI-touching code gets a stricter standard: tests written before implementation, branch coverage rather than line, and a named test corpus that must pass before it merges.

_Recorded note: orchestrator recommendation after the human deferred, the human accepted the full set of eight recommendations after reviewing them._

---

## Q4. Is one bounded external review of the compliance core worth buying?

Not staffing — that question was answered no. This is a single review of the
compliance core by someone outside the project, plausibly bundled into the
compliance-counsel engagement already planned before real patient data.

Per the security review's tiering, this is **the only thing that covers redaction,
consent and audit correctness**. Both the security and quality reviewers raised it
unprompted.

A. Yes — bundle a technical review of the compliance core into the counsel engagement.
B. Yes, but separately and later — after the compliance core is built, before real patients.
C. No — accept the exposure, and record it as an accepted exposure rather than an unexamined default.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Yes — bundle a technical review of the compliance core into the counsel engagement.

_Recorded note: orchestrator recommendation after the human deferred, the human accepted the full set of eight recommendations after reviewing them._

---

## Q5. How should the coverage floor be shaped?

The scope's 80% floor is mandatory and cannot be weakened. Its *shape* is open,
and the quality review argued the shape is the whole question: an aggregate floor
lets the compliance core sit at 55% while booking logic carries the average, and
every Hard regulatory constraint — consent expiry, BAA gating, jurisdiction
routing — is a **branch**, reachable by line coverage without ever being taken.

A. Per-package branch coverage, with vendor transport adapters excluded but required to carry contract or recorded-fixture tests instead.
B. Per-package line coverage — simpler, still prevents the compliance core hiding behind the average.
C. Global line coverage at 80% — the plain reading of the org default.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Per-package branch coverage, with vendor transport adapters excluded but required to carry contract or recorded-fixture tests instead.

_Recorded note: orchestrator recommendation, the human accepted the full set of eight recommendations after reviewing them._

---

## Q6. What is the test-data rule?

The quality review's sharpest finding: PHI must never leave the compliance
boundary, and a CI runner, a fixtures directory and a development laptop are all
outside it. The CI vendor has no BAA. This is concrete rather than hypothetical —
the Indic accuracy bake-off is specified on **real 8kHz call recordings**.

A. Synthetic fixtures only. Real recordings stay inside the compliance boundary, never enter the repository, and never reach CI.
B. As A, plus a defined place real recordings may live for the bake-off, treated as a PHI environment with its own controls.
C. No rule yet — decide when the bake-off is scheduled.
D. Not yet decided.
X. Other (please specify)

[Answer]: B. Synthetic fixtures only, plus a defined place real recordings may live for the bake-off, treated as a PHI environment with its own controls.

_Recorded note: orchestrator recommendation, the human accepted the full set of eight recommendations after reviewing them._

---

## Q7. Production deploys — what replaces sign-off that cannot exist?

The org practice gates production on tech-lead plus product-owner approval. With
one person that is self-approval, which the security review noted is not a
control.

A. An audited machine gate — deploy proceeds only when tests, scans and the BAA-register check pass; a waiver must be written in-repo with a justification and an expiry.
B. Keep manual self-approval, honestly labelled as a checkpoint rather than a control.
C. Both — machine gate plus a deliberate human pause before production.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. An audited machine gate — deploy proceeds only when tests, scans and the BAA-register check pass; a waiver must be written in-repo with a justification and an expiry.

_Recorded note: orchestrator recommendation, the human accepted the full set of eight recommendations after reviewing them._

---

## Q8. Which code conventions should be binding rules rather than preferences?

The developer review argued that with no second reader, conventions plus machine
checks *are* the review, and named three that carry real cost if got wrong.
Select all that should be binding.

A. Vendor SDK imports quarantined under a provider boundary, with no vendor vocabulary in domain types — protects the per-region swappability that C-T1 makes a Hard constraint.
B. Tenant context passed explicitly as a first parameter rather than ambient — a missing tenant filter is a cross-tenant PHI disclosure, and an explicit parameter makes omission a type error.
C. PHI carried in a wrapper type whose representation redacts, with a logging façade that refuses it — converts the most likely breach into a build failure.
D. None of these as binding rules; keep them as guidance.
X. Other (please specify)

[Answer]: A, B and C — all three are binding rules: provider-boundary quarantine, explicit tenant context, and a PHI wrapper type refused by the logging façade.

_Recorded note: orchestrator recommendation, the human accepted the full set of eight recommendations after reviewing them._

---

## Consolidated Summary Confirmation

Summary of all answers:

- **Audit log:** two log classes with different retention policies, enforced in infrastructure. Audit entries reference by opaque identifier and never embed content. Holds from Bolt 1. [Q1]
- **Quality gates:** blocking, with an in-repo written waiver carrying a justification and an expiry date. [Q2]
- **PHI-touching code gets a stricter standard:** tests before implementation, branch coverage, and a named test corpus that must pass before merge. This makes the methodology field `custom`. [Q3]
- **One bounded external technical review** of the compliance core, bundled into the compliance-counsel engagement already planned. [Q4]
- **Coverage:** per-package branch coverage; vendor transport adapters may be excluded but must carry contract or recorded-fixture tests instead. [Q5]
- **Test data:** synthetic fixtures only in the repository and CI, plus a defined PHI environment where real recordings may live for the Indic bake-off. [Q6]
- **Production deploys:** an audited machine gate; self-approval is not treated as a control. [Q7]
- **Three binding code conventions:** provider-boundary quarantine, explicit tenant context, and a PHI wrapper type refused by the logging façade. [Q8]

**Provenance, which matters for how these should be read.** Q1 through Q4 were
first answered `D. Not yet decided`. The human then asked the orchestrator to
recommend answers to all eight for review, the orchestrator did so with its
reasoning shown, and the human accepted the full set. These are therefore
human-accepted decisions that originated as orchestrator recommendations rather
than as the human's own unprompted answers. `evidence.md` records the same.

**Process deviation, recorded rather than hidden.** This stage declares
`summary_confirmation: required`, which means this confirmation should have been
taken *before* the lead integrated the artifacts. It was not — the four artifacts
were written first, and the engine refused the approval gate until this section
existed. The artifacts are unchanged by this confirmation; what changed is that
the ordering the protocol requires was not followed, and the gate caught it.

**Where the three reviewers disagreed, and what was done.** The quality reviewer
argued that test cadence is decisive on PHI code — a same-day test written by the
implementer agrees with the implementation including where it is wrong. The
security reviewer argued the test corpus matters far more than cadence — full
coverage of wrong redaction is still wrong redaction. Both were adopted, because
they address different failure modes rather than competing.

**Maintained dissent carried to the gate.** The security reviewer's tool matrix —
specific linting, secret-scanning, dependency and supply-chain tooling — was never
put to the human, so it promotes into team memory as a silence. That reviewer
objected to exactly that outcome. The objection stands unresolved and is recorded
here rather than settled.

Does this all look correct before the affirmation gate?

- Looks correct
- Request changes

[Answer]: Looks correct
