# Vendor landscape — telephony, STT, TTS, orchestration, compliance

Research pass: August 2026. Input for the NFR Requirements and NFR Design stages.

**How to read this.** Prices and latency figures move constantly and most vendors
gate real numbers behind sales. Every figure below is labelled by how it was
established:

- **Verified** — read off the vendor's own docs or pricing page.
- **Vendor claim** — the vendor asserts it; no independent confirmation.
- **Third-party** — from an aggregator or comparison site, not the vendor.
- **Not found** — searched for and could not confirm. Not the same as "absent",
  but treat it as absent until someone confirms otherwise.

Nothing here is contractual. Confirm pricing, BAA scope, and region availability
directly with each vendor before committing. The compliance section is research,
not legal advice — a US healthcare-compliance attorney and an Indian
data-protection/telecom counsel need to review before architecture is frozen.

---

## The three findings that drive everything else

**1. Call audio is PHI on its own.** HHS's 18 Safe Harbor identifiers include
both telephone numbers and *biometric identifiers, including voice prints*. So a
patient call is PHI twice over — by content, and because raw voice is itself an
identifier. Transcripts too. This is what forces the BAA chain.

**2. A BAA does not flow down to subcontractors.** Each vendor touching PHI needs
its own executed BAA. For a voice pipeline that means telephony + STT + LLM + TTS
+ orchestration + hosting + logging + observability, individually. One gap breaks
the chain. This single fact eliminates several otherwise-attractive vendors.

**3. No single vendor covers US healthcare and India well.** Not one. The US-strong
vendors have no India region and often no Indic languages; the India-strong
vendors have no HIPAA story at all. **Per-region vendor selection behind a stable
internal interface is not an architectural nicety — it is the only configuration
that works.** Everything below reinforces this.

---

## Telephony

The hard requirement is **bidirectional media streaming** — a WebSocket carrying
raw audio both ways. A provider that only does classic IVR/TwiML cannot host an
LLM voice agent. This alone eliminates several established Indian CPaaS vendors.

### US

| Provider | Streaming | Price (verified) | HIPAA BAA | India |
|---|---|---|---|---|
| **Twilio** | Media Streams + ConversationRelay | $0.0085/min in, $0.014/min out | **Yes** — Media Streams and ConversationRelay both explicitly HIPAA-eligible (official PDF, June 2026); needs Security or Enterprise Edition | Numbers yes ($0.0699/min out); **no India edge** — nearest PoP Singapore/Tokyo |
| **Telnyx** | Media Streaming over WebSockets ($0.0035/min) | $0.002/min base + SIP trunking | Yes — claims conduit exception, also signs BAAs; no tier gate found | No India PoP found |
| **Plivo** | Audio Streaming API, native bidirectional | **India ₹0.38/min both ways**; US $0.0055–0.0115/min | Yes — **Enterprise only** | **Best dual-market option.** India numbers require an India data region account |
| SignalWire | Stream via `<Connect>` | $0.0066–0.0147/min + $0.16/min AI runtime | Yes, **all tiers** ($100–1,000/mo BAA fee, third-party) | **None.** Numbers in 6 countries, India not among them |
| Vonage | WebSocket Voice API + Pipecat serializer | Pricing pages 403'd — **not found** | Yes, Enterprise; unclear if WebSocket path is in BAA scope | Not found |
| AWS Connect / Chime SDK | Via Kinesis Video Streams, not raw WebSocket | Connect ~$0.018/min + telephony | Yes — covered by account-wide AWS BAA, no extra fee | **None.** No ap-south-1 for Connect; India absent from AWS's entire telecom coverage PDF |

### India

| Provider | Streaming | Notes |
|---|---|---|
| **Exotel** | **AgentStream / Voicebot Applet — confirmed, mature.** Bidirectional WebSocket, PCM 8/16/24kHz, published OpenAI Realtime and Pipecat integrations, sample repos | Strongest India option. ISO 27001 only — **no HIPAA, no SOC 2 found**. Pricing sales-gated. States data stays in-country for BFSI |
| **Ozonetel (KooKoo)** | Confirmed — `<stream>` tag opens bidirectional WS, `clearBuffer` barge-in, sub-200ms claimed | Real and documented, but the companion SDK sits in a non-Ozonetel GitHub org with 0 stars, created April 2026 — reference implementation, not proven in production |
| Knowlarity | **Not found.** Only a call-*metadata* streaming API. Probed several likely URLs, all 404 | Owned by **Gupshup** (Feb 2022, $100M) — not Freshworks, and SmartFlo is Tata's unrelated product. No ISO/SOC/HIPAA claims found anywhere |
| Kaleyra (Tata) | **Not found.** Click-to-Call + IVR Flow Builder only | Classic IVR CPaaS, not a streaming media API |
| MyOperator | **Not found.** Dashboard-configured voicebots | SMB call-management SaaS, not developer CPaaS |

### India regulatory — this bites immediately

TRAI's February 2025 TCCCPR amendment **bans ordinary 10-digit numbers for
commercial calling**. Numbering series is now mandatory and CLI-traceable:

- **140-series** — promotional/telemarketing
- **1600-series** — transactional/service calls

Appointment reminders and clinic follow-ups are transactional, so **1600-series**
is our path. Penalties escalate ₹200k → ₹500k → ₹1M per instance, and unregistered
promotional calling from a personal SIM triggers immediate disconnection plus a
**two-year cross-operator blacklist** shared via DLT.

Also: explicit consent for commercial calls now expires in **7 days**; the
complaint threshold for enforcement dropped to 5 complaints in 10 days. **CNAP**
(verified caller-name display from KYC data) has been rolling out since late 2025 —
outbound calls will display whatever name is registered against the number, so
properly KYC'd DLT-registered numbers directly affect whether our agent's calls
look trustworthy or get flagged as spam.

**No provider registers DLT on your behalf.** Twilio, Telnyx, Plivo, Exotel — all
document it as the customer's own job on carrier portals. Budget for it.

---

## Speech-to-text

The decisive axis is **Hinglish**. Indian phone conversations code-switch
mid-sentence, and most ASR handles this badly. Second axis: **8kHz telephony
audio**, which is the actual input — not the clean studio audio every benchmark uses.

**No vendor publishes an Indian-accented-English or 8kHz-telephony WER benchmark.**
Five separate research passes looked. Every published accuracy number is
general/English-weighted. This is a real gap in the market, and it means **we will
have to run our own bake-off on real call recordings** before choosing.

| Vendor | Streaming latency | Price | Hinglish | India region | BAA |
|---|---|---|---|---|---|
| **AssemblyAI** | 317ms P50 emission (verified, published methodology) | $0.15/hr streaming | **Best documented** — explicit mid-sentence Hindi-English example in docs, on by default | Not found | **Self-serve, no sales call, no premium** — best-in-class |
| **Deepgram** | ~300ms; Flux EndOfTurn 100–500ms | $0.0077/min Nova-3 | Hindi in `multi` code-switch mode; other Indic single-language only. **No Malayalam at all** | EU + Australia only | On request, via sales |
| **ElevenLabs Scribe** | ~150ms (vendor claim) | $0.39/hr realtime | Not documented | **India region confirmed** (`in.residency.elevenlabs.io`) — only global vendor with one | Enterprise only |
| **AWS Transcribe** | No published figure | $0.01/min streaming | Multi-language ID with explicit Hindi-English example — but segment-level, not word-level | **ap-south-1 Mumbai confirmed, streaming + batch** | Yes, HIPAA-eligible |
| Google Chirp 3 | No published figure | ~$0.016/min | Not documented | asia-south1 partially confirmed | Yes — but **must disable data logging** |
| Azure | Not found | ~$0.0167/min | **Explicitly disclaims it** — docs state continuous LID "doesn't support changing languages within the same sentence" | Central India exists; Speech-specific availability unconfirmed | Bundled by default; Speech's in-scope status unconfirmed |
| **Sarvam (Saaras/Saarika)** | Not found | **₹30/hr** (₹45 with diarization) | Yes — `codemix` output mode | Not found | **None found** |
| **Gnani (Prisma v2.5)** | **P95 < 200ms** — only hard number in the whole category | Sales-gated | Yes — Hinglish, Tanglish, Benglish named explicitly; 8kHz-optimised | Not found | None found |
| Bhashini / AI4Bharat | Streaming for only 4 languages | Free (government) | Not found | Self-hostable — full control | None |

Two traps worth naming. **AWS's streaming PII redaction covers only en-US, en-AU,
en-GB, es-US — not Hindi or any Indic language**, and it cannot be combined with
multi-language identification anyway. So on AWS you can have Hinglish *or*
redaction, not both. And **AI4Bharat's own roadmap admits 8kHz telephony
optimisation is still future work**, which undercuts Bhashini for real phone audio
despite its unmatched 22-language coverage.

---

## Text-to-speech

Latency matters most here — above roughly 300ms time-to-first-audio, conversation
stops feeling live. One independent benchmark (Coval, May 2026) measured several
vendors under identical conditions, which is worth more than any vendor claim:

**Cartesia Sonic-3 188ms → ElevenLabs Turbo v2.5 264ms → Flash v2.5 288ms →
Deepgram Aura-2 313ms → Rime Mist-v3 337ms.**

Note how far vendor claims sit from measured reality: Deepgram claims sub-200ms
TTFB and measured 313ms TTFA; Rime claims 37–96ms on an isolated H100 and measured
337ms live. Different things are being measured, but the live numbers are what
users hear.

| Vendor | TTFA | Price | Indic languages | Code-switching | BAA | India residency |
|---|---|---|---|---|---|---|
| **Cartesia Sonic-3** | **188ms (independent)** | ~$5–37/M chars | **9 Indic** incl. Hindi, Tamil, Telugu, Bengali, Marathi, Kannada, Malayalam, Gujarati, Punjabi | Not documented | Enterprise | **On-prem, VPC, and air-gapped**; India-resident via Blue Machines partnership |
| **ElevenLabs Flash v2.5** | 264–288ms (independent) | $0.05/1k chars | 12 Indian languages/accents (v3) | `hinglish_mode` exists but is an **Agents-platform** feature, and language is fixed per call | Enterprise + Zero Retention Mode | **India region** (Enterprise); on-prem available |
| **Rumik Silk (Mulberry)** | 162ms vendor claim; <200ms third-party on H100 | **₹0.50/1k chars** — cheapest by far | Hindi, Hinglish, Tamil, Telugu, Bengali, Marathi | **Strongest claim in the market** — explicit mid-sentence switching, accent retained across switches | **None. Searched explicitly — no HIPAA, BAA, or healthcare compliance mention anywhere** | Not found |
| Deepgram Aura-2 | 313ms (independent) | $0.03/1k chars | **None.** English, Spanish, German, French, Dutch, Italian, Japanese only | N/A | On request | US + EU, no India |
| Google Chirp 3 HD | Not published | $30/M chars | 10 Indic incl. Punjabi (preview) | Not documented for TTS | **Yes, TTS explicitly HIPAA-covered** | India endpoint unconfirmed |
| Azure Neural | Not published | ~$16/M chars | Broad — Hindi with 18 emotion styles, Tamil, Telugu, Bengali, Marathi, more | **No.** Guidance is to switch voices via SSML | In-scope status unconfirmed | **Central India confirmed** |
| AWS Polly | Not published | $16/M neural, $30/M generative | **Hindi + Indian English only.** No Tamil/Telugu/Bengali/Marathi | Bilingual voices (per-request, not mid-sentence) | Yes, HIPAA-eligible | Mumbai yes — but **Generative engine not available there** |
| Sarvam Bulbul | Not found | Pricing page 403'd | 11 Indic | Code-mixed supported | Not found | Not found |
| Reverie | Not found | Sales-gated | 11 Indic + Indian English | Not mentioned | Not found | **On-prem offered**. Note: their site had an **expired TLS certificate** during research |
| Rime Coda | 337ms (independent) | $0.05/1k chars | Hindi only (2 voices) | **Regressed** — Arcana advertised Hindi/English code-switching; Coda docs now state each voice is locked to one language. Arcana sunset Aug 15 2026 | HIPAA since Feb 2024, SOC 2 Type II | US only; **on-prem available** |

**Rumik is the sharpest trade-off in this document.** It is roughly 10× cheaper
than ElevenLabs, has the best code-switching story anyone publishes, ships an
official Pipecat package, and is built for exactly our India market. It also has
**no HIPAA posture whatsoever** — and its terms of service actively disclaim
clinical use and prohibit simulating a medical professional. That is a reasonable
India-market TTS choice and an unusable US-healthcare one. Which is precisely why
TTS must be swappable per deployment.

---

## Orchestration

**Recommendation: self-host LiveKit Agents. Build multi-tenancy and the vertical
packs ourselves. Use LiveKit Cloud as the MVP bridge.**

LiveKit gives us WebRTC + SIP (GA 2025), a multilingual turn-detection model,
telephony noise cancellation, and real interruption handling. Apache 2.0, no
platform fee self-hosted. LiveKit *Cloud* has an **ap-south (Mumbai) region** and
offers **HIPAA eligibility + SOC 2 Type II + a signed BAA at Scale tier** — so the
MVP can run managed and compliant, then migrate to self-hosted when volume or
residency demands it. Self-hosting only becomes cost-favourable above roughly 1.5M
agent-minutes/month against ~$15.5k/mo of fixed infra and SRE.

Why not the managed platforms:

- **None have native multi-tenancy.** Vapi, Retell, Bland, Synthflow — the market's
  own workaround is third-party wrapper products (Vapify, VapiWrap, VoiceAIWrapper).
  If we must build the tenant layer regardless, better to build it on infrastructure
  we control.
- **None showed an India region.** This alone disqualifies the tier for our second
  market.
- **HIPAA is Enterprise-gated everywhere** — Vapi ~$1–2k/mo add-on, Retell needs
  ~$3k/mo usage, Bland Enterprise-only. Bland is the notable exception on
  architecture: it runs its own models and offers on-prem/VPC.
- Pipecat is the strongest alternative and has the larger community (13.4k stars),
  but its maintainers have an open issue acknowledging the self-hosted production
  path lacks battle-tested blueprints; it's optimised for Daily's managed cloud.
- **Vocode is stalled** and seeking maintainers — rule it out.

**Cascaded pipeline, not speech-to-speech.** Speech-to-speech (OpenAI Realtime,
Gemini Live, Nova Sonic) wins on raw latency — 300–500ms floor versus 1–3s typical
cascaded — but loses on everything we need. Cascaded gives text at every stage, so
each component is independently BAA-able and auditable, prompts and guardrails work
normally, and vendors stay swappable. Speech-to-speech ties us to one vendor's BAA
scope, and the cautionary example is concrete: **OpenAI's Realtime audio modality
was reported as not on its BAA-covered-services list as of May 2026.** Also note
Azure OpenAI's Realtime API was explicitly *not* HIPAA-covered while in preview.

If we ever want speech-to-speech for a latency-critical, low-tool-surface flow,
**Amazon Nova Sonic** has the best compliance story — it runs inside Bedrock, data
stays in our AWS account, we hold the KMS keys.

---

## Compliance

### US — HIPAA

Current Security Rule technical safeguards: access control, audit controls,
integrity controls, transmission security. Encryption at rest and in transit is
currently **addressable, not mandatory**.

That is about to change. The **January 2025 NPRM** would eliminate the
addressable/required distinction entirely: mandatory encryption, mandatory MFA,
workforce access termination within 1 hour, written asset inventory and network
maps, vulnerability scans every 6 months, annual penetration testing, network
segmentation, 72-hour restoration capability, annual verification of business
associate security. HHS estimates ~$9B industry-wide first-year cost.

**Status: not finalised. Reporting indicates the target slipped to 2027.** The
current rule still governs. But the direction is unambiguous, and OCR revived
compliance audits in March 2025 — so build to the proposed standard now rather than
retrofit. Separately, 42 CFR Part 2 alignment had a **February 16, 2026** deadline
if we ever touch substance-use-disorder records.

**Vendor BAA availability** (verify each directly before contracting — these lists
change, especially for realtime/voice APIs):

| Vendor | BAA | Gate |
|---|---|---|
| AWS (Bedrock, Transcribe, Polly, Connect) | Yes | Self-serve via Artifact, no fee, account-wide |
| Azure | Yes | Bundled in licensing by default |
| Google Cloud | Yes | Org-level BAA + must disable data logging |
| Anthropic | Yes | Enterprise/sales; HIPAA must be activated in Enterprise settings |
| OpenAI | Yes | Zero-retention endpoints only; **Realtime audio modality reportedly excluded** |
| AssemblyAI | Yes | **Self-serve in dashboard, minutes, no premium** |
| Retell | Yes | Self-serve click-agreement |
| Deepgram | Yes | On request via sales |
| Twilio | Yes | Security or Enterprise Edition |
| Plivo, ElevenLabs, Cartesia, LiveKit, Vapi | Yes | Enterprise tier only |
| SignalWire | Yes | All tiers, for a monthly BAA fee |
| **Rumik, Sarvam, Gnani, Exotel, Reverie** | **None found** | India-market vendors have no HIPAA posture as a category |

### US — call handling

**TCPA.** The FCC's February 2024 Declaratory Ruling holds that **AI-generated
voices are "artificial or prerecorded"** under TCPA — no AI exemption exists. But
the **2012 healthcare exemption is genuinely favourable to us**: calls delivering a
health-care message by or on behalf of a HIPAA covered entity need only **prior
express consent** (not written) to reach a cell phone, and appointment reminders,
lab results, pre-op instructions, post-discharge follow-up, and prescription
notifications are all explicitly covered. That exemption **evaporates the moment
marketing content enters the call** — which is a hard product constraint on the
reminder agent, not just a legal note.

An FCC NPRM proposing mandatory in-call AI disclosure remains **unfinalised**.

**Recording consent.** Roughly 11–12 all-party-consent states, with sources
disagreeing at the margins (California, Delaware, Florida, Illinois, Maryland,
Massachusetts, Montana, Nevada, New Hampshire, Pennsylvania, Washington
consistently; Connecticut and Oregon contested). Rather than geo-detecting caller
state law in real time, **disclose on every call nationwide**.

**AI disclosure.** Already law in places:
- **California AB 2905**, effective Jan 1 2025 — verbal disclosure at the *very
  start* of any robocall using an AI-generated voice, before the message. $500 per
  violation.
- **Utah UAIPA**, effective May 2024 — proactive disclosure is mandatory for
  interactions involving **licensed/regulated professions**, which a clinic agent
  falls squarely inside.
- **Colorado CAIA** — postponed to June 30 2026, penalties up to $20,000.
- **Maine LD 1727** — effective Sept 24 2025.

Practical floor: **verbal AI disclosure at the start of every call, everywhere.**

### India — DPDP

The **DPDP Rules 2025 were notified around November 13, 2025** and are in force,
with obligations phasing in over 18 months — remaining provisions land by roughly
**May 2027**. So there is runway, but the clock is running.

Obligations that hit our architecture directly: reasonable security safeguards with
**logs retained a minimum of one year**; breach notification to affected people
immediately and a **detailed report to the Data Protection Board within 72 hours**;
erase personal data once the purpose is fulfilled; publish DPO contact details.
**Consent Managers must be Indian-incorporated companies** — relevant if we
integrate with ABDM/ABHA.

**DPDP does not mandate data localisation.** Section 16 uses a negative-list model —
transfer is permitted except to countries the government specifically restricts.
The localisation concepts from the 2019/2021 drafts were dropped. *Confidence:
low-medium — primary-source analysis could not be fetched during research. Confirm
with Indian counsel before finalising hosting.* Note that **RBI's payment-data
localisation is real but separate** and only bites if we process payments.

**ABDM Health Data Management Policy specifics could not be verified** —
abdm.gov.in returned no usable content. If a clinic integrates ABHA-linked records,
this needs its own research pass.

### Certifications

SOC 2 is **not legally required** to sell into US healthcare — it's a procurement
expectation. Small clinics may not ask; enterprise health systems will, and usually
want Type II. Type I is roughly 2–3 months and $10–40k; Type II needs a 3–12 month
observation window at $20–60k plus tooling. *(Industry norms — could not verify
against a live source; get actual quotes.)* ISO 27001 carries more weight than
usual for us because Indian and international enterprise buyers ask for it by
default. **HITRUST is not worth it pre-PMF** — $50–150k and 12–18 months, pursue
only when a specific large customer demands it.

---

## What this means for the build

**Region-pinned deployments with per-region vendor selection.** Not a preference —
the only configuration the vendor landscape permits.

A defensible starting shortlist, to be validated by our own bake-off:

| Layer | US (HIPAA) | India (DPDP) |
|---|---|---|
| Telephony | Twilio (Media Streams HIPAA-eligible, verified) | Exotel AgentStream, or Plivo for one vendor across both |
| STT | AssemblyAI (self-serve BAA, best Hinglish docs) or AWS Transcribe | Sarvam or Gnani; AWS Transcribe if Mumbai residency dominates |
| LLM | Bedrock or Anthropic direct (both BAA) | Same, India region |
| TTS | Cartesia (fastest measured, 9 Indic, on-prem) or ElevenLabs | Rumik (10× cheaper, best code-switching) — **never for US PHI** |
| Orchestration | LiveKit Cloud Scale (BAA, SOC 2) → self-hosted | LiveKit Cloud ap-south → self-hosted |

**Before choosing, we must run our own accuracy bake-off on real Indian call
recordings at 8kHz.** No vendor publishes telephony or Indian-accent benchmarks, so
every accuracy claim in this document is unvalidated for our actual use case. This
is the single biggest open risk in vendor selection.

### Open items needing direct vendor or counsel contact

- Exotel and Plivo per-minute voice pricing, and whether Plivo supports India number port-in
- Whether Rumik or any India TTS vendor will sign a BAA (probably not — plan around it)
- Indian counsel on DPDP Section 16 and ABDM obligations
- US healthcare-compliance counsel on the TCPA healthcare exemption boundary for our reminder flows
- Current BAA scope for OpenAI Realtime audio and Azure OpenAI Realtime, if either is ever considered
- SOC 2 quotes from 2–3 auditors
