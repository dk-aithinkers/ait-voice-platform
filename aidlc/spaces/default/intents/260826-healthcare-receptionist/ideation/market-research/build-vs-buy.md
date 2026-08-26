# Build vs Buy Assessment

## Scope and method

This assessment covers what AI Thinkers builds versus buys to deliver the
initiative described in the approved intent statement
(`../intent-capture/intent-statement.md`) — a clinic receptionist agent on a
vertical-agnostic platform core, deployable to both a US and an India tenant.

**Partnering is out of scope** [Q6]. The assessment covers build and buy only.

Two layers are treated differently, per the confirmed approach [Q5]:

- **Component layer** (telephony, speech-to-text, text-to-speech) — the decision to
  buy is settled. Recorded and justified below, not re-litigated.
- **Orchestration layer** — deliberately re-opened and argued from first
  principles below rather than inherited from `docs/vendors.md`.

Vendor-level detail is authoritative in `docs/vendors.md` and is cited rather than
re-derived [Q7]. This document stays at the level of *what we build and what we
buy*; component selection and system design belong to later stages.

The decision rule applied throughout is the standard one: **if a capability is not
a core differentiator and a mature vendor solution exists, buy it. Build only where
the capability is central to competitive advantage, or where no vendor solution can
meet the requirement.**

## What is actually our differentiator

The build/buy line follows from this, so it is stated first. Per
`competitive-analysis.md`, the defensible differentiators are vertical healthcare
depth (workflow and system-of-record fit), compliance depth, Indic-language and
code-switching handling, and India regulatory fit. Conversational plumbing is not
on that list. Neither is speech processing.

## Component layer — buy (settled)

| Layer | Decision | Rationale |
|---|---|---|
| Telephony | **Buy** | Carrier relationships, number provisioning and regulatory registration are not replicable. `docs/vendors.md` establishes that no single provider serves both markets well, which makes this a per-region purchase behind a stable internal interface. |
| Speech-to-text | **Buy** | Commodity with rapid vendor improvement. Building would mean competing with vendors whose entire business is this. |
| Text-to-speech | **Buy** | As above. `docs/vendors.md` records the sharpest constraint here: the best India code-switching vendor has no HIPAA posture and its terms disclaim clinical use, so this must be bought *per deployment*, not once. |
| Large language model | **Buy** | Not a candidate for building at any scale we operate at. |

The consequential property is not *who* we buy from — that is a later-stage
decision — but that **every one of these is bought per region and must be
replaceable**. `docs/vendors.md` states this is not an architectural preference but
the only configuration the vendor landscape permits, because no vendor covers US
healthcare compliance and India well.

## Orchestration layer — argued fresh

The candidates are: a managed voice-agent platform (Vapi, Retell, Bland), an
open-source framework we operate (LiveKit Agents, Pipecat), or building the
orchestration ourselves.

### Managed platforms — rejected

Not on price, but on two structural facts recorded in `docs/vendors.md`: **none
offers native multi-tenancy** (the market's own workaround is third-party wrapper
products), and **none showed an India region**. Multi-tenancy is not a feature we
can defer — it is the substrate of both the managed-service and SaaS business
models in `BRIEF.md`. If the tenant layer must be built regardless, building it on
infrastructure we control is strictly better than building it on someone else's
abstraction. The absent India region independently disqualifies the tier for the
second market.

*Noted for completeness:* Bland is the architectural exception, running its own
models with on-prem/VPC options. It remains rejected on multi-tenancy and India
region, and buying it would also mean buying its model stack — the opposite of the
per-region swappability the component layer requires.

### Building orchestration ourselves — rejected

Turn detection, interruption handling, barge-in and telephony audio handling are
solved problems with mature open-source implementations. Building them would
consume the schedule that vertical depth and compliance need, to reach parity with
an Apache-2.0 library. It fails the decision rule on both limbs: not a
differentiator, and mature solutions exist.

### LiveKit vs Pipecat — the real decision, and it is closer than the vendor document suggests

`docs/vendors.md` recommends LiveKit. Examining it fresh, the case is sound but the
counter-case is stronger than that document credits.

**For LiveKit:** WebRTC plus SIP (GA 2025), a multilingual turn-detection model,
telephony noise cancellation, Apache 2.0 with no platform fee when self-hosted. The
decisive property is the **compliant on-ramp with an exit**: LiveKit Cloud offers an
ap-south (Mumbai) region *and* HIPAA eligibility with SOC 2 Type II and a signed BAA
at Scale tier — so a pilot can run managed and compliant, then migrate to
self-hosted when volume or residency demands. Few options give both a compliant
managed start and a credible self-hosted end state.

**For Pipecat — the point the vendor document underweights:** the two vendors
`docs/vendors.md` identifies as strongest for the India market both ship Pipecat
integrations. Exotel — the strongest India telephony option, with mature
bidirectional streaming — publishes Pipecat integrations and sample repositories.
Rumik Silk — the best India code-switching TTS, roughly 10× cheaper than
alternatives — ships an official Pipecat package. Pipecat also has the larger
community. **The India stack leans Pipecat; the compliance story leans LiveKit.**

**Against Pipecat:** its maintainers have an open issue acknowledging the
self-hosted production path lacks battle-tested blueprints, and it is optimised for
Daily's managed cloud. Self-hosted production is precisely our end state.

### Recommendation

**Adopt LiveKit, and budget explicitly for writing the India adapters ourselves.**

The reasoning is that the single-core principle is load-bearing for the entire
business case. `BRIEF.md` prices each additional vertical pack at roughly 20%
incremental work on an 80% shared core; running different orchestration frameworks
per region would fracture that core and destroy the economics that make the
aerospace and finance packs attractive. Given a single framework must be chosen,
the compliance on-ramp is harder to replicate than the integration adapters:
adapters are bounded engineering work against documented streaming interfaces,
whereas a HIPAA-eligible managed environment with an India region and a signed BAA
cannot be built by us at all in the pilot timeframe.

This recommendation carries a real, acknowledged cost — the Exotel and Rumik
integrations come free with the framework we are not choosing. It should be
validated by a **time-boxed spike** proving Exotel bidirectional streaming against
LiveKit before the choice is treated as settled. If that spike fails or proves
disproportionately expensive, the decision genuinely reopens, and this document
should not be read as foreclosing it.

*Confidence: medium.* This rests on `docs/vendors.md`'s vendor research and on
public documentation, not on hands-on evaluation of either framework.

## What we build

| Capability | Why it cannot be bought |
|---|---|
| Multi-tenant platform core | No managed platform offers native multi-tenancy (`docs/vendors.md`). It is the substrate of both business models. |
| Per-region provider abstraction | The requirement that every speech and telephony component be swappable per deployment is specific to our dual-market compliance position. No vendor sells it. |
| Compliance machinery — region isolation, PII/PHI redaction, consent disclosure, immutable audit log | This is a stated differentiator, and `market-trends.md` finds compliance becoming a barrier to entry. Buying it is neither possible nor desirable. |
| Healthcare agent pack — clinic workflows, intake, booking, recall | The differentiator itself. |
| Practice-management / EHR integration | Sully.ai's stated moat, and unbuyable — though `competitive-analysis.md` records that we do not yet know which systems our clients run, which blocks scoping this. |
| Human handoff with structured context | `market-trends.md` finds patient acceptance is contingent on human availability, making this an acceptance requirement as well as a compliance one. |
| Call analytics, transcripts, outcomes | Tied to the tenant model and the redaction boundary. |

## Costs this assessment attributes to build

Because partnering is excluded [Q6], burdens that a partner might otherwise absorb
are carried in-house. The most concrete is **India regulatory registration**:
`docs/vendors.md` records that DLT registration and 1600-series numbering are
mandatory for commercial calling and that **no provider does this on a customer's
behalf** — Twilio, Telnyx, Plivo and Exotel all document it as the customer's own
job on carrier portals. Penalties escalate to ₹1M per instance with a two-year
cross-operator blacklist. This is unavoidable in-house operational work for any
India deployment, and it is a *precondition of the India pilot*, not a
productisation task.

No monetary estimates are offered. `docs/vendors.md` states that self-hosting
becomes cost-favourable only above roughly 1.5M agent-minutes per month against
~$15.5k/month of fixed infrastructure and SRE cost — which, with no volume forecast
and no capture target [Q8], cannot yet be evaluated against our actual case.

## Assumptions & Open Questions

- The LiveKit recommendation is not validated by hands-on evaluation. It should be
  confirmed by a time-boxed spike proving Exotel bidirectional streaming against
  LiveKit before being treated as settled. [assumption]
- Choosing LiveKit forgoes the Exotel and Rumik Pipecat integrations, and the cost
  of writing equivalent adapters is unestimated. [assumption]
- Whether Rumik or any India TTS vendor would sign a BAA is unresolved;
  `docs/vendors.md` advises planning on the assumption that they will not.
  [assumption]
- EHR/practice-management integration cannot be scoped until the systems AI
  Thinkers' clients run are known. [assumption]
- No build cost, headcount, or timeline estimate is offered. Producing one requires
  a volume forecast that does not exist at this stage. [assumption]
- The 1.5M agent-minutes/month self-hosting break-even is quoted from
  `docs/vendors.md` and has not been independently verified. [assumption]
- Partnering was excluded by instruction, not by analysis. Should the India
  regulatory burden or the EHR integration gap prove larger than expected, that
  exclusion is worth revisiting. [hypothesis]
