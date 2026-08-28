**Collaborator:** aidlc-developer-agent

## Contribution

Remit: naming, layer boundaries, error handling, file organization, code-style
conventions. Reviewed `team-practices.md`, `discovered-rules.md` and
`evidence.md` against `../../ideation/feasibility/constraint-register.md`,
`../../ideation/team-formation/skill-matrix.md`,
`../../ideation/scope-definition/intent-backlog.md` and
`../../ideation/market-research/build-vs-buy.md`.

### 1. The framing problem: Code Style is not the residual section on this project

The draft's `## Code Style` is three bullets — defer to a config that does not
exist, suggest Black + Ruff, and confirm snake_case. On a normal project that
would be proportionate. Here it is not, for a reason the draft itself
establishes elsewhere and then does not carry into this section.

`skill-matrix.md` records no code review by default, bus factor one, and
written artifacts as the only knowledge redundancy. Strip that down: **on this
project, conventions and machine checks are the review.** There is no second
reader who will catch a vendor SDK import that leaked into the domain layer, a
repository method that forgot its tenant filter, or an f-string that
interpolated a transcript into a log line. A convention that a linter enforces
is a reviewer that never gets tired at 1am; a convention written in prose and
nowhere else is a hope.

The three conventions that actually cost money on this system are absent from
the draft: **where the provider boundary sits, how tenant context is threaded,
and how PHI-carrying values are named and handled.** Each is derived from a Hard
constraint the lead has already promoted to `discovered-rules.md`. Each is
brutally expensive to retrofit — the same argument `BRIEF.md` makes about the
compliance core, applied to the code that implements it. Sections 2-6 below
propose them as replacement text.

### 2. Where the provider abstraction boundary sits (C-T1)

C-T1 is promoted as "no design may hard-code a vendor or use a single global
pipeline configuration." That states an outcome, not a check — it cannot fail a
build, so it cannot substitute for the missing reviewer. Three conventions make
it enforceable:

**One package per capability, vendor imports quarantined.** `telephony/`,
`stt/`, `tts/`, `llm/`, each with a `base.py` declaring the Protocol and
`providers/<vendor>.py` holding the implementation. **Vendor SDK imports appear
only under a `providers/` directory.** That is a mechanical rule: an
`import-linter` layer contract, or Ruff's `flake8-tidy-imports` banned-api list,
fails CI if `twilio`, `livekit.plugins.*`, an Exotel or Rumik SDK, or a boto3
Transcribe client is imported from anywhere else. It converts a Hard constraint
into a build failure, which is what "hard" ought to mean when nobody is
reviewing.

**Vendor vocabulary must not cross the boundary either.** The domain type is
`CallSession`, not `TwilioCall`; `AudioFrame`, not `LiveKitAudioFrame`. An
interface can be import-clean and still be vendor-shaped, and when that happens
the abstraction has already failed while the import check still passes. Vendor
nouns in a domain signature are the early-warning signal, and they are visible
in a diff without any tooling.

**Region selection is data, not branching.** A per-region provider registry
resolved once at session construction — never `if region == "IN":` inside the
pipeline. The grep is `== "IN"` / `== "US"` outside the registry module. This one
matters most: conditionals scattered through the pipeline are precisely how the
"single global pipeline configuration" C-T1 forbids re-forms by accretion, one
harmless-looking branch at a time.

**Draw the boundary per capability, never per region.** The tempting solo-dev
shortcut is `us/` and `in/` top-level packages. It duplicates the pipeline and
destroys the shared core the business case rests on — `build-vs-buy.md` rejects
per-region orchestration frameworks for exactly this reason (each vertical pack
priced at ~20% incremental on an 80% shared core), and a per-region source fork
fractures that core the same way, just later and more quietly. This belongs in
`## Code Style` as a NEVER.

### 3. How tenant context is threaded — the largest gap in the draft

Not mentioned anywhere in `team-practices.md`. With multi-tenancy from day one
(P4, C-T4) and PHI in scope (C-R2), **a missing tenant filter is a cross-tenant
PHI disclosure — a breach, not a defect.** It is the same class of error
`skill-matrix.md` flags for P3, and it needs the same treatment.

Two workable conventions, and the interview should pick one rather than letting
Bolt 1 pick by accident:

- **(a) Explicit** — every repository and data-access function takes a
  `TenantContext` as its first parameter, with no default. There is no function
  that reads tenant data without one.
- **(b) Ambient** — a `contextvars.ContextVar[TenantContext]` set at call entry,
  read by the data layer, raising if unset.

`contextvars` does propagate correctly across asyncio tasks, so (b) is
technically sound, but it makes the dependency invisible in signatures and fails
**open** if a background task is ever spawned outside the scope. **Recommend (a)
at the data-access boundary**, with (b) reserved for logging and tracing
enrichment. The reason is specific to a team with no reviewer: a missing
argument is a type error caught in CI; a missing ContextVar is a runtime
behaviour you discover in a breach report.

Two supporting conventions:

- **`TenantId = NewType("TenantId", str)`**, never a bare `str`. It costs one
  line and makes `get_calls(clinic_id)` a type error rather than a silent
  cross-tenant read.
- **The repository layer is the single enforcement point** — no raw table or
  query access outside it, enforced by the same import contract as §2. Tenant
  scoping then has exactly one place to be got right instead of N.

And one test convention that is a code-organization matter rather than a
coverage one: **every data-access test uses a shared two-tenant fixture and
asserts that tenant B cannot read tenant A's row.** One fixture, applied per
repository. It is the cheapest available substitute for a second reader on the
isolation boundary.

### 4. How PHI is named and handled so it is not logged by accident

`discovered-rules.md` promotes C-R2 as "never logged outside that boundary."
Correct, and as written unenforceable. The conventions that make it real:

**Type it, do not trust it.** PHI-carrying values are wrapped in a type whose
`__repr__`/`__str__` redacts — a frozen dataclass returning
`<PHI:transcript len=412>`, or an equivalent `Redacted[T]` wrapper. This is the
one convention that survives a tired engineer, because interpolating a
transcript into an f-string is the accident, and this makes the safe rendering
the default rather than the disciplined choice.

**Fail safe in the naming convention.** Inside the compliance core, values are
PHI unless marked otherwise: a `_redacted` / `_safe` suffix marks a value
cleared to leave the boundary, and anything unmarked is assumed unsafe. (The
inverse — a `_phi` suffix on sensitive values — is greppable too, but it fails
open when someone forgets the suffix, which is the failure we are guarding
against.)

**One logging façade; `logging` and `print` banned outside it.** Same banned-import
mechanism as §2. The façade takes structured fields, refuses (or redacts) PHI
types rather than merely discouraging them, and stamps tenant, region and call
id on every line.

**Exception messages are logs.** The framework's own generic guidance —
"propagate errors with context, include input values" — is actively dangerous
here: `raise TranscriptionError(f"failed on {transcript}")` puts PHI into a
stack trace that lands in CloudWatch outside the compliance boundary. Project
rule: **exception messages carry identifiers (call id, tenant id, region,
provider, pipeline stage) and never content.** Worth stating explicitly in
`## Code Style` precisely because it contradicts the default an agent or an
engineer would otherwise reach for.

**Third-party loggers leak too.** Vendor SDKs and HTTP clients at DEBUG happily
log request bodies containing audio and transcripts. Root logging config pins
third-party loggers to WARNING, and that belongs in the written convention
rather than in one person's memory.

**C-T5 makes redaction our code, not a vendor's.** On the India path AWS-native
redaction is unavailable for code-switched calls, so redaction is a first-class
module in P3 with its own tests and its own place in the pipeline ordering — not
a utility called wherever someone remembers. The raw-versus-redacted distinction
must be visible in types and names at every boundary crossing, because on that
path nothing upstream is doing it for us.

### 5. A contradiction between two promoted Hard rules that lands on a convention

`discovered-rules.md` promotes C-R7 (India: security logs retained **minimum one
year**) and C-R8 (India: personal data **erased once its purpose is fulfilled**)
as adjacent bullets. They pull against each other in the same subsystem: if
audit or security log entries embed personal data, the retention obligation and
the erasure obligation cannot both be satisfied for the same bytes. The
inception guardrails say not to carry forward unresolved contradictions, so it
should be surfaced rather than left as two bullets that look independent.

The resolution is a code convention, which is why it lands in my remit:
**audit and security log entries reference by identifier and event type, and
never embed content.** Retention then applies to identifiers and events (safe to
hold a year) and erasure applies to the content store (erasable on purpose
fulfilment) — disjoint data, both obligations satisfiable. This has to hold from
Bolt 1, because retrofitting it means rewriting the audit schema after it has
real entries in it.

Corollary: **`compliance.audit` and the operational logging façade are separate
modules writing to separate sinks, and must never share one.** Two log streams
with different retention regimes and different PHI rules, distinguished in the
module structure so the distinction cannot be lost by someone reaching for the
nearest logger.

### 6. Error handling — what is actually specific to this system

**The failure mode here is dead air, not a 500.** Every provider call sits
inside a live conversation with a patient. Three conventions follow:

- **Every provider call carries an explicit deadline**, and every provider
  interface declares its degraded path — retry once within budget, speak a
  fallback line, or hand off to a human. An adapter that can hang without a
  deadline is the defect class to ban outright, because its symptom is silence
  rather than an error.
- **The provider boundary is the error-translation boundary.** Vendor exceptions
  (`TwilioRestException`, botocore `ClientError`, websocket errors) are caught in
  the adapter and re-raised as domain errors (`TelephonyUnavailable`,
  `TranscriptionFailed`). Otherwise vendor exception types leak into pipeline
  error handling and the C-T1 abstraction is broken on the failure path — which
  is where these abstractions almost always break first, because the happy path
  gets the attention.
- **asyncio specifics.** Every `create_task` result is retained and its exception
  observed; a background task that dies silently takes a leg of the pipeline
  with it and logs nothing. And no bare `except Exception` in pipeline tasks —
  swallowing a timeout there produces exactly the dead air above.
- **Human handoff is the designed error path, not a fallback.** C-T6 and P5 both
  say so. Convention: no error handler terminates a call without either a spoken
  message or a handoff attempt. Silent hangup on a patient is the worst available
  outcome and the easiest one to write by accident.

### 7. File organization

Feature-first, with the proto-Units as the top-level shape: `platform/`
(tenancy, config), `providers/` (per-capability adapters, §2), `compliance/`
(redaction, consent, disclosure, audit), `agents/healthcare/` (the vertical
pack), `surfaces/operator/`.

The load-bearing boundary is **the vertical-agnostic core versus the vertical
pack**. `build-vs-buy.md` and `BRIEF.md` price the whole multi-vertical business
case on ~20% incremental work over an 80% shared core. That seam has to be a
real directory boundary with a real import contract from Bolt 1 —
**`platform/` and `compliance/` never import from `agents/healthcare/`** —
because if that edge is ever allowed, the economics quietly stop being true and
nobody discovers it until the second vertical is quoted.

**Gap: the operator surface (P9) has no stated language, stack or location.**
The draft confirms frontend skill is present and names nothing. That is a
decision Bolt 1 cannot avoid: a Python runtime plus a JS/TS frontend needs a
repository layout convention now (one repo with `apps/` + `packages/` and
per-subtree tool config, or two repos), and the org's trunk-based squash-per-Bolt
practice assumes a single trunk. Recommend one repo, two toolchains, per-language
config at each subtree root — and put the stack question in the interview.

### 8. On the draft's [INTERVIEW] flags inside my remit

- **Naming conventions [INTERVIEW]** — the flag is misdirected rather than
  wrong. Nobody overrides snake_case in Python; asking spends a question and
  returns nothing. **Replace it with the three that actually bind**: the PHI
  naming/typing convention (§4), the tenant-threading convention (§3, a genuine
  a-or-b choice), and the operator-surface stack and repo layout (§7). Same
  interview budget, materially different value.
- **Formatter/linter, deferred by omission** — should be decided now rather than
  "once a project config exists." Skeleton-first means Bolt 1 writes the first
  `pyproject.toml`; deciding after it exists means reformatting. Minor point on
  the suggestion itself: `ruff format` + `ruff check` is one tool and one config
  where Black + Ruff is two, which matters more than usual for a solo build.
  `ruff format` is Black-compatible, so this specialises `org.md`'s deferral
  rather than contradicting it. Tool selection likely overlaps the devsecops
  remit; I am speaking to what the rules must express, not to which scanner runs
  them.
- **Static type checking is absent from the draft entirely.** For a solo build it
  is the highest-leverage automated control available in my remit — it is the
  mechanism that turns "PHI is a distinct type" and "TenantId is not a str" from
  aspiration into a CI failure. mypy or pyright in strict mode over
  `compliance/` and `platform/` at minimum.
- **Concrete finding on "automated checks" as the compensating control.** The
  draft rightly refuses to invent a compensating control for absent review and
  leaves it to the interview. Worth knowing before that question is asked: the
  framework's shipped `linter` and `type-check` sensors match `**/*.{ts,tsx,js}`
  and default to eslint and tsc — `.claude/sensors/aidlc-linter.md` and
  `.claude/sensors/aidlc-type-check.md` both record Python auto-detection as
  deferred. **On a Python-first runtime those two sensors will never fire.** So
  "automated checks" is not a free option supplied by the workflow; it means CI
  jobs the team writes (ruff, mypy, import-linter) or custom sensor manifests. If
  the human is asked to choose between automated checks, external review, and
  accepting the exposure, the first option needs that price attached, or the
  choice is being made against a mirage.

### 9. Proposed replacement text for `## Code Style`

Offered in the draft's own voice and marker convention, for direct integration.

> - Formatter and linter: `ruff format` + `ruff check` for Python, configured in
>   a root `pyproject.toml`, decided now rather than after Bolt 1 writes the
>   first config. Static type checking (mypy or pyright, strict) over
>   `compliance/` and `platform/` at minimum. **[INTERVIEW]** confirm, and see
>   the note on framework sensor coverage for Python.
> - Python for the agent runtime per C-T7. **[INTERVIEW]** the operator surface
>   (P9) has no stated stack or repository layout; Bolt 1 needs both.
> - Naming follows language idiom (snake_case). Not an open question.
> - **Provider boundary.** One package per capability with a `base.py` Protocol
>   and `providers/<vendor>.py` implementations. Vendor SDK imports appear only
>   under `providers/`, enforced by an import contract in CI. Domain types carry
>   no vendor vocabulary. Region selection resolves through a provider registry
>   at session construction; never an inline region conditional. NEVER organise
>   source per region — the boundary is per capability.
> - **Tenant context.** `TenantId` is a distinct type, never a bare `str`. Every
>   data-access function takes a `TenantContext` as its first parameter with no
>   default; `contextvars` is used for logging enrichment only, never for
>   authorisation. All table access lives in the repository layer. Every
>   data-access test asserts tenant isolation from a shared two-tenant fixture.
>   **[INTERVIEW]** explicit parameter (recommended) versus ambient context.
> - **PHI handling.** PHI-carrying values are wrapped in a type whose repr
>   redacts. Inside the compliance core, values are PHI unless suffixed
>   `_redacted`/`_safe`. All logging goes through one façade that refuses PHI
>   types; `logging` and `print` are banned elsewhere; third-party loggers are
>   pinned to WARNING. Exception messages carry identifiers only, never content.
>   Audit entries reference by id and never embed content, so C-R7 retention and
>   C-R8 erasure apply to disjoint data. **[INTERVIEW]** confirm the marker
>   convention direction.
> - **Error handling.** Every provider call carries a deadline and a declared
>   degraded path. Vendor exceptions are translated to domain errors at the
>   adapter. Every `create_task` exception is observed. No error handler ends a
>   call without a spoken message or a handoff attempt.
> - **Layering.** `platform/` and `compliance/` never import from
>   `agents/healthcare/`; the vertical-agnostic seam is a CI-enforced import
>   contract from Bolt 1, because the multi-vertical business case is priced on
>   it.

## Positions

- AGREE: Greenfield means every convention is a choice made now, and drafting
  from `org.md` defaults with explicit **[INTERVIEW]** marks is the honest shape
  — the draft does not pass off a default as a discovered fact anywhere.
- AGREE: Not inventing a compensating control for absent code review. The
  trade-off is genuinely the human's, and three upstream artifacts deferred it
  here rather than to the lead.
- AGREE: Promoting only Hard-severity constraints, and the "Not included, and
  why" section — the reasoning for excluding Firm and Soft is sound and the
  exclusions are visible rather than silent.
- AGREE: Treating the walking skeleton as already decided rather than
  re-litigating it at interview; `scope-document.md` settles it.
- OBJECT: `## Code Style` treats this project's load-bearing conventions as a
  formality — provider-boundary placement, tenant threading and PHI naming are
  all absent, and on a project where conventions *are* the review they are the
  three that cost money if got wrong (§§2-4).
- OBJECT: The naming-convention **[INTERVIEW]** flag spends interview budget on a
  question nobody will answer differently, while three binding conventions go
  unasked (§8).
- OBJECT: C-T1 and C-R2 are promoted as outcomes with no enforcement point, so
  neither can fail a build and neither substitutes for the missing reviewer. The
  rule text is right for `discovered-rules.md`; the enforcement clause belongs in
  `## Code Style` and needs the interview's affirmation, since a machine check is
  a cost the human is agreeing to pay.
- OBJECT: C-R7 (one-year log retention) and C-R8 (erase on purpose fulfilment)
  are listed as independent bullets but pull against each other in the same
  subsystem; the inception guardrails require surfacing that rather than carrying
  it forward (§5).
- OBJECT: Static type checking is absent from the draft though it is the
  highest-leverage automated control available to a solo build, and the shipped
  `linter`/`type-check` sensors cover only TS/JS — so "automated checks" as a
  compensating control is not free here, and the interview should say so (§8).
- OBJECT: The operator surface (P9) has no stated stack or repository layout,
  yet Bolt 1 cannot lay out the repository without one (§7).
