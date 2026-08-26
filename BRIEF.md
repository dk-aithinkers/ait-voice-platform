# AIT Voice Platform — project brief

Input for the AI-DLC workflow's Ideation and Inception stages. Captures decisions
already made, so the workflow starts from a considered position rather than a
blank prompt. Everything here is a starting position, not a frozen requirement —
the workflow's approval gates are where it gets challenged.

## What we're building

A multi-tenant AI voice agent platform: one shared engine that answers and places
phone calls with natural, multilingual AI, sold as industry-specific **agent
packs** rather than as a generic "AI answers your phone" product.

The company (AI Thinkers) has existing clients in **healthcare, aerospace parts,
and finance**. Those relationships are the distribution channel and the source of
design partners.

## Why this shape

The market splits into three layers:

- **Voice infrastructure** (TTS/STT) — commodity. Buy, don't build.
- **Horizontal platforms** (GoTo AI Receptionist, PolyAI, Vapi, Retell, Bland) —
  crowded, no defensible position for a new entrant.
- **Vertical applications** (Sully.ai in healthcare) — where margin and
  defensibility are. Sully wins on EHR integration, role-specific agents, and
  compliance, not on better models.

Our differentiation: existing vertical relationships, plus an **India + US**
dual-market posture that the incumbents ignore (Indian languages, Indian
telephony, Indian price points).

### Reference points

| Company | What to take from it |
|---|---|
| [Sully.ai](https://www.sully.ai) | Role-based agent packs; deep integration with a vertical's system of record; compliance as moat |
| [GoTo Connect](https://www.goto.com/connect/ai-virtual-receptionist) | The SMB receptionist use case; language auto-detection; 24/7 simultaneous answering |
| [PolyAI](https://poly.ai) | No-code studio *and* developer SDK on one runtime; guardrails; handling hard calls (auth, payments, disputes) |
| [Sesame](https://www.sesame.com) | The naturalness bar users now expect from voice |
| [Rumik Silk](https://rumik.ai/silk-api) | Indian-language TTS with mid-sentence switching, ~162ms latency — buy this layer |

## Architecture position

One **platform core**, vertical-agnostic:

- Telephony (Twilio for US, Exotel-class for India)
- STT → LLM dialog engine → TTS, each **swappable per deployment**
- Human handoff with structured context — a compliance primitive, not a fallback
- Call analytics, transcripts, outcomes
- Compliance in the skeleton: region-isolated deployments, PII/PHI redaction
  before logs or analytics, jurisdiction-aware consent disclosure, append-only
  audit log

Then **agent packs** on top, roughly 20% incremental work each on an 80% shared core.

### Why providers must be swappable

Not a preference — a constraint. US healthcare requires a signed BAA from every
vendor touching call audio, transcripts, or caller identity (one gap breaks the
chain). India pushes toward in-region processing and regional-language TTS that
US vendors don't match on quality or cost. Latency budgets differ per vertical.
See [PROVIDERS.md](PROVIDERS.md).

## Vertical sequencing

**1. Healthcare receptionist — first, and the subject of this MVP.**
Most templated, fastest to a pilot, and the compliance work (BAA chain,
redaction, audit) is ~80% reusable by the finance pack later.
Scope: answer clinic calls 24/7, book/reschedule/cancel appointments, patient
intake, outbound reminder and recall calls. Integrate with the practice
management / EHR systems our clients actually run.

**2. AOG parts desk — fast-follow pilot, the real differentiator.**
Aerospace distributors staff 24/7 Aircraft-on-Ground hotlines. The agent answers
instantly, captures part number, condition code (NE/OH/SV), certifications
(8130-3/EASA), quantity and ship-to, checks ERP availability, quotes or escalates
to the on-call human with a structured summary. No competitor has a template for
this.

**3. Finance — third, deliberately.**
Collections reminders, loan intake, KYC callbacks, account inquiries. Highest
willingness to pay, least forgiving compliance. Enter once the audit, consent,
and handoff machinery is proven by the first two.

## Compliance requirements

**US:** HIPAA (BAA chain across telephony, STT, LLM, TTS, storage, analytics);
PCI DSS — stay out of scope via DTMF masking / payment-IVR handoff rather than
handling card data; TCPA consent for outbound; state call-recording laws
(~13 require two-party consent) and AI-disclosure rules; SOC 2 Type II as the
enterprise procurement checkbox.

**India:** DPDP Act 2023 (consent, purpose limitation, breach notification,
deletion/correction rights — voice recordings are personal data); RBI guidelines
for collections (call hours, harassment rules, outsourcing, payment-data
localisation); TRAI/DLT registration for outbound at scale.

**Sequencing:** region pinning, redaction, consent engine and audit log are
Phase 1 architecture — cheap now, brutally expensive to retrofit. HIPAA is
self-attested via a clean BAA chain, so US healthcare pilots don't wait on a
certification body. SOC 2 Type I → II in months 6–12 unlocks mid-market and
finance.

## Business model

Three doors into the same building, in order:

1. **Managed service (start here)** — we configure and operate agents for
   clients; they get a working number and a dashboard. Needs no self-serve UI, so
   every engagement is paid product development.
2. **SaaS** — the proven pack becomes self-serve: sign up, pick a template,
   connect calendar/EHR, go live. Needs onboarding, template editor, billing.
3. **Platform/API (optional, later)** — white-label for other agencies. Most
   scalable, most crowded, lowest margin.

Architecturally there is no fork: the multi-tenancy, per-client configuration,
and dashboard built for (1) are the foundation of (2). Only who clicks the
buttons changes.

## MVP scope for this workflow

Platform core plus the **healthcare receptionist pack**, deployable to both a US
and an India tenant, with one existing healthcare client as design partner
(white-label). Operations-phase stages are intentionally out of scope — the repo
default scope is `mvp`. Promote with `/aidlc --scope feature` when it graduates.

## Open questions for the workflow to resolve

- Which practice-management / EHR systems do our healthcare clients actually run?
  (Determines the first integration and is currently unknown.)
- Which pilot client, in which market, first — US or India?
- Buy vs. build for the orchestration layer (LiveKit / Pipecat vs. in-house).
- Telephony vendor per region, and whether numbers are ours or the client's.
- Where the human-handoff destination lives — client's existing phone system, or ours.
