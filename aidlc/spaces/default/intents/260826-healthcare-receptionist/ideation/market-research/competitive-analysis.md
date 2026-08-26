# Competitive Analysis — Healthcare Receptionist Voice Agent

## Scope of this analysis

The approved intent statement (`../intent-capture/intent-statement.md`) frames the
initiative as a clinic-facing agent whose primary value is **staff time returned to
an overloaded front desk**, sold into AI Thinkers' existing healthcare
relationships. This analysis positions the product against the vendors a clinic
would realistically shortlist: vertical healthcare AI agents and horizontal AI
receptionist platforms [Q1]. Developer platforms (Vapi, Retell, Bland) and
India-only vendors are treated as supply-side options in `build-vs-buy.md`, not as
competitors here.

**Evidence standard.** Every figure below is labelled by how it was established:
**verified** (read from the vendor's own site), **third-party** (aggregator or
comparison site), or **hypothesis** (our inference, not established fact). Vendor
capability claims are the vendor's own marketing unless stated otherwise.

## The competitor set

| Vendor | Layer | What they actually sell | Evidence |
|---|---|---|---|
| **Sully.ai** | Vertical healthcare | A "workforce" of role-based healthcare agents — AI Receptionist, Triage Nurse, Scribe, Medical Coder, Interpreter — across phone, SMS and web. Claims 50+ EHR integrations (Epic, Cerner, MEDITECH, Athenahealth) and ISO 27001 / SOC 2 Type II / HIPAA / GDPR certification. Pricing not published; demo-gated. | Verified from [sully.ai](https://www.sully.ai) |
| **GoTo Connect AI Receptionist** | Horizontal SMB | An AI receptionist bolted onto an SMB phone system: 24/7 answering, simultaneous call handling, intent-based routing, intake, reporting. **10+ languages with automatic caller-language detection.** Built on foundation LLMs including OpenAI models. | Verified from [GoTo](https://www.goto.com/connect/ai-virtual-receptionist); corroborated by [GetVoIP](https://getvoip.com/blog/goto-connect-ai-receptionist/) and [CloudTalk](https://www.cloudtalk.io/blog/goto-connect-ai-receptionist-review/) |
| **PolyAI** | Horizontal enterprise | Enterprise contact-centre voice agents across banking, hospitality, insurance, utilities and healthcare. Two surfaces on one runtime — a no-code Agent Studio and a developer ADK. Proprietary dialog model; SOC 2 / HIPAA / GDPR / PCI DSS guardrails. Enterprise sales motion, pricing not published. | Verified from [poly.ai](https://poly.ai) |

Two vendors named in `BRIEF.md` are deliberately **excluded from the competitor
set**: Sesame is a consumer personal-AI and eyewear company, not a clinic vendor,
and Rumik Silk is a text-to-speech API — a supplier, not a competitor. Both remain
relevant as reference points and are treated as such in `build-vs-buy.md`.

## Feature comparison

Rated Strong / Adequate / Weak / Absent against what a clinic buyer would evaluate.

| Capability | Sully.ai | GoTo | PolyAI | Us (target) |
|---|---|---|---|---|
| 24/7 answering, simultaneous calls | Strong | Strong | Strong | Strong (table stakes) |
| Appointment booking / rescheduling | Strong | Adequate | Adequate | Strong (table stakes) |
| Call transfer / human handoff | Strong | Strong | Strong | Strong (table stakes) |
| Healthcare-specific workflows (intake, triage, recall) | Strong | Weak | Adequate | Strong |
| EHR / practice-management integration | Strong (50+) | Absent | Weak | **Unknown — see gap below** |
| US compliance posture (HIPAA, SOC 2) | Strong | Adequate | Strong | Planned, unproven |
| Indic languages + mid-sentence code-switching | Absent | Weak | Weak | Target differentiator |
| India telephony / regulatory fit | Absent | Absent | Absent | Target differentiator |
| SMB-accessible price point | Weak (enterprise) | Strong | Weak (enterprise) | Target |

## Testing the table-stakes classification

The confirmed answer classifies 24/7 answering, booking and transfer as table
stakes, with multilingual handling, compliance depth and EHR integration as
differentiators [Q4]. Two of those three survive scrutiny. One does not, in the
form stated.

**"Multilingual" is not a differentiator.** GoTo already ships 10+ languages with
automatic caller-language detection as a standard feature of an SMB-priced product
(verified). A clinic comparing vendors will treat language coverage as baseline,
not as a reason to choose. Asserting multilingual as an edge against this
competitor set would not survive a buyer conversation.

**The defensible version is narrower.** What is genuinely scarce is *Indic-language
and mid-sentence code-switching at telephony audio quality*. `docs/vendors.md`
records that no STT or TTS vendor publishes an Indian-accented-English or
8kHz-telephony accuracy benchmark; that Azure's documentation explicitly disclaims
changing languages within a sentence; that Rime's code-switching capability
regressed when Arcana was sunset; and that the vendors with the strongest
code-switching claims (Rumik, Sarvam, Gnani) have no HIPAA posture as a category.
None of the three competitors above claims Hinglish or Indic code-switching at all.

**Recommended reclassification** — offered for the next stage to accept or reject,
not applied retroactively to [Q4]:

- **Table stakes:** 24/7 answering, booking, transfer, *and general multilingual
  support*
- **Differentiators:** Indic-language and code-switching handling, compliance
  depth, EHR/practice-management integration, India regulatory fit

This narrows the claim and makes it defensible. It is a *hypothesis* that clinics
in the India market will pay for code-switching quality; nothing in this research
establishes willingness to pay, and no vendor benchmark exists to prove our
handling would be better.

## Positioning

Plotting the set on the two axes a clinic actually weighs — **healthcare depth**
(workflow and system-of-record fit) against **accessibility** (price point and
time to deploy):

- **Sully.ai** occupies high depth, low accessibility. Enterprise motion, 30,000+
  providers claimed, demo-gated pricing.
- **GoTo** occupies low depth, high accessibility. Cheap, fast, generic — a phone
  system with an AI answering feature, not a clinic product.
- **PolyAI** occupies moderate depth, low accessibility. Enterprise contact-centre
  economics; a single clinic is not their buyer.
- **The underserved quadrant is high depth at accessible price**, and it is
  emphatically empty in India, where none of the three has a presence.

This matches the intent statement's positioning — the customer segment follows
existing relationships rather than a segment chosen in the abstract — but it also
exposes the gap below.

## The gap this analysis cannot close

**EHR / practice-management integration is Sully.ai's stated moat, and we do not
know what our clients run.** `BRIEF.md` lists this as an open question. Sully
claims 50+ integrations including the major US systems; matching that breadth is
not realistic, and does not need to be — but matching the *specific* systems our
design-partner clinics use is a precondition for competing on healthcare depth at
all. Until that is known, the "healthcare depth" axis of our position is
aspirational.

This is the single most consequential unknown in this analysis and belongs in
requirements gathering with the pilot clinic, not in further desk research.

## Pricing landscape

The confirmed pricing direction is hybrid — managed-service retainer for pilots,
converting to per-clinic subscription at productisation [Q2]. Against the market:

| Segment | Observed range | Evidence |
|---|---|---|
| SMB AI receptionist products generally | $25–$899/month; most small businesses pay $99–$299/month for 24/7 coverage with booking and CRM integration | Third-party ([AgentZap](https://agentzap.ai/blog/ai-receptionist-pricing-complete-cost-guide-2025)) |
| Named entry-level products | Upfirst $24.95, Dialzara $29, Rosie $49, My AI Front Desk $65, NextPhone $199 flat | Third-party, stated as verified June 2026 |
| Alternative models | Per-call $0.75–$2.40; per-minute $0.25–$0.48 | Third-party |
| Sully.ai, PolyAI | Not published — demo/sales gated | Verified absence |

Two implications. First, the **subscription end of the hybrid model has a hard
ceiling**: a clinic comparing against a $99–$299 market will not pay
enterprise-tier subscription pricing without visible healthcare depth to justify
it. Second, the **retainer end is where the healthcare depth gets paid for**, which
is consistent with starting as a managed service — a pilot retainer is priced
against the staff cost it displaces, not against a $99 SaaS product.

Indian price points are not covered by any source found; the sources above are
US-centric. Sizing this properly requires India-specific pricing research that this
stage did not find. Treat the India price point as **unknown**, not as a
translation of the US range.

## Assumptions & Open Questions

- Which practice-management or EHR systems AI Thinkers' healthcare clients actually
  run is unknown, and it determines whether we can compete on healthcare depth at
  all. [assumption]
- Willingness to pay for Indic code-switching quality is unestablished. The
  capability is scarce; that scarcity is not itself evidence of demand.
  [hypothesis]
- No vendor publishes Indian-accent or 8kHz telephony accuracy benchmarks, so no
  competitor's real-world quality — or ours — can be compared on evidence.
  [assumption]
- Sully.ai's and PolyAI's actual price points are not public, so the comparison
  above places them qualitatively rather than numerically. [assumption]
- India-market price points for clinic AI receptionists were not found in this
  research pass. [assumption]
- Competitor capability ratings are drawn from vendor marketing, not from hands-on
  evaluation or customer reference calls. [assumption]
