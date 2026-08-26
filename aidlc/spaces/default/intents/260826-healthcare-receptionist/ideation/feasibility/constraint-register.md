# Constraint Register

## Purpose

Constraints are non-negotiable boundaries the design must satisfy — distinct from
risks (which may or may not occur, see `raid-log.md`) and from decisions still
open. Each entry states the constraint, where it comes from, and what it forecloses.

Sources are the approved intent statement
(`../intent-capture/intent-statement.md`), the approved market research
(`../market-research/competitive-analysis.md`,
`../market-research/market-trends.md`, `../market-research/build-vs-buy.md`), the
answers in `feasibility-questions.md`, and the vendor research in
`docs/vendors.md`.

Severity: **Hard** = cannot be designed around. **Firm** = could be changed only
by revisiting an approved decision. **Soft** = a strong default that a good reason
could override.

## Technical constraints

| ID | Constraint | Severity | Source | What it forecloses |
|---|---|---|---|---|
| C-T1 | Every speech and telephony component must be replaceable per deployment region | Hard | `docs/vendors.md`: no vendor covers US healthcare and India adequately | Any design that hard-codes a vendor, or a single global pipeline configuration |
| C-T2 | Telephony must support bidirectional media streaming over WebSocket | Hard | `docs/vendors.md`: classic IVR/TwiML providers cannot host an LLM voice agent | Several established Indian CPaaS vendors, including Knowlarity, Kaleyra and MyOperator |
| C-T3 | The pipeline must be cascaded (speech→text→model→speech), not speech-to-speech | Firm | `docs/vendors.md`: cascaded keeps text at every stage so each component is independently BAA-able and auditable | Speech-to-speech APIs for the compliant path, and the latency floor they would offer |
| C-T4 | Multi-tenancy must be built in-house | Hard | `../market-research/build-vs-buy.md`: no managed voice platform offers native multi-tenancy | Adopting Vapi, Retell, Bland or Synthflow as the platform |
| C-T5 | On AWS, Indian-language calls cannot use both code-switching and automated PII redaction | Hard | `docs/vendors.md`: Transcribe streaming redaction covers only English variants and Spanish, and cannot combine with multi-language identification | Relying on AWS-native redaction for the India voice path |
| C-T6 | Human handoff must carry structured context | Firm | `../market-research/market-trends.md`: acceptance is contingent on human availability, not on the technology | Treating handoff as a failure fallback rather than a designed path |
| C-T7 | Implementation language is Python for the agent runtime | Soft | [Q2] team skill profile; orchestration candidates are Python-first | A TypeScript-only implementation of the voice runtime |

## Organisational constraints

| ID | Constraint | Severity | Source | What it forecloses |
|---|---|---|---|---|
| C-O1 | Engineering capacity is contended with paid client delivery | Hard | [Q6] | Any plan assuming dedicated full-time capacity, or blocking gates on engineering tasks |
| C-O2 | No fixed budget or deadline; funded from ongoing services revenue | Firm | [Q4] | Deadline-driven scope cuts; also removes any basis for a delivery estimate |
| C-O3 | Scope and priority decisions rest with one person, with engineering influencing | Firm | Intent statement, from intent capture | Committee decision-making, and any assumption that clinic feedback arbitrates scope |
| C-O4 | No formal reporting cadence | Soft | Intent statement | Milestone-gated stakeholder reporting as a project mechanism |
| C-O5 | Partnering is excluded; build and buy only | Firm | [Q6 of market research] | Reselling or white-labelling an existing vertical product, and distribution partnerships |
| C-O6 | India regulatory registration is carried in-house | Hard | `docs/vendors.md`: no provider performs DLT registration or 1600-series numbering on a customer's behalf | Outsourcing the India compliance onboarding burden |

## Regulatory constraints

These are compressed from `docs/vendors.md`, which states its compliance section
is research and not legal advice. Nothing here is legal advice.

| ID | Constraint | Severity | Jurisdiction | What it forecloses |
|---|---|---|---|---|
| C-R1 | Every vendor touching call audio, transcripts or caller identity needs its own executed BAA; a BAA does not flow down to subcontractors | Hard | US | Any vendor without a BAA in the US healthcare path — which per `docs/vendors.md` excludes the entire India-vendor category including Rumik, Sarvam, Gnani, Exotel and Reverie |
| C-R2 | Call audio and transcripts are PHI — by content, and because voice is itself a listed identifier | Hard | US | Treating raw audio as non-sensitive, or logging it outside the compliance boundary |
| C-R3 | Verbal AI disclosure at the start of every call | Firm | US (practical floor) | Silent AI operation; California AB 2905 requires disclosure before the message, and Utah UAIPA mandates it for regulated professions |
| C-R4 | Recording disclosure on every call, nationwide | Firm | US | Geo-detecting caller state law in real time as an alternative to universal disclosure |
| C-R5 | No marketing content in reminder calls | Hard | US | Upsell or promotional content in the outbound flow — it would void the TCPA healthcare exemption the reminder agent depends on |
| C-R6 | Commercial calling requires 1600-series numbering (transactional) with DLT registration | Hard | India | Ordinary 10-digit numbers for outbound; penalties escalate to ₹1M per instance with a two-year cross-operator blacklist |
| C-R7 | Security logs retained a minimum of one year; breach report to the Data Protection Board within 72 hours | Hard | India | Short log retention, and any breach process without a 72-hour reporting path |
| C-R8 | Personal data erased once its purpose is fulfilled | Hard | India | Indefinite retention of call recordings and transcripts by default |
| C-R9 | Consent for commercial calls expires after 7 days | Hard | India | Treating consent as durable; the consent model must carry expiry |

## Constraints deliberately not yet binding

Recorded so their absence is visible rather than assumed away.

| Item | Status | Why it is not a constraint yet |
|---|---|---|
| Target EHR / practice-management systems | Unknown | Requires a client conversation [Q1]. Until known, no integration constraint can be stated — this is the largest gap in this register. |
| Launch jurisdiction | Undecided | [Q3]. Until settled, both C-R1–C-R5 (US) and C-R6–C-R9 (India) must be treated as potentially binding, which is the expensive posture. |
| SOC 2 certification | Not required | `docs/vendors.md`: a procurement expectation, not a legal requirement. Becomes binding when an enterprise buyer demands it. |
| PCI DSS | Not applicable | No payment processing in scope. Would become binding if payment capture is ever added. |
| Data residency in India | Not mandated | `docs/vendors.md` records DPDP does not mandate localisation, with low-to-medium confidence and a recommendation to confirm with Indian counsel. |
