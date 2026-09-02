# The merge gate

`team.md`, affirmed at practices-discovery:

> Because there is no second human reader, the merge gate — not a pull request
> review — is the reviewer… CI status checks are what actually stand in for the
> missing review, and are required on every merge including the owner's own.

This document is what that means in practice.

## What runs, and why each one is here

| Job | Check | What it stands in for |
|---|---|---|
| **python** | `ruff check` | the security rule sets (S, T20, G, B, ASYNC) already configured |
| | `ruff format --check` | a consistent diff, so review sees changes not reflow |
| | `mypy` (strict on `src`) | the compensating control `team.md` names for having no second reader |
| | `pytest` | 715 tests |
| | `scripts/check_coverage.py` | **per-package** floors — see below |
| **compliance** | `scripts/check_baa.py` | C-R1: the register is well formed |
| **security** | `gitleaks` | a key committed by accident — irreversible once pushed |
| | `pip-audit` | a vulnerable Python dependency |
| **infra** | `cfn-lint` | a template that will not deploy |
| | `scripts/check_infra.py` | Object Lock, retention, encryption — see `docs/deploying.md` |
| **web** | `npm audit` | the frontend holds PHI on screen |
| | `eslint`, `vitest`, `tsc && vite build` | the React surface |

Nothing deploys. Nothing needs a credential — the suite runs against the
offline providers, so a fork's pull request builds safely.

## Per-package coverage, not a repository total

`pytest --cov-fail-under` gates one number for the whole repository, which is
exactly what `team.md` rejects:

> measured and gated **per package**, not as one repository-wide number, so the
> compliance core cannot hide behind a well-covered booking layer's average

So `scripts/check_coverage.py` applies a floor per package, and the compliance
core gates on **branch** coverage rather than line. That is not pedantry: every
Hard regulatory constraint here is a branch — BAA gating, jurisdiction routing,
consent expiry — and line coverage reaches a branch without ever taking it.

That distinction earned its keep on the gate's first run. `core/audit.py` was
at **89% line and 73.5% branch**: the path that reads the last hash off disk
when appending to an existing log had never been exercised, so nothing proved
the audit chain survives a restart. An audit log whose chain silently restarts
on every deploy is not tamper-evident. Four tests now cover it.

### Exclusions carry a replacement obligation

`team.md` permits excluding vendor transport from the denominator "by an
explicit, named list", but only where a contract or recorded-fixture test
stands in — "an exclusion with no replacement obligation is how a coverage gate
becomes decorative". So `EXCLUSIONS` names both halves, and the gate fails if a
named replacement test goes missing.

## The BAA gate has two modes

`check_baa.py` (default) checks the register is **well formed** — every vendor
declared, and anything marked `baa = true` naming where the executed agreement
lives. It passes today with nothing signed, and still catches the failure worth
catching: a flag flipped to unblock a deploy with no evidence recorded.

`check_baa.py --require-signed` checks every vendor in the live PHI path has an
executed BAA. **It fails today, and that failure is the control working** — it
belongs on the production deploy, not on the merge gate. This is D-05, external
contracting rather than engineering.

## Branch protection — on

`main` is protected, and the rule applies to the repository owner too.
`team.md` is explicit about why:

> On this repository the required-check enforcement applies to the repository
> owner as well: a branch-protection rule the only committer can bypass
> unrecorded is not a gate, it is a suggestion.

What is set:

| Setting | Value |
|---|---|
| Required status checks | the four below, all four required |
| Require branches to be up to date | yes — a branch that passed against a stale `main` was not tested against what it merges into |
| Include administrators | **yes** — this is the one that makes it a gate |
| Required PR approvals | none, deliberately — see below |
| Force pushes / branch deletion | both refused |

### The required check names are the job `name:`, not the job id

This is worth stating because getting it wrong fails in a confusing direction.
The workflow gives every job a `name:`, and that display name is what GitHub
registers as the check run — so the required contexts are:

```
Python — lint, types, tests, coverage
Compliance — BAA register
Security — secrets and dependencies
Infra — synthesise and check compliance
Web — lint, types, tests, build
```

Not `python`, `compliance`, `security`, `web`. Requiring the job ids would name
four checks that never report, and GitHub blocks a merge that is waiting on a
check it has not seen — so every merge would hang forever on a rule that looks
correctly configured. Rename a job in `ci.yml` and this rule must be updated in
the same change, or the same thing happens.

### No required approvals, deliberately

`team.md` puts the reviewer role on the merge gate precisely because there is
no second human. GitHub will not let you approve your own pull request, so a
required-approval rule on a one-person repository is not a stricter control —
it is an unsatisfiable one. The status checks are the review.

### Reading it back

```bash
gh api repos/dk-aithinkers/ait-voice-platform/branches/main/protection
```

## Committing the AI-DLC workspace tree

`CLAUDE.md` says to commit the `aidlc/` tree, and the hook appends to the audit
shard continuously — so it is dirty most of the time. Protection applies to it
like anything else, which means a file the hook wrote by itself now needs a
branch, a pull request and four CI jobs.

Done per session that is enough friction that the tree stops being committed,
and an audit trail living on one laptop is not an audit trail. So batch it:

```bash
uv run python scripts/commit_workspace.py --dry-run   # what would go
uv run python scripts/commit_workspace.py             # branch, PR, wait, squash-merge
uv run python scripts/commit_workspace.py --no-merge  # stop at the PR
```

It refuses to run if **anything outside `aidlc/`** is dirty. That guard is the
whole reason the script is allowed to merge without a human: without it, a tool
that auto-merges once CI is green is a way for source changes to reach `main`
inside a commit labelled "workspace state" — the unreviewed merge the rule
exists to prevent. `tests/test_workspace_batch.py` tests the guard for the same
reason the gates have their own tests.

The deliberate trade-off: the audit trail lags real time by however long you go
between runs. That is the cost of batching, and it is cheaper than the trail not
existing. Nothing stops you running it more often.

### Why not `paths-ignore`

Skipping CI for `aidlc/**` would remove the friction entirely, and was
considered. It also means a path committed more often than any other stops being
checked at all — and since `aidlc/` sits in the same repository as the source, a
rule keyed on paths is one mistaken glob away from being a hole in the gate.
`team.md` is pointed about controls that only look like controls.

## Local first pass

```bash
uv run pre-commit install
```

Ruff, gitleaks, and file hygiene on every commit. This is convenience — a hook
that `--no-verify` skips is not a control. CI is the gate.

## Overriding a failed gate

`team.md` permits it only as "an in-repo written waiver carrying a
justification and an expiry date". There is no mechanism for a silent override,
deliberately.
