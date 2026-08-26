# Intent Statement — Healthcare Receptionist Voice Agent

## Sources

- [desc] Initial description: "Build the platform core and the healthcare receptionist pack described in BRIEF.md and docs/vendors.md: a multi-tenant AI voice agent platform whose first vertical answers clinic calls 24/7, books and reschedules appointments, does patient intake, and runs outbound reminder calls, deployable to both US (HIPAA) and India (DPDP) tenants."

## Problem Statement

Clinic front-desk staff are overloaded with repetitive scheduling calls, and that
overload causes burnout and staff turnover. [Q1]

Staff time is the primary value story: the agent exists to take repetitive load
off the front desk. Calls and appointments captured by the agent are a welcome
side effect rather than the headline claim. [Q10]

## Target Customer

The customer segment follows AI Thinkers' existing healthcare relationships
rather than a segment chosen in the abstract. [Q2]

The buying clinic is served alongside two end-user groups who experience the
agent directly: the clinic's practitioners and its patients. [Q5]

## Success Metrics

| Metric | Why it matters | Source |
|---|---|---|
| Call answer rate, and reduction in missed or abandoned calls | Calls that never get answered are the visible symptom of front-desk overload | [Q3] |
| Appointments booked or recovered by the agent, and reduction in no-shows | Measures whether the agent completes the scheduling work rather than merely answering | [Q3] |
| Front-desk staff hours saved per clinic per week | The primary value story is staff time, so hours saved is the headline measure | [Q3][Q10] |

Commercial metrics — paying clinics, revenue per clinic, pilot-to-paid
conversion — were deliberately not selected as success measures for this
initiative. [Q3]

## Initiative Trigger

The trigger is market opportunity: voice AI quality has crossed the threshold
where patients accept it. This initiative is not driven by a specific client
request, a competitive window, or an internal services-to-product strategy.
[Q4]

## Initial Scope Signal

**Workflow-selected scope:** `feature` [scope]

**User-confirmed product boundary:** the `feature` scope was confirmed as-is —
platform core plus the healthcare receptionist pack, full lifecycle through to
operations. [Q8]

The initial description states the platform core is multi-tenant, that the
healthcare receptionist is its first vertical, and that the vertical answers
clinic calls 24/7, books and reschedules appointments, does patient intake, and
runs outbound reminder calls. It further states the platform is deployable to
both US (HIPAA) and India (DPDP) tenants. [desc]

No specific pilot clinic exists yet. The relationships are known to exist and one
will be selected later, so the pilot clinic is a real stakeholder role with no
named party behind it today. [Q9]

## Assumptions & Open Questions

- Numeric targets and measurement windows for the three success metrics are not
  yet defined, so success is currently directional rather than testable.
  [assumption]
- The regulatory frameworks named in the initial description (US HIPAA, India
  DPDP) have not been confirmed against a specific deployment jurisdiction or
  named customer, because no pilot clinic is selected yet. [assumption]
- Whether the first deployment targets the US tenant, the India tenant, or both
  at once is not established. [assumption]

## Review

**Verdict:** READY
**Reviewer:** aidlc-product-lead-agent
**Date:** 2026-08-26T11:29:19Z
**Iteration:** 1

### Findings

| # | Severity | Location | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Major | intent-statement.md § Success Metrics | The three retained success metrics (call answer rate, appointments booked/no-show reduction, staff hours saved) carry no numeric target or measurement window — the artifact itself labels this `[assumption]`, so success is directional, not testable, contrary to the ideation-phase rule that success metrics must be measurable. | Carry this forward as a mandatory follow-up in requirements-analysis: attach a number and a time window to each metric before it is used as an acceptance criterion. |
| 2 | Major | intent-statement.md § Initial Scope Signal / Assumptions | The initiative spans two distinct regulatory regimes (US HIPAA, India DPDP) but which regime actually applies is unresolved — no pilot clinic or jurisdiction is selected yet, and this is carried only as an accepted assumption with no named owner or resolution trigger. For a healthcare initiative this is a compliance-relevant unknown, not a cosmetic gap. | Before architecture/compliance work begins, resolve at minimum which jurisdiction the first deployment targets (per open assumption 3), since HIPAA and DPDP impose materially different technical and process controls. |
| 3 | Minor | intent-statement.md § Target Customer | The target customer is defined only as "whichever healthcare clients AI Thinkers already has" (Q2 answer C) — no criteria for clinic size, specialty, or location. This is a legitimate, explicitly confirmed answer, not a sourcing defect, but it leaves scope-definition with no concrete segment to design against. | When a pilot clinic is selected, capture its profile (size, specialty, location) and use it to sharpen the customer definition rather than relying on "whichever client" indefinitely. |
| 4 | Minor | stakeholder-map.md § Key Stakeholders | Three of six stakeholder rows (AI Thinkers leadership, clinic practitioners, patients) have interest recorded as `Unknown (open question)`. Correctly labeled per the grounding contract, but half the stakeholder table currently carries no substantive interest data. | Elicit these interests in a follow-up before delivery-planning needs to prioritize against stakeholder value. |
| 5 | Minor | intent-capture-questions.md Q1, Q3, Q4 | These questions omit an explicit "Not yet defined" / "None" style option that Step 2 of the stage definition calls for "as appropriate." The user answered confidently in each case, so this had no practical effect here, but a narrower or less-formed intent could have been forced into an invented choice. | Add a "Not yet defined" style option to substantive questions as a standing practice for future runs of this stage. |

### Summary

The two artifacts are well-grounded: every substantive claim carries a resolvable `[Q<n>]`/`[desc]`/`[scope]`/`[assumption]` tag, no unselected option is turned into an exclusion, both `## Assumptions & Open Questions` sections are populated, and every retained assumption traces to the completed `## Assumption Confirmation` in the questions file. The main open risk is that two of the six accepted assumptions — unmeasurable success metrics and an unresolved regulatory jurisdiction — are exactly the kind of gap that should be closed early in a healthcare initiative; they are correctly disclosed rather than hidden, so this is decision support for the approval gate rather than a blocker.
