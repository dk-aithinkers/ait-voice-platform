**Collaborator:** aidlc-devsecops-agent

## Contribution

Remit: lint/format rules, SAST/DAST, secret and dependency scanning, supply-chain
controls. Reviewed `team-practices.md`, `discovered-rules.md`, `evidence.md` and
`practices-discovery-timestamp.md` against `memory/org.md`, `memory/project.md`,
`../../ideation/feasibility/constraint-register.md`,
`../../ideation/feasibility/raid-log.md`,
`../../ideation/team-formation/skill-matrix.md`, and `docs/vendors.md`.

### 1. The largest gap: the draft names no security gate anywhere

`team-practices.md`'s Way of Working section correctly identifies that this
project has no second reader and that compensating for that is the human's call.
But the draft then never says what a compensating automated control would
consist of. Its Code Style section stops at "formatter/linter"; Testing Posture
names coverage and CI without naming a single security check; Deployment names
an approval without naming what the approval is checking.

That is the substantive hole. On this project the security pipeline *is* the
compensating control under discussion in Way of Working — it is not a separate
topic that can be deferred to `ci-pipeline` in Construction, because the
interview is where the human affirms whether those gates are binding, and
`ci-pipeline` will build whatever this stage affirmed. A silence here promotes to
`memory/team.md` as a silence.

`team.md` has only the five replaceable sections, so this content cannot get its
own heading. Section mapping for integration is given in §6 below.

### 2. What automated tooling actually substitutes for a human reviewer, and what does not

This is the question the interview turns on, and it deserves a straight answer
rather than a general endorsement of "automated checks". Three tiers:

**Tier A — genuinely substitutes.** These catch the whole of their class
deterministically, and a human reviewer adds little over them:

- *Committed secrets.* Gitleaks (pre-commit + CI history scan) catches
  credentials, API keys and tokens as well as any reviewer, and better than a
  tired one. With ~8 vendor SDKs in the chain (`docs/vendors.md` §Recommended
  stack), key material is the most-handled sensitive artifact after PHI itself.
- *Known-vulnerable dependencies.* `pip-audit` in CI plus Dependabot or Renovate
  on a weekly cadence. A human reviewer cannot do this at all — it is a database
  lookup, not a judgement.
- *Infrastructure misconfiguration.* This is the highest-value control on this
  project and the draft does not mention it. Checkov or cdk-nag with the HIPAA /
  NIST rule pack machine-checks most of what P3 (compliance core) is actually
  made of: region pinning, KMS encryption at rest, TLS in transit, CloudWatch
  log group retention, IAM least-privilege, S3 public-access blocks, VPC flow
  logs. Region isolation and encryption are IaC-expressible, therefore
  machine-checkable, therefore they do not need a reviewer. Roughly half of P3's
  compliance surface can be moved from "hope the solo engineer got it right" to
  "the build fails".
- *Common injection and crypto-misuse patterns.* Bandit rules — reachable
  without adding a tool, see §3.

**Tier B — substitutes only if the code is written to make it possible.** Custom
Semgrep rules can catch PHI reaching a log, metric, exception or third-party
sink — but only if PHI-carrying values are nominally distinguishable. A rule can
match `log.*(...transcript...)` or a taint flow out of a `Phi[str]` / `Redacted`
wrapper type; it cannot match `log.info(f"{x}")` where `x` happens to hold a
transcript. So the control does not exist unless a naming/typing convention
exists to anchor it, which turns a code-style choice into a security control.
This is the one place where the Code Style section carries real weight on this
project, and it is worth affirming deliberately rather than as a stylistic
default.

**Tier C — does not substitute, at any tooling budget.** Nothing off-the-shelf
and nothing custom catches these; a human has to look, or a test corpus has to
exist:

- Whether a redaction routine is *correct* for Hinglish code-switched speech.
  C-T5 (Hard) forecloses AWS-native redaction on the India path, so this is
  hand-written code doing the single highest-consequence job in the product, and
  no scanner has an opinion about its output quality.
- Whether the consent model's 7-day expiry (C-R9, Hard) is computed correctly,
  and against which clock.
- Whether the audit log is complete — a missing write is invisible to every
  scanner ever built.
- Whether an exception traceback carrying transcript fragments is shipped to an
  observability vendor. `docs/vendors.md` is explicit that the BAA chain includes
  logging and observability as separate links; an error path is the most likely
  place PHI escapes the boundary, and error paths are the least-reviewed code.
- Whether a vendor holds an executed BAA before its SDK is added. See §4.

**The honest summary for the interview: automated gates fully cover the
credential, dependency and infrastructure classes, partially cover the
PHI-in-logs class if the code is shaped for it, and do not cover redaction
correctness, consent correctness or audit completeness at all.** Those last
three are exactly P3, and they are exactly where `skill-matrix.md` says an error
is a breach rather than a defect. The interview should not be allowed to
conclude that tooling closes the review gap; it closes about two-thirds of it,
and the remaining third needs either a bounded external review or a named test
corpus, or an explicit decision to accept the exposure.

### 3. Concrete tool set (Python, AWS, greenfield, solo, contended capacity)

Chosen with C-O1 (Hard — contended capacity) in mind: every item below is
near-zero ongoing maintenance. Where two tools would do the same job, one is
picked.

| Control | Tool | Where it runs | Gate |
|---|---|---|---|
| Format + lint | **Ruff** (`ruff format` + `ruff check`) | pre-commit + CI | Block |
| SAST (Python) | Ruff rule sets `S` (bandit), `T20` (no `print`), `G` (logging-format), `B`, `ASYNC` | same run as lint | Block on `S` |
| PHI-sink rules | **Semgrep OSS**, ~5 hand-written rules | CI | Block |
| Secrets | **Gitleaks** | pre-commit + CI (full history) | Block |
| Dependencies | **pip-audit** + Dependabot/Renovate weekly | CI + scheduled | Block on Critical/High |
| Lockfile | `uv lock` / pip-compile with hashes, committed | — | Block on drift |
| SBOM | **Syft** or Trivy, artifact per build | CI | Advisory |
| IaC | **Checkov** or **cdk-nag** with HIPAA/NIST pack | CI, pre-synth | Block on High |
| Containers | **Trivy** (only if LiveKit or the runtime is self-hosted) | CI on image build | Block on Critical |
| DAST | **OWASP ZAP** baseline against the P9 operator API | staging, after P9 exists | Advisory first |

Notes the lead should carry:

- **Ruff replaces the org default's "Black + Ruff" pairing.** `team-practices.md`
  suggests both; Ruff's formatter is Black-compatible, so this is one tool, one
  config file, one CI step instead of two. More importantly, selecting Ruff's `S`
  rules puts SAST inside the lint gate at zero marginal cost — which is the
  difference between a solo engineer having SAST and not having it.
- **`T20` and `G` are not style rules here.** Banning bare `print` and enforcing
  structured logging calls are what make the Semgrep PHI-sink rules tractable —
  you cannot write a taint rule against arbitrary `print(f"...")`.
- **DAST is genuinely low-priority and the draft is right not to have rushed it.**
  A voice pipeline's externally-reachable surface is small; the real web attack
  surface is P9 (operator surface), which does not exist yet. ZAP belongs after
  P9, not before P1. Penetration testing is a pre-pilot item, not a pre-code
  item — the January 2025 HIPAA NPRM proposes annual pen testing and 6-monthly
  vulnerability scans (`docs/vendors.md` §US — HIPAA), and that rule is not
  final, but that document's own advice is to build to the proposed standard.
- **CI identity is the one setup decision that is painful to retrofit:** OIDC
  federation to a scoped AWS role, not long-lived access keys stored as CI
  secrets. Free at day zero. This is worth stating to the human as a
  recommendation rather than offering as an open preference.

### 4. Supply-chain: the BAA chain is a supply-chain control and no scanner ships it

`docs/vendors.md` establishes the rule that matters most here: *a BAA does not
flow down to subcontractors*, and the chain to cover is telephony + STT + LLM +
TTS + orchestration + hosting + logging + observability, individually. "One gap
breaks the chain."

That makes `pip install <vendor-sdk>` a compliance event, not a dependency event.
No dependency scanner has this concept. `discovered-rules.md`'s C-R1 rule
("ALWAYS verify an executed BAA exists...") is correct and well-sourced, but it
has **no enforcement point** — it is an instruction to remember something, given
to a team of one with no reviewer, which is the weakest possible form of a Hard
constraint.

Proposed enforcement, cheap enough to actually build:

1. A checked-in `compliance/baa-register.yaml` listing every vendor in the PHI
   path, its BAA status (`executed` / `pending` / `none`), the date, and the
   gate/tier it required (`docs/vendors.md` §Vendor BAA availability already has
   the raw data for the first version).
2. A checked-in egress allowlist of hostnames the PHI path may talk to.
3. A CI check that fails when a new direct dependency, or a new outbound host in
   config, is absent from the register — cross-referenced against D-05 in
   `raid-log.md` (executed BAAs across the full vendor chain, currently
   `Unassigned`).

That converts a Hard constraint from a memory aid into a gate, which is the whole
point of this stage for a team with no second reader. It is also the only control
in this contribution that does not exist off the shelf, so it should be scoped
deliberately rather than assumed.

Two smaller supply-chain points: pin dependencies with a hash-verified lockfile
(the voice-SDK ecosystem is young and typosquat-prone), and treat the SBOM as
doing double duty — it is also the "written asset inventory" the HIPAA NPRM
proposes.

### 5. A contradiction in `discovered-rules.md` that must be resolved, not carried

Two promoted Hard rules are in unresolved tension as written:

- C-R7: "ALWAYS retain security logs for a minimum of one year..."
- C-R8: "ALWAYS erase personal data once its purpose is fulfilled... no
  indefinite retention of call recordings or transcripts by default."

Add P3's "immutable audit log" (`../../ideation/scope-definition/intent-backlog.md`)
and the three are jointly unsatisfiable *if the audit log contains PHI* — you
cannot both hold it immutably for a year and erase it on purpose fulfilment.
Neither rule as drafted references the other, so an implementer following either
one in isolation violates the other.

The inception phase guardrails require this be surfaced and resolved rather than
carried forward. It resolves cleanly, and the resolution is a design-forcing
constraint worth stating as its own rule:

> ALWAYS keep the immutable audit log and the security log free of PHI —
> reference call and caller records by opaque identifier only — so that
> minimum-retention (C-R7) and erasure-on-purpose-fulfilment (C-R8) can both be
> satisfied on the same system.

This also makes the separation machine-checkable: two log classes with different
sinks, different retention policies in IaC (checkable by Checkov), and a Semgrep
rule that no PHI-typed value reaches the audit sink. It is a good example of the
Tier B pattern in §2 — a design decision that converts a human-judgement control
into an automated one.

### 6. Where this content goes in `team-practices.md`

Since `team.md` carries only the five sections, integration should be:

- **Way of Working** — pre-commit hooks are mandatory locally; CI status checks
  are required to merge, and required-check enforcement applies to the repository
  owner too. On a solo repository this last clause is load-bearing: a branch
  protection rule the only committer can bypass is not a gate, it is a
  suggestion. Also: the merge gate, not the PR, is the reviewer.
- **Testing Posture** — the security scan set (§3) runs in the same CI job as
  the tests and blocks the merge on the same terms; plus the P3 redaction/consent
  test corpus (see §7).
- **Deployment** — the deploy gate blocks on any Critical dependency or image
  finding and any High IaC finding; waivers are time-boxed, written in-repo with
  a justification and an expiry, and never applied silently. CI authenticates to
  AWS via OIDC.
- **Code Style** — Ruff (format + lint) with `S`/`T20`/`G`/`B`/`ASYNC` selected;
  the PHI naming/typing convention from §2 Tier B; secrets from AWS Secrets
  Manager or SSM Parameter Store, never from a committed file.

### 7. On the lead's [INTERVIEW] flags — my read

**"Compensating control for absent code review" — right to flag, but it is three
questions, not one.** Asked as one, it will get one vague answer. Split it:

(a) *Do the automated gates block the merge, or warn?* (Recommend: block. A
warning on a solo project is a log line nobody reads.)
(b) *Does PHI-touching code get a higher bar than the rest?* (This is the real
question — the answer determines whether P3 gets the Semgrep rules, the test
corpus and the BAA gate, or whether everything gets a uniform middle setting.)
(c) *Is one bounded external human review of the compliance core worth buying
before real patients?* The draft does not offer this and it should. It is not an
ongoing retainer — it is a single review of P3, and D-06 in `raid-log.md`
(compliance counsel review, owner Deepak) is already a planned external
engagement, so there is a natural pairing: counsel reviews the policy, a security
engineer reviews the implementation, once, before the pilot. Per §2 Tier C this
is the only thing that covers redaction correctness, consent correctness and
audit completeness. If the answer is no, that should be recorded as an accepted
exposure rather than left as an unexamined default.

**"Stricter testing methodology for compliance code" — right to flag, but the
methodology is not the useful axis.** Whether P3 is written test-first or
test-after matters much less than whether a specific artifact exists: a named
redaction and consent test corpus, including Hinglish code-switched samples,
which must pass before P3 merges. Line coverage — the `feature` scope's 80% floor
— says nothing about whether a redaction regex removes an identifier; 100%
coverage of wrong redaction is still wrong redaction. Ask for the corpus, not the
cadence. (Corpus samples must be synthetic — see the proposed rule below.)

**"CI platform and coverage tooling" — right to flag, but not as a bare
preference.** GitHub Actions is the pragmatic default here because Dependabot and
secret scanning are native and free, which removes two tools from §3. Present it
with the OIDC recommendation attached rather than as an open menu.

**"Naming conventions" — agree it is low-stakes, with one exception.** Fold the
PHI-value naming/typing convention (§2 Tier B) into the same question, because
it is the anchor the whole PHI-sink rule set depends on.

**"What manual production-approval means with no tech-lead/product-owner pair" —
right to flag, and the draft is right not to silently drop the safeguard, but it
should say the uncomfortable part.** For a team of one, "manual approval"
degrades to self-approval, which is not a control at all. What *is* a control is
a machine-checked pre-deploy gate whose waiver is audited: the deploy is blocked
by findings, and overriding leaves a written record with a justification and an
expiry. Offer that as the substitute rather than asking who signs off.

### 8. Sequencing: what must be in CI before the first real call

The draft does not distinguish thresholds, and they are far apart in cost.

**Before the first line of application code** (about an hour, and hostile to
retrofit): pre-commit with Gitleaks + Ruff; CI running Ruff (`S` rules included),
pip-audit and the test suite; required status checks with owner enforcement;
hash-pinned lockfile; secrets in Secrets Manager. All of this is cheaper now than
at any later point, and Gitleaks especially — a secret caught pre-commit is
prevented, a secret caught later is a rotation plus a history rewrite.

**Before P1 (walking skeleton) dials a live carrier leg, even with synthetic
audio**: IaC scanning with the HIPAA pack, TLS enforced end to end, OIDC CI
identity, the first version of the BAA register (§4) — because P1 crosses the
real vendor chain by design (`scope-document.md` sequencing), and the first time
that chain is wired is the cheapest time to check it.

**Before the first call carrying real PHI** — the compliance threshold, and the
one that matters:

- the two-log-class separation from §5, with retention enforced in IaC;
- Semgrep PHI-sink rules passing, and the code shaped so they can be written;
- the redaction/consent test corpus green, Hinglish samples included;
- an audit-log completeness test (a call produces the expected audit events);
- the BAA register complete for every vendor in the live path — D-05 closed, not
  merely tracked;
- SBOM produced and retained;
- whatever review substitute §7(c) resolved to, actually performed.

**Can wait, and should**: DAST (needs P9), penetration testing (pre-pilot, not
pre-code), container scanning (only if self-hosting materialises), SOC 2
tooling — `constraint-register.md` records SOC 2 as a procurement expectation and
not a legal requirement, so it stays out until an enterprise buyer asks.

PCI DSS remains out of scope per the scope decision; nothing above reintroduces
it.

### 9. Candidate rules for `discovered-rules.md`

Offered as candidates only — per the stage, a rule is promoted on a human-stated
hard constraint, so these belong in the interview before they belong in the file.
Each is an operational corollary of an already-promoted Hard constraint rather
than a new policy:

- **NEVER commit real call audio, transcripts, or caller identifiers to the
  repository, test fixtures, or CI logs — test data is synthetic without
  exception.** (Corollary of C-R2. CI logs are a real and commonly-missed PHI
  egress path, and a public or vendor-hosted CI log is outside the compliance
  boundary. This is the one addition I would argue for even if the human declines
  everything else.)
- **ALWAYS record a vendor in the BAA register before adding its SDK, endpoint,
  or credential to the PHI path.** (Gives C-R1 an enforcement point — §4.)
- **ALWAYS keep the immutable audit log and security logs free of PHI, referencing
  records by opaque identifier only.** (Resolves the C-R7/C-R8 contradiction — §5.)
- **NEVER ship an error, traceback, or telemetry payload from the PHI path to a
  vendor without a BAA.** (Corollary of C-R1 + C-R2; observability is a named link
  in the chain in `docs/vendors.md`, and error paths are where this leaks.)

### 10. Evidence I inspected

- `team-practices.md`, `discovered-rules.md`, `evidence.md`,
  `practices-discovery-timestamp.md` — the lead draft, read in full.
- `aidlc/spaces/default/memory/org.md` (Code Style, Testing Posture, Deployment),
  `memory/project.md` (eight learned rules; none duplicate the candidates above),
  `memory/team.md` (empty template, confirmed).
- `../../ideation/feasibility/constraint-register.md` — all 22; C-T1, C-T2, C-T5,
  C-O1, C-O6, C-R1, C-R2, C-R5–C-R9 bear on this remit. Confirmed independently
  that all 13 Hard constraints are promoted in the draft and that C-O1 is the
  omission, correctly reasoned.
- `../../ideation/feasibility/raid-log.md` — R-03 (both regimes, accepted), R-04
  (compliance architecture frozen before counsel), D-05 (BAA chain, unowned),
  D-06 (counsel review).
- `../../ideation/team-formation/skill-matrix.md` — no review by default; the
  deferral of the compensating-control question to this stage.
- `../../ideation/scope-definition/intent-backlog.md` — P3's four components.
- `docs/vendors.md` — the BAA chain (no flow-down to subcontractors; eight links
  named), AWS streaming redaction limited to English variants and Spanish and not
  combinable with multi-language ID, the January 2025 NPRM's proposed controls,
  DPDP one-year log retention and 72-hour Board reporting, and the vendor BAA
  availability table.
- Repository state independently verified: no `.github/workflows/`, no
  `pyproject.toml`, no `.pre-commit-config.yaml`, no lint or scanner
  configuration anywhere. Every control above is a decision made now, and none
  contradicts an existing one.

### 11. Uncertainty I am carrying

- The hosting shape is not settled (LiveKit Cloud vs. self-hosted per
  `docs/vendors.md`), so container scanning is conditional rather than assumed.
- The CI platform is unchosen, so the Dependabot/secret-scanning saving in §3 is
  contingent on GitHub; on another platform those become two more tools to add.
- I have not costed the BAA register gate (§4) in engineering hours. It is the
  only bespoke control proposed and the only one whose cost the human should
  weigh explicitly against C-O1.

## Positions

- AGREE: The greenfield finding and "there is no code evidence" — independently
  verified; no CI, lint, scanner or lockfile configuration exists anywhere in the
  repository.
- AGREE: Refusing to invent a compensating-control rule for absent code review
  and flagging it for the interview — that trade-off is the human's, and asserting
  a default would have hidden a decision that three upstream artifacts left open.
- AGREE: Promoting only Hard-severity constraints, with the Firm exclusions
  explained rather than silently dropped — the "Not included, and why" section is
  the right shape.
- AGREE: Treating the walking skeleton as already decided rather than reopening
  it, and DAST's absence from the near-term picture — the operator surface it
  would target does not exist yet.
- OBJECT: `team-practices.md` contains no security gate of any kind — no SAST, no
  secret scanning, no dependency or IaC scanning, no SBOM, no pre-commit. On a
  project whose Way of Working section is explicitly about compensating for the
  absence of a reviewer, that pipeline *is* the compensating control, and a
  silence here promotes into `memory/team.md` as a silence.
- OBJECT: `discovered-rules.md`'s C-R7 (retain security logs ≥ 1 year) and C-R8
  (erase personal data on purpose fulfilment) are jointly unsatisfiable alongside
  P3's immutable audit log unless that log is PHI-free, and neither rule
  references the other — the inception guardrails forbid carrying an unresolved
  contradiction forward.
- OBJECT: The C-R1 BAA rule has no enforcement point — it asks a team with no
  second reader to remember a Hard constraint at exactly the moment (`pip install`)
  when nothing is checking.
- OBJECT: The "Black + Ruff" suggestion is redundant, and the redundancy costs
  something real: Ruff alone does format, lint and Python SAST in one gate, which
  is the difference between a solo engineer having SAST and skipping it.
- OBJECT: The Deployment [INTERVIEW] framing asks *who* performs the production
  approval without saying that on a team of one the answer is self-approval and
  self-approval is not a control; the substitute worth offering is an audited,
  non-silently-waivable machine gate.
- OBJECT: The Testing Posture flag asks about methodology (test-first vs.
  test-after) for compliance code, where the decisive artifact is a redaction and
  consent test corpus with Hinglish code-switched samples — the `feature` scope's
  80% line-coverage floor certifies nothing about whether redaction is correct.
