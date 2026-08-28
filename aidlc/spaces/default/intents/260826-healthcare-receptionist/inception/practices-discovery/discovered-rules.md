# Discovered Rules

Only Hard-severity constraints from `../feasibility/constraint-register.md`,
and hard constraints the human explicitly affirmed as binding during this
stage's interview, are turned into rules here — Firm and Soft constraints are
left in the register, and open preferences are left as guidance in
`team-practices.md`. None of these duplicate the eight rules already recorded
in `memory/project.md`'s `## Mandated`, which are about workflow/process
discipline (confirmation receipts, evidence standards, template honesty)
rather than about the product being built; these are about the product being
built.

## Mandated

- ALWAYS retain security logs for a minimum of one year and support breach
  reporting to India's Data Protection Board within 72 hours, for the India
  tenant — **applied only to logs that reference records by opaque
  identifier and event type; see the audit/security log rule below for how
  this is kept satisfiable alongside the erasure rule that follows it.**
  (source: C-R7, Hard, India, `../feasibility/constraint-register.md`)
- ALWAYS erase personal data once its purpose is fulfilled, for the India
  tenant — no indefinite retention of call recordings or transcripts by
  default — **applied to the content store, which is kept separate from the
  security/audit log covered by the rule above so the two obligations apply
  to disjoint data.** (source: C-R8, Hard, India,
  `../feasibility/constraint-register.md`)
- ALWAYS keep the immutable audit log and every security log free of PHI:
  entries reference the call, caller, and event by opaque identifier and
  type only, and never embed content. This is the resolution the human
  affirmed for the contradiction two independent reviewers found between the
  rule above (retain security logs at least one year) and the rule above it
  (erase personal data once its purpose is fulfilled) — both hold only if
  the retained log contains no personal data. The two log classes carry
  different retention policies and are enforced as separate infrastructure
  (separate sinks, separate IaC-defined retention), not merely as a written
  convention, so the separation is machine-checkable rather than
  memorized. Must hold from Bolt 1: retrofitting this after the audit
  schema has real entries means rewriting it under load. (source: Q1 of the
  practices-discovery interview, resolving C-R7 × C-R8 ×
  `../scope-definition/intent-backlog.md`'s immutable-audit-log requirement
  for P3)
- ALWAYS verify an executed BAA exists for a vendor before it is given access
  to call audio, transcripts, or caller identity — a BAA does not flow down to
  subcontractors, so each vendor in the chain needs its own. (source: C-R1,
  Hard, US, `../feasibility/constraint-register.md`)
- ALWAYS treat call audio and transcripts as PHI, handled only within the
  compliance boundary — never as non-sensitive data, and never logged outside
  that boundary. (source: C-R2, Hard, US,
  `../feasibility/constraint-register.md`; voice is itself a listed
  identifier)
- ALWAYS use 1600-series numbering with completed DLT registration for
  outbound commercial calls placed to India numbers. (source: C-R6, Hard,
  India, `../feasibility/constraint-register.md`; penalties escalate to ₹1M
  per instance with a two-year cross-operator blacklist)
- ALWAYS expire commercial-call consent after 7 days, for the India tenant —
  the consent model must carry expiry rather than treating consent as
  durable. (source: C-R9, Hard, India,
  `../feasibility/constraint-register.md`)
- ALWAYS build multi-tenancy in-house rather than adopting a managed voice
  platform's native tenancy. (source: C-T4, Hard,
  `../feasibility/constraint-register.md`, citing
  `../market-research/build-vs-buy.md`: no managed voice platform offers
  native multi-tenancy)
- ALWAYS keep every speech and telephony component replaceable per deployment
  region — no design may hard-code a vendor or use a single global pipeline
  configuration. (source: C-T1, Hard, `../feasibility/constraint-register.md`,
  citing `docs/vendors.md`: no vendor covers US healthcare and India
  adequately)
- ALWAYS quarantine vendor SDK imports behind a per-capability provider
  boundary, with no vendor vocabulary in domain types. Affirmed by the human
  as a binding code convention, not guidance, because it is the enforcement
  point the constraint above (C-T1) otherwise lacks — a written outcome with
  no build-time check is the weakest form a Hard constraint can take on a
  team with no second reader. (source: Q8-A of the practices-discovery
  interview, enforcing C-T1)
- ALWAYS pass tenant context explicitly as the first parameter of every
  data-access function — never ambiently. A missing tenant filter is a
  cross-tenant PHI disclosure, not a defect, given multi-tenancy from day one
  (C-T4) and PHI in scope (C-R2); an explicit parameter turns the omission
  into a type error rather than a runtime discovery. (source: Q8-B of the
  practices-discovery interview, enforcing C-T4 × C-R2)
- ALWAYS carry PHI-touching values in a wrapper type whose representation
  redacts, and route all logging through a single façade that refuses PHI
  values rather than discouraging them. Affirmed as binding because "never
  logged outside the compliance boundary" (C-R2) is otherwise unenforceable
  — this converts the single most likely accidental breach into a build
  failure. (source: Q8-C of the practices-discovery interview, enforcing
  C-R2)
- ALWAYS write tests before implementation for PHI-touching code (any
  component that reads, writes, redacts, or routes PHI), gated on branch
  coverage and a named test corpus — including code-switched samples — that
  must pass before merge. (source: Q3 of the practices-discovery interview)
- ALWAYS block a merge on a failed quality gate; an override requires an
  in-repo written waiver carrying a justification and an expiry date. (source:
  Q2 of the practices-discovery interview)
- ALWAYS gate a production deploy on an audited machine check — tests,
  security/dependency/IaC scans, and a BAA-register check for every vendor in
  the live PHI path — passing; self-approval by the sole engineer is not
  treated as a control, and an override requires an in-repo written waiver
  carrying a justification and an expiry date. (source: Q7 of the
  practices-discovery interview)
- ALWAYS include one bounded external technical review of the compliance core
  (P3), bundled into the compliance-counsel engagement already planned before
  real patient data touches the system. This is the only control identified
  during review that covers redaction correctness, consent correctness, and
  audit completeness — the three failure classes no automated scanner has an
  opinion about. (source: Q4 of the practices-discovery interview)

## Forbidden

- NEVER adopt a telephony provider that cannot support bidirectional media
  streaming over WebSocket — this rules out classic IVR/TwiML-only providers
  for the voice pipeline. (source: C-T2, Hard,
  `../feasibility/constraint-register.md`, citing `docs/vendors.md`:
  forecloses Knowlarity, Kaleyra, MyOperator among others)
- NEVER rely on AWS Transcribe's native redaction for Indian-language,
  code-switched calls — automated PII redaction and code-switching cannot be
  combined on that AWS path. (source: C-T5, Hard,
  `../feasibility/constraint-register.md`; Transcribe streaming redaction
  covers only English variants and Spanish)
- NEVER include marketing or upsell content in outbound reminder calls — it
  would void the TCPA healthcare exemption the reminder agent depends on.
  (source: C-R5, Hard, US, `../feasibility/constraint-register.md`)
- NEVER plan India-tenant registration (DLT, 1600-series numbering) as
  outsourceable — no provider performs it on a customer's behalf; it must be
  carried in-house. (source: C-O6, Hard,
  `../feasibility/constraint-register.md`)
- NEVER place real call audio, transcripts, or caller identity in test
  fixtures, in the repository, or on a development workstation; test data
  for every PHI-touching component is synthetic. A CI runner and a
  development workstation are both outside the compliance boundary, and the
  CI vendor carries no BAA. (source: Q6-A of the practices-discovery
  interview, a testing corollary of C-R2)
- NEVER use the repository or CI as the storage location for the real
  recordings the Indic accuracy bake-off (D-02) needs; a separately defined
  place holds them, treated as its own PHI environment with its own access
  controls. (source: Q6-B of the practices-discovery interview, a testing
  corollary of C-R2 and C-R1)

## Not included, and why

- **AI disclosure and recording disclosure at call start** (C-R3, C-R4) are
  Firm, not Hard, per the register — left as constraints rather than promoted
  to a rule here, though `initiative-brief.md` calls the greeting "the most
  regulated and most experience-critical moment in the product," which the
  interview or a later design stage should not lose sight of.
- **Cascaded (not speech-to-speech) pipeline** (C-T3) is Firm, not Hard —
  left in the register for the same reason.
- **Formatter, linter, CI platform, and operator-surface stack** were
  discussed by two reviewers as decisions Bolt 1 cannot avoid, but none of
  them was put to the human at this stage's interview — they were not asked,
  so they are not promoted here as either a rule or an affirmed default. See
  `team-practices.md`'s Code Style section and `evidence.md`'s uncertainty
  list.
- **Construction Autonomy Mode** (continue autonomously vs. gate every Bolt)
  is genuinely undecided — the org's own sequencing places that choice at the
  ladder prompt after Bolt 1 ships, not at this stage, so it is not promoted
  here.
