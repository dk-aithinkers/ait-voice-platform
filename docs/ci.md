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

## Branch protection — required, and not yet on

CI reports status; it does not block anything by itself. On GitHub:

**Settings → Branches → Add rule** for `main`:
- Require status checks to pass: `python`, `compliance`, `security`, `web`
- Require branches to be up to date before merging
- **Do not allow bypassing the above settings** ← the important one

`team.md` is explicit that this applies to the repository owner:

> On this repository the required-check enforcement applies to the repository
> owner as well: a branch-protection rule the only committer can bypass
> unrecorded is not a gate, it is a suggestion.

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
