# Market Research & Competitive Analysis — Questions

**Mode:** guided

## Context

These questions build on the approved intent statement
(`../intent-capture/intent-statement.md`) and on two documents already in the
repository: `BRIEF.md` (positions taken before the workflow started) and
`docs/vendors.md` (an August 2026 vendor research pass covering telephony, STT,
TTS, orchestration, and compliance).

Where those documents already state a position, the question below asks you to
confirm, change, or defer it rather than re-asking from scratch.

Every question offers an option for "not yet decided" so a genuinely open item
stays open rather than being forced into an invented answer.

---

## Q1. Which competitor set should the analysis position us against?

`BRIEF.md` splits the market into voice infrastructure, horizontal platforms, and
vertical applications, and names Sully.ai, GoTo, PolyAI, Sesame and Rumik as
reference points.

A. Vertical healthcare AI only — Sully.ai and comparable healthcare-specific agent vendors. Positions us as a healthcare product.
B. Vertical healthcare plus horizontal receptionist platforms (GoTo, PolyAI) — these are what a clinic would actually shortlist against us.
C. All three layers including the developer platforms (Vapi, Retell, Bland) and the India-market players — the full landscape a buyer or investor might raise.
D. Indian-market voice AI vendors specifically — the competitor set that matters for the market nobody else serves well.
E. Not yet decided — analyse broadly and let the findings determine positioning.
X. Other (please specify)

[Answer]: B. Vertical healthcare plus horizontal receptionist platforms (GoTo, PolyAI) — these are what a clinic would actually shortlist against us.

---

## Q2. What pricing model should the analysis evaluate us into?

Nothing in the intent statement or brief fixes a pricing model, and the success
metrics deliberately excluded commercial measures.

A. Per-clinic monthly subscription (SaaS-style), tiered by call volume or location count.
B. Per-minute or per-call usage pricing, passed through with margin over telephony and model costs.
C. Managed-service retainer — setup fee plus monthly operations fee, matching the "start with managed service" business model in the brief.
D. Hybrid — managed-service retainer for pilots, converting to per-clinic subscription at productisation.
E. Not yet decided — the analysis should surface what comparable vendors charge and leave our model open.
X. Other (please specify)

[Answer]: D. Hybrid — managed-service retainer for pilots, converting to per-clinic subscription at productisation.

---

## Q3. Which market should the sizing exercise treat as primary?

The launch jurisdiction is an open assumption carried forward from intent
capture, and the product-lead review flagged it as a Major finding.

A. India first — the market incumbents ignore, lower compliance burden to launch, existing relationships.
B. US first — higher willingness to pay, HIPAA work is reusable for the finance pack later.
C. Both sized equally — the platform is dual-market by design and the sizing should not pre-judge the pilot.
D. Size both, but recommend one based on what the research finds.
E. Not yet decided — size both and defer the recommendation to the feasibility stage.
X. Other (please specify)

[Answer]: C. Both sized equally — the platform is dual-market by design and the sizing should not pre-judge the pilot.

---

## Q4. Which capabilities do you consider table stakes versus differentiators?

This shapes what the competitive analysis scores vendors on.

A. Table stakes: 24/7 answering, appointment booking, call transfer. Differentiators: multilingual/Hinglish, compliance depth, EHR integration.
B. Table stakes: everything in A plus multilingual. Differentiator is compliance and vertical depth only.
C. Table stakes: answering and booking only. Everything else — languages, compliance, integrations — is a differentiator at this market stage.
D. Not yet decided — let the competitive analysis determine where the market baseline actually sits.
X. Other (please specify)

[Answer]: A. Table stakes: 24/7 answering, appointment booking, call transfer. Differentiators: multilingual/Hinglish, compliance depth, EHR integration.

---

## Q5. How firm is the "buy the voice layer, build the platform" position?

`BRIEF.md` states voice infrastructure is commodity and should be bought, and
`docs/vendors.md` recommends self-hosting LiveKit Agents with LiveKit Cloud as
the MVP bridge.

A. Firm — confirm it in the build-vs-buy artifact and move on. STT/TTS/telephony bought, orchestration on LiveKit, platform and packs built in-house.
B. Firm on buying STT/TTS/telephony, but the orchestration choice (LiveKit vs Pipecat vs in-house) should be re-examined rather than assumed.
C. Re-examine the whole stack — including whether to build on a managed platform (Vapi/Retell/Bland) despite the multi-tenancy and India gaps noted in the vendor research.
D. Not yet decided — present the trade-offs without a recommendation.
X. Other (please specify)

[Answer]: B. Firm on buying STT/TTS/telephony, but the orchestration choice (LiveKit vs Pipecat vs in-house) should be re-examined rather than assumed.

_Recorded note: the human delegated this choice ("whatever you recommend best"); B is the orchestrator's recommendation, on the grounds that component choices are commodity and swappable by design while orchestration is the most expensive decision to reverse._

---

## Q6. Is partnering a real option, or is this build-and-buy only?

The stage's build-vs-buy assessment can include partnering, but nothing in the
brief mentions it.

A. No partnering — we build the platform and buy components. Not a consideration.
B. Consider white-labelling an existing vertical product (e.g. reselling a healthcare voice vendor) as a faster route to a first pilot.
C. Consider partnering on distribution only — our platform, someone else's clinic relationships.
D. Consider partnering for compliance or telephony in India specifically, where the regulatory burden (DLT registration, 1600-series numbering) is heaviest.
E. Not yet decided — surface partnering options in the analysis without committing.
X. Other (please specify)

[Answer]: A. No partnering — we build the platform and buy components. Not a consideration.

---

## Q7. How should the vendor research already in the repository be treated?

`docs/vendors.md` is dated August 2026 and labels each figure by confidence
(verified / vendor claim / third-party / not found).

A. Treat it as the authoritative input — cite it and do not re-research vendor specifics in this stage.
B. Treat it as authoritative for vendor detail, but add fresh market-level research (sizing, trends, regulatory direction) that it does not cover.
C. Re-verify its key claims with fresh research, since vendor pricing and compliance posture move quickly.
D. Not yet decided — use your judgement on where re-verification is worth the effort.
X. Other (please specify)

[Answer]: B. Treat it as authoritative for vendor detail, but add fresh market-level research (sizing, trends, regulatory direction) that it does not cover.

---

## Q8. What is the intended commercial horizon for this analysis?

Market sizing needs a target period to be meaningful.

A. Pilot-stage only — size the immediate opportunity among AI Thinkers' existing clients, not the general market.
B. 2–3 year horizon — standard SOM framing for a new entrant.
C. Both — an immediate serviceable figure for the pilot and a 2–3 year obtainable figure for the product.
D. Not yet decided — the analysis should present the market picture without committing to a capture target.
X. Other (please specify)

[Answer]: D. Not yet decided — the analysis should present the market picture without committing to a capture target.

_Recorded note: the human answered "not sure", which is recorded as the explicit not-yet-decided option rather than resolved into a horizon._

---

## Consolidated Summary Confirmation

Summary of all answers:

- Position the analysis against vertical healthcare AI vendors **and** the horizontal receptionist platforms — the set a clinic would realistically shortlist. Developer platforms and India-only vendors are not the primary comparison set. [Q1]
- Evaluate a hybrid pricing model: managed-service retainer for pilots, converting to per-clinic subscription at productisation. [Q2]
- Size India and the US equally. The sizing must not pre-judge which market the pilot targets. [Q3]
- Table stakes are 24/7 answering, appointment booking, and call transfer. Multilingual/Hinglish handling, compliance depth, and EHR integration are treated as differentiators. [Q4]
- Buying STT, TTS, and telephony is settled. The orchestration choice (LiveKit vs Pipecat vs in-house) is re-opened and must be argued rather than inherited. The human delegated this choice to the orchestrator's recommendation. [Q5]
- Partnering is not a consideration. The assessment covers build and buy only. [Q6]
- `docs/vendors.md` is authoritative for vendor-level detail; this stage adds fresh market-level research (sizing, adoption trends, regulatory direction) that it does not cover. [Q7]
- No capture target is committed. The analysis presents the market picture without claiming an obtainable share. [Q8]

**Ambiguity resolved without a follow-up question:** Q5 re-opens the orchestration
choice while Q7 makes the vendor document authoritative for vendor detail, and
orchestration is vendor detail. These are read as narrower-overrides-broader: Q7
governs component vendors (telephony, STT, TTS), and Q5's explicit carve-out
governs orchestration, which is argued fresh in `build-vs-buy.md`.

**Tension the analysis must test rather than assert:** Q4 classifies multilingual
handling as a differentiator, but Q1's competitor set includes a horizontal
platform that already ships multi-language answering with automatic language
detection. The competitive analysis has to establish whether multilingual is
genuinely an edge, or only an edge for the specific Indic-language and
code-switching cases — it cannot simply assert the classification.

**Consequences worth stating plainly:**

- Q3 and Q8 together mean the sizing is deliberately non-committal on both market
  and capture. The launch-jurisdiction question raised as a Major finding at
  intent capture therefore stays open past this stage and moves to feasibility.
- Q6 means India's regulatory burden — DLT registration and 1600-series
  numbering, which `docs/vendors.md` records as work no provider does on a
  customer's behalf — is carried entirely in-house in the build-vs-buy costing.

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
