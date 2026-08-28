**Collaborator:** aidlc-quality-agent

## Contribution

Remit: testing posture, coverage tooling, CI quality gates, test/code patterns,
and the gaps the human interview must resolve. Reviewed blind against the lead
draft, `memory/org.md`, `constraint-register.md`, `team-assessment.md`,
`skill-matrix.md`, and `intent-backlog.md`.

The draft's judgement calls are sound — it declines to invent a review
substitute, and it flags methodology rather than asserting it. My contribution
is almost entirely additive: the Testing Posture section is the thinnest of the
five relative to what this project actually needs, and four specific things are
missing from it that a solo PHI build cannot afford to leave unstated.

---

### 1. The `feature` scope's 80% floor is stated but not shaped, and its shape is the whole question

`org.md` fixes the floor at 80% line coverage and forbids weakening it. It does
not fix *what it is measured over*, and on this project that is where all the
risk sits. Three decisions the draft leaves open, each of which the interview
should settle:

**(a) Global or per-module.** A single global 80% lets the compliance core (P3)
sit at 55% while a well-covered booking layer carries the average. Aggregate
coverage is precisely the metric that hides concentrated risk, and the risk here
is concentrated by design — P3 is the one proto-Unit where an error is a breach
rather than a defect. Recommend the floor be enforced **per package**, with a
raised floor on the compliance boundary. Raising and partitioning a floor is
strict-additive and therefore admissible; only weakening it is forbidden.

**(b) Line or branch.** Line coverage is the weakest available signal, and this
codebase's risk lives in conditionals, not statements. Every Hard regulatory
constraint is a branch:

| Constraint | The branch it creates |
|---|---|
| C-R1 | vendor has an executed BAA / does not |
| C-R2 | value is inside the compliance boundary / is being logged outside it |
| C-R5 | reminder call content is transactional / contains marketing |
| C-R6 | outbound India call is on a 1600-series DLT-registered number / is not |
| C-R7 / C-R8 | log is inside the 1-year retention floor / personal data is past purpose |
| C-R9 | consent is inside 7 days / has expired |
| C-T1 / C-T5 | region is US / is India (and therefore which redaction path applies) |

80% line coverage is reachable on this code without ever taking the India
branch. Recommend **branch coverage is the reported and gated metric on the
compliance core**, with line coverage retained as the 80% floor elsewhere to
satisfy `org.md` literally. Jurisdiction (US / India) should be a
parametrization axis across the compliance suite, not a handful of separate test
cases — otherwise the second region gets covered by whichever tests someone
remembered to duplicate.

**(c) What is excluded from the denominator, and what replaces it.** A large
fraction of P1 and P2 is I/O glue against telephony, STT and TTS SDKs. That code
cannot be meaningfully unit-tested, and if it sits in the denominator exactly one
of two things happens: the engineer writes mock-echo tests that assert nothing in
order to reach 80%, or the gate is permanently red and gets switched off. Both
outcomes are worse than an honest exclusion. Recommend the practice name an
explicit exclusion list (vendor adapter transport layers, generated code,
migrations) **paired with a standing rule that anything excluded from coverage
must instead carry a contract test or a recorded-fixture replay test**. Exclusion
without a replacement obligation is how a coverage gate becomes decorative.

Suggested Testing Posture bullets the lead can lift directly:

- Coverage is measured with `pytest-cov` and enforced per package via
  `--cov-fail-under`, not as a single repository-wide number.
- The compliance core (P3) reports and gates on **branch** coverage; the 80%
  line floor from the `feature` scope applies everywhere as the minimum.
- Vendor transport adapters are excluded from the coverage denominator by an
  explicit, named list; anything excluded must carry a contract or
  recorded-fixture test instead.

### 2. Coverage answers the wrong question for a build with no reviewer — name the control that answers the right one

Coverage asks "was this line executed?" A reviewer asks "does this do what it is
supposed to do?" Nothing in the draft currently asks the second question, and
that is the exact gap left by the absent review. Two cheap controls close part of
it and both are affordable *because* they are narrowly scoped:

- **Mutation testing on the compliance core only** (`mutmut` or `cosmic-ray`).
  A surviving mutant in redaction, consent expiry or audit-write logic is a test
  that executes the code and asserts nothing meaningful about it. This is the
  single closest mechanical analogue to "a second reader checked your
  assertions," and full-codebase mutation testing would be unaffordable on
  residual time while one module is not.
- **Property-based tests (Hypothesis) on redaction, consent and retention.**
  The failure mode for redaction is "an input shape nobody thought of got
  through," which is exactly what example-based tests miss *and* what a human
  reviewer also misses. The invariants are easy to state and hard to satisfy by
  accident: for all inputs, the redacted output contains no substring of any
  identifier present in the input; for all consent timestamps, validity is false
  beyond 7 days (C-R9); for all records past purpose, erasure is reachable
  (C-R8); for all security-log writes, retention is at least one year (C-R7).

### 3. Missing entirely: a test-data practice, on a project whose natural test corpus *is* PHI

This is my most serious finding, and it is absent from all four draft artifacts.

C-R2 was correctly promoted as a product rule ("never logged outside the
compliance boundary"). Its testing corollary was not promoted anywhere, and the
corollary is where PHI most plausibly leaks in a solo build. **A CI runner is
outside the compliance boundary. So is a laptop's `pytest` output, a fixture
file, a git history, and a debugging print.** The vendor whose CI runners execute
the suite has no BAA (C-R1 does not flow down, and nobody has considered the CI
vendor as being in the chain at all).

D-04 makes this concrete rather than hypothetical: the Indic accuracy bake-off
(D-02) is specified on **real 8kHz recordings**. That work item, as written,
invites exactly the behaviour the rule must forbid — pulling real caller audio
onto a workstation to debug the code-switching path, and then leaving it in a
fixtures directory because it was the only realistic sample available. C-T5 makes
this worse: because AWS-native redaction cannot cover the code-switched India
path, the India redaction implementation is the piece most likely to be developed
against real audio and least likely to be covered by a vendor's own guarantees.

Recommend the following be added to `discovered-rules.md`. It derives from an
already-promoted Hard constraint (C-R2) rather than inventing a new one, so it
clears the "human-stated hard constraint" bar the same way the rest of that file
does:

> **`## Forbidden`** — NEVER place real call audio, transcripts, or caller
> identity in test fixtures, in the repository, in CI, or on a development
> workstation. Test data for every PHI-touching component is synthetic. Real
> recordings used for evaluation (D-02) stay inside the compliance boundary,
> under a BAA, and never enter the repository or a CI runner. (source: C-R2,
> Hard, US, `../feasibility/constraint-register.md` — a CI runner and a
> development workstation are both outside the compliance boundary)

And to Testing Posture: name the synthetic-fixture generator (Faker plus a small
set of hand-authored code-switched transcript samples), and state that the D-02
bake-off runs inside the boundary against data that never lands in the repo.

### 4. CI is not a preference question here — it is a precondition for Bolt 1's merge

The draft lists "which coverage tool and CI platform" alongside naming
conventions as an interview item. They are not the same class of question. The
`feature` scope floor mandates **CI execution before merge**; there is no CI; the
walking skeleton (P1) is gated and merges to `main`. Either CI exists before that
first merge, or the very first merge of the project violates the practice being
affirmed in this stage. That makes a minimal CI pipeline a Bolt-0 deliverable,
and the interview should be told so rather than being asked to express a
preference.

The minimum gate that satisfies the floor and is cheap enough for residual time:
`ruff` + `black --check` + `pytest` with `--cov-fail-under` + a dependency/CVE
scan + a secret scan. One ordering correction for the interview: **ask where the
repository is hosted before asking which CI platform.** Nothing upstream
establishes that this repo is on GitHub, and "GitHub Actions" is only the
low-friction answer if it is.

One thing the practice must state honestly: a solo engineer is always able to
merge past a red gate, and pre-commit hooks are bypassable with `--no-verify`.
Pretending the gate is unbypassable is worse than admitting it, because it makes
the exception invisible. Recommend the practice read: **a red gate blocks the
merge; overriding it is permitted and must be recorded in the Bolt's record with
the reason.** This is the same failure mode already recorded in `project.md` — an
advisory check approved over silently — one layer further down.

### 5. `test-after` is the wrong way round for the compliance core, and `custom` is the field value this is heading for

I agree with the lead that the methodology should not be asserted. I object to
which way the draft leans. It presents `test-after` as the standing answer with
"stricter for compliance code" as a flagged option; given that no review exists
at all, the presentation should be inverted — stricter on P3 as the suggested
answer, with `test-after` as the deviation to justify.

The argument is narrow and specific, not a general preference for TDD. On a solo
build, a test written *before* the compliance implementation is the only artifact
that states what the code is supposed to do independently of the code that might
be wrong. Written after, it is authored by the same person, on the same day, from
the same reading of the same regulation — it will agree with the implementation
including where the implementation is mistaken. That is precisely the error class
a reviewer catches and coverage does not. This does not apply to booking logic or
the operator surface, where test-after is fine and cheaper.

The stage definition requires two structured fields and names `custom` for mixed
cadences. Given the above, the value this is likely to land on is:

- `- **Methodology**: custom`
- `- **Ordering**: For the compliance core (P3) and any component that reads,
  writes, redacts, or routes PHI, write the failing test first and implement
  against it; for every other component, implement each testable layer and then
  write and run that layer's tests.`

Recommend the draft be shaped so `custom` is the low-friction outcome of the
interview rather than something the human has to construct unprompted.

### 6. Missing: what a Bolt's quality evidence is when its acceptance criterion is a phone call

P1 is "ring, answer, converse, hang up" across the real vendor chain. There is no
unit test for that; the acceptance signal is a human placing a call. Nothing in
the draft says what evidence that produces. Without a stated practice, "80%
coverage, CI green" will be reported as Bolt 1 complete while the criterion the
Bolt actually existed to prove — that the chain holds together — was checked once
and left unrecorded.

`project.md` already carries a rule about describing what an artifact actually
contains rather than what was intended for it. This is that rule applied to test
evidence. Recommend Testing Posture state: **where a Bolt's acceptance is a
manual call, the Bolt record carries the call's date, the path exercised, the
observed turn latency, and the outcome — and that record is the acceptance
evidence, not the coverage number.**

Related, and worth one line in the same section: tests that place real calls cost
money and are non-deterministic. They belong outside the merge gate, run
deliberately, with recorded audio frames replayed into the adapter as the
CI-safe substitute. This is also what makes the coverage exclusion in §1(c)
defensible.

### 7. Two smaller omissions

- **The active `Test Strategy` is never named.** `aidlc-state.md` records
  `Test Strategy: Standard` and `Depth: Standard`; `org.md` states the active
  strategy "applies in every scope and determines test volume/types" and that
  scope floors are additive on top of it. The draft's Testing Posture does not
  mention it, so Code Generation will resolve volume from a field nobody
  affirmed. Recommend one bullet: *Standard strategy — roughly 5-8 tests per
  component, unit and integration, pyramid proportions within that; the
  `feature` scope's 80% floor and CI-before-merge are additive on top.*
- **Latency has no owner yet.** C-T3 accepts a cascaded pipeline knowing it
  raises the latency floor, and turn latency is the defining quality attribute of
  a voice agent. This is `nfr-requirements`' stage to own, not this one — but the
  skeleton is where a latency-budget harness is cheapest to build, and it will be
  built or not built during Bolt 1 depending on whether anyone says so now. Worth
  one forward-looking line rather than a practice to affirm.

---

### What the interview should actually ask

The draft's code-review question ("what kind of compensating control, and at what
cost") is the right question flagged in the wrong shape. Asked openly, of a
person on residual time, about an unfamiliar trade-off, it will be answered with
whatever is cheapest to agree to. `project.md` already carries the principle that
applies here — a decision made against a prepared list beats one improvised under
pressure. Recommend it be put as a costed menu with a marked default:

**Q — Compensating controls for PHI code with no second reader.** Select all
that apply; the first three are the recommended set.

| # | Control | What it catches that the others do not | Solo cost |
|---|---|---|---|
| 1 | Make PHI a distinct type whose `__repr__`/`__str__` returns a redaction marker, and fail the build when a PHI-typed value reaches a logging or serialization sink | Turns the single most likely breach — an accidental f-string or a debug log of a transcript — from a review-catchable error into a build failure | Low, one-off; highest value per hour of anything on this list |
| 2 | Property-based tests on redaction, consent expiry and retention | Input shapes nobody enumerated; the reviewer misses these too | Low-moderate |
| 3 | Mutation testing scoped to the compliance core | Tests that execute the code and assert nothing real | Moderate, and only because it is scoped to one module |
| 4 | A written, versioned self-review checklist derived from C-R1, C-R2, C-R5, C-R7–C-R9, executed against the diff at least a day later | Intent errors — the one class nothing mechanical catches. Weakest control here, and the only one in that column | Near zero |
| 5 | An AI reviewer pass on PHI-touching diffs | A fourth net. Genuinely useful; **not** a substitute for the human review C-R1/C-R2 would ordinarily receive, and should not be recorded as one | Low |
| 6 | A single external review of P3 only, bundled into the counsel engagement already planned before real patient data | An independent reader, once, on the highest-stakes module | Unknown; may be near-free relative to what is already planned |

On option 6: `[Q6]` excluded external help and `team-assessment.md` correctly
declines to reopen it. But `[Q6]` excluded help with *delivery capacity*, and a
one-off review of one module is not delivery capacity. Feasibility `[Q8]` already
commits to engaging counsel before real patient data touches the system. Whether
a code review of the compliance boundary rides along with that engagement is a
different question from "should someone else help build this," and it has not
been asked. It is worth asking; it is not worth assuming either way.

Whichever subset is chosen, the practice should state the **residual exposure
that remains**, in writing, as accepted — consistent with `project.md`'s rules on
marking superseded assessments and logging corrections alongside decisions.

Four further interview questions, in priority order:

1. **Coverage shape** — per-package or global; branch or line on the compliance
   core; what is excluded from the denominator. (§1)
2. **Where is the repository hosted**, then which CI platform — and confirm that
   a minimal CI gate is understood as a precondition for Bolt 1's merge, not a
   later convenience. (§4)
3. **Test data** — confirm synthetic-only fixtures and that D-02's real
   recordings stay inside the compliance boundary. Present the proposed
   `## Forbidden` rule for affirmation. (§3)
4. **Methodology** — test-first on PHI-touching components, test-after
   elsewhere, recorded as `custom`; or blanket `test-after` with a stated reason.
   (§5)

## Positions

- AGREE: Declining to invent a compensating control for absent code review and
  routing it to the interview — the trade-off is genuinely the human's, and
  inventing one would have papered over the project's largest exposure.
- AGREE: Flagging methodology-per-component rather than asserting a stricter
  posture for the compliance core; the lead was right not to decide it.
- AGREE: Promoting only Hard-severity constraints to `discovered-rules.md`, and
  explaining under "Not included, and why" what was left in the register.
- AGREE: Treating the walking skeleton as already decided upstream rather than
  re-opening it, and flagging only Construction Autonomy Mode as genuinely open.
- AGREE: Recording plainly that there is no code evidence and that everything
  rests on `org.md` defaults plus ideation context.
- OBJECT: Testing Posture states the 80% floor without shaping it — global vs
  per-package, line vs branch, and the coverage denominator are all unaddressed,
  and on this codebase an unshaped aggregate floor is the metric most likely to
  hide the concentrated risk in P3. (§1)
- OBJECT: No test-data practice exists in any of the four artifacts, on a project
  whose natural test corpus is PHI and whose D-02 bake-off is specified on real
  8kHz recordings. C-R2 was promoted as a product rule but its testing corollary
  — a CI runner and a workstation are outside the compliance boundary — is stated
  nowhere. This is the most likely PHI leak path in a solo build. (§3)
- OBJECT: CI platform is listed as an interview preference alongside naming
  conventions; the `feature` scope's CI-before-merge floor makes a minimal
  pipeline a precondition for Bolt 1's gated merge, not a later choice. The
  question also asks which CI platform before establishing where the repo is
  hosted. (§4)
- OBJECT: The methodology question leans the wrong way. With no reviewer at all,
  the suggested answer for PHI-touching code should be test-first with
  `test-after` as the deviation to justify — and the resulting field value is
  `custom`, not `test-after`. (§5)
- OBJECT: Nothing states what quality evidence a Bolt produces when its
  acceptance criterion is a manual phone call (P1), so "coverage met, CI green"
  will stand in for a criterion that was never mechanically checked. (§6)
- OBJECT: The active `Test Strategy: Standard` from `aidlc-state.md` is never
  named in Testing Posture, leaving Code Generation to resolve test volume from
  an unaffirmed field. (§7)
- OBJECT: The quality gate is defined as "CI execution before merge" with no
  statement of what a red gate blocks or how an override is recorded. A solo
  engineer can always merge past it; an unrecorded override is the same failure
  already learned in `project.md` about approving over advisory sensor
  results. (§4)
