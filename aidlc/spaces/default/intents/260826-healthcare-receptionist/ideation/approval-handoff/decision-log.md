# Decision Log — Ideation Phase

Every decision taken across the six Ideation stages, with what it was decided
against and what it cost. Ordered by stage. Decisions marked **deferred** were
put to the human and explicitly left open rather than resolved — those are
recorded as decisions too, because deferring is a choice with consequences.

## Intent Capture (1.1)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D1.1 | The problem is front-desk overload causing burnout and turnover | Lost revenue from unanswered calls; a productised offering for AI Thinkers | Positions the product against staff cost, not revenue capture |
| D1.2 | Customer segment follows existing healthcare relationships | Small independent clinics; mid-size multi-location groups | No segment criteria exist to design against |
| D1.3 | Success = call answer rate, appointments booked/no-shows, staff hours saved | Commercial metrics (paying clinics, revenue, conversion) | Commercial success is explicitly not a measure of this initiative |
| D1.4 | Staff time leads; captured calls are a side effect | Captured revenue leading; equal weight | Determines what the product is sold on |
| D1.5 | Six assumptions accepted rather than converted to questions | Converting them to follow-ups | Jurisdiction and success targets stayed open into later stages |
| D1.6 | **Deferred:** no pilot clinic named | — | Became the critical path item D-01 |

## Market Research (1.2)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D2.1 | Position against vertical healthcare AI plus horizontal receptionist platforms | Vertical only; all three layers; India vendors only | Comparison set matches what a clinic would shortlist |
| D2.2 | Hybrid pricing — managed-service retainer converting to subscription | Pure subscription; pure retainer; usage-based | Matches the managed-service-first business model |
| D2.3 | Size India and US equally; do not pre-judge | Either market first; recommend one | Jurisdiction stayed open into feasibility |
| D2.4 | **No market size produced** | Quoting one of the analyst figures | Analyst estimates span 4×; a figure would have been false precision |
| D2.5 | Multilingual reclassified from differentiator to table stakes; the real edge narrowed to Indic code-switching | Asserting multilingual as the differentiator | A competitor already ships 10+ languages at SMB pricing; the original claim would not survive a buyer conversation |
| D2.6 | Buy STT/TTS/telephony; **re-open orchestration** | Confirming LiveKit outright; re-examining the whole stack | Human delegated this to the orchestrator's recommendation |
| D2.7 | Recommend LiveKit, conditional on a spike | Pipecat, which the two strongest India vendors already integrate with | Single-core economics outweighed free adapters; needs D-03 to confirm |
| D2.8 | No partnering | White-label; distribution; India compliance partnering | India regulatory burden carried entirely in-house |

## Feasibility (1.3)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D3.1 | **Deferred:** EHR systems unknown | — | R-02; blocks scoping the differentiator |
| D3.2 | **Deferred:** launch jurisdiction unknown | India first; US first; both | R-03; both regimes carried through design |
| D3.3 | No fixed budget or deadline; funded from services revenue | A deadline or budget ceiling | Removes the forcing function; feasibility assessed against capacity |
| D3.4 | AWS already in use with existing accounts | Other cloud; none established | Helps the US path via account-wide BAA; **does not help the India voice path** |
| D3.5 | Orchestration spike runs during Inception, in parallel | Blocking before Inception; skipping it | Its urgency depends on the unresolved jurisdiction |
| D3.6 | Compliance counsel engaged before real patient data, not before architecture | Counsel before architecture freeze | R-04 — accepts rework risk on compliance architecture |

## Scope Definition (1.4)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D4.1 | **No EHR integration in the MVP**; agent owns its calendar | Full integration; read-only integration | Only buildable option today; concedes healthcare depth; raises the calendar-source-of-truth question |
| D4.2 | All four capabilities in scope | Three (defer outbound); two | Outbound pulls DLT registration onto the critical path |
| D4.3 | Both US and India tenants at MVP | One region, region-pinnable; one region only | R-03 becomes Accept — double compliance surface, knowingly |
| D4.4 | Full multi-tenancy from day one | Single-tenant; tenant-aware only | Avoids a PHI-boundary retrofit; costs build time one clinic won't exercise |
| D4.5 | Internal config plus read-only clinic view | Internal only; clinic self-service | The clinic view is what makes the pilot demonstrable |
| D4.6 | Walking-skeleton-first sequencing | Risk-first; value-first | Risk-first is blocked on D-01; skeleton is not blocked on anything |
| D4.7 | Excluded: other verticals, all payments, all clinical advice | Narrower exclusions | PCI DSS avoided outright; TCPA healthcare exemption protected |
| D4.8 | MoSCoW, not WSJF or RICE | Either scoring framework | No cost of delay, reach or effort figures exist to score with |
| D4.9 | Indic code-switching ranked Should, not Must | Must, as the stated differentiator | No evidence establishes the quality is achievable |

## Team Formation (1.5)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D5.1 | One engineer, residual time, no outside help | Specialist contractors for gaps; broader contracting | The scope-versus-capacity gap becomes an issue |
| D5.2 | Gap recorded as an **issue**, not a risk | Scoring it as a risk | It is the current state, not something that might occur |
| D5.3 | Three template artifacts omitted (RACI, capacity agreement, gap remediation) | Producing them | Each would convey structure the project does not have |
| D5.4 | Options presented without a recommendation | Recommending a scope cut | The scope was approved knowingly by the person who would change it |

## Rough Mockups (1.6)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D6.1 | Conversation and screens both treated as design surfaces | Conversation-first; screens-only | The call is where the product lives; patients never see a screen |
| D6.2 | **Deferred:** screen set and clinic-view audience | — | Resolved by deferring to the approved scope document |
| D6.3 | One recovery attempt, then transfer | Immediate transfer; message-first | Balances patient experience against the front-desk load the product exists to relieve |
| D6.4 | Message and callback when unstaffed | Callback slots; clinic's existing after-hours path | Completes the failure policy; creates an obligation on the clinic |
| D6.5 | **Deferred:** accessibility standard | WCAG AA committed; best-effort | AA applied as a labelled default; voice access gap left open → became R-10 |
| D6.6 | No hours-saved figure in the clinic view | Displaying it | No baseline exists to compute it from |
| D6.7 | Gate rejected, accessibility notes completed, re-reviewed | Approving with the finding recorded | First rejection of the workflow; the review loop worked as designed |

## Approval & Handoff (1.7)

| # | Decision | Rejected alternative | Consequence |
|---|---|---|---|
| D7.1 | **GO as approved**, full scope | Reduced scope; pause after Inception; no-go | Proceeds at maximum scope against one engineer on residual time |
| D7.2 | Non-voice access gap promoted to a named risk (R-10) | Leaving it as a wireframe assumption | A patient-access issue now sits where risks are tracked |
| D7.3 | R-03 changed to Accept; R-07 superseded | Leaving both as scored | Keeps the register honest about what changed and why |
| D7.4 | **Deferred:** whether the market research justifies the investment | Any of the offered readings | The brief states what the research supports without manufacturing a verdict |
| D7.5 | **Deferred:** first action after the gate | Starting D-01; gating Construction on it | The critical path item is unsequenced |

## Practices learned and persisted

Six rules now in `aidlc/spaces/<space>/memory/project.md`, each from a specific
failure or judgement during these stages:

| From | Rule |
|---|---|
| 1.1 | Verify a confirmation's audit receipt before treating an answer as human-confirmed |
| 1.2 | Refuse to produce a figure the evidence cannot support, and say why |
| 1.3 | Read gate-fired sensor results after opening the gate, before presenting approval |
| 1.4 | Record a scope reduction order at the moment scope is set |
| 1.5 | State why a template section does not apply rather than filling it in |
| 1.6 | Describe what an artifact contains, not what was intended for it |

## Corrections made during Ideation

Recorded because they are part of the honest history of this phase.

- **Intent capture's summary confirmation had never been human-confirmed.** A
  prior session wrote the answer itself; the guard refused the receipt. Reset and
  re-confirmed.
- **Intent capture was approved without reading gate-fired sensor results**, which
  had failed with 15 findings. Fixed later; became the practice from 1.3.
- **A backward-jump cost was understated at a gate** — described as a stage redo
  when it would have reset 29 stages. Corrected before the human acted on it.
- **Three ideation stages carry stale completion receipts** after the sensor fix
  edited already-approved artifacts. Advisory; the artifacts are more correct than
  the receipts.
- **Rough mockups claimed complete accessibility notes it did not have.** Caught
  by the reviewer, rejected at the gate, fixed and re-reviewed.
