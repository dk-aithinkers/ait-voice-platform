# Intent Capture & Framing — Questions

**Mode:** guided

## Sources

- [desc] Initial description: "Build the platform core and the healthcare receptionist pack described in BRIEF.md and docs/vendors.md: a multi-tenant AI voice agent platform whose first vertical answers clinic calls 24/7, books and reschedules appointments, does patient intake, and runs outbound reminder calls, deployable to both US (HIPAA) and India (DPDP) tenants."
- [scope] Workflow-selected scope: `feature`.

---

## Q1. What business problem is this platform solving?

A. Clinics lose revenue and patients because calls go unanswered outside office hours and during busy periods.
B. Clinic front-desk staff are overloaded with repetitive scheduling calls, causing burnout and turnover.
C. AI Thinkers needs a repeatable productised offering to sell into its existing client base instead of bespoke project work each time.
D. All of the above — a real clinic operational problem that also becomes our productised offering.
X. Other (please specify)

[Answer]: B. Clinic front-desk staff are overloaded with repetitive scheduling calls, causing burnout and turnover.

---

## Q2. Who is the customer, and what pain are they experiencing?

A. Small independent clinics (1–5 practitioners) with no capacity for a dedicated receptionist.
B. Mid-size multi-location clinic groups with inconsistent call handling across sites.
C. Whichever healthcare clients AI Thinkers already has — the segment follows the existing relationship.
D. Not yet defined — the customer segment is still to be decided.
X. Other (please specify)

[Answer]: C. Whichever healthcare clients AI Thinkers already has — the segment follows the existing relationship.

---

## Q3. Which success metrics matter most? (select all that apply)

A. Call answer rate and reduction in missed or abandoned calls.
B. Appointments booked or recovered by the agent, and reduction in no-shows.
C. Front-desk staff hours saved per clinic per week.
D. Commercial metrics — paying clinics, revenue per clinic, pilot-to-paid conversion.
X. Other (please specify)

[Answer]: A, B, C

---

## Q4. What is the trigger for doing this now?

A. Market opportunity — voice AI quality has crossed the threshold where patients accept it.
B. Existing client demand — one or more healthcare clients have asked for this.
C. Competitive window — incumbents are moving in the US and the India market is still open.
D. Internal strategy — AI Thinkers wants to shift from services revenue to a product.
X. Other (please specify)

[Answer]: A. Market opportunity — voice AI quality has crossed the threshold where patients accept it.

---

## Q5. Who are the key stakeholders?

A. Internal only — AI Thinkers leadership and the engineering team.
B. Internal plus one named design-partner clinic acting as pilot customer.
C. Internal, a pilot clinic, and that clinic's practitioners and patients as end users.
D. All of C plus external compliance advisors (US healthcare counsel, Indian data-protection counsel).
X. Other (please specify)

[Answer]: C. Internal, a pilot clinic, and that clinic's practitioners and patients as end users.

---

## Q6. Who decides scope and priority, and who influences those decisions?

A. Deepak decides; the engineering team influences.
B. Deepak decides jointly with the pilot clinic; clinic feedback drives priority.
C. AI Thinkers leadership group decides collectively.
D. Not yet decided — governance still to be established.
X. Other (please specify)

[Answer]: A. Deepak decides; the engineering team influences.

---

## Q7. Are there communication requirements or a reporting cadence?

A. Weekly written progress update to internal leadership.
B. Milestone-based demos to the pilot clinic at each phase boundary.
C. Both A and B.
D. No formal cadence — informal updates as work progresses.
X. Other (please specify)

[Answer]: D. No formal cadence — informal updates as work progresses.

---

## Q8. The workflow was started with the `feature` scope. Does that match your intended product boundary?

A. Confirm `feature` scope as-is — platform core plus the healthcare receptionist pack, full lifecycle through to operations.
B. Confirm the scope but narrow the product boundary — platform core plus healthcare pack only, with aerospace AOG and finance explicitly deferred to later initiatives.
C. Narrow further — healthcare receptionist agent only, no multi-vertical platform core in this initiative.
D. Broaden — platform core plus healthcare pack plus at least one more vertical in this same initiative.
X. Other (please specify)

[Answer]: A. Confirm `feature` scope as-is — platform core plus the healthcare receptionist pack, full lifecycle through to operations.

---

## Q9. Follow-up — does a specific pilot clinic exist today?

Raised because Q5 names "a pilot clinic" as a stakeholder, while Q4 gives the
trigger as market opportunity rather than existing client demand, and Q2 says the
customer segment follows existing relationships. Whether a named pilot exists
today determines whether the stakeholder map records a real party or an open
question, and whether the Operation phase has a real deployment target.

A. Yes — a specific clinic is identified and has agreed in principle to pilot.
B. A specific clinic is identified as a candidate, but has not yet been approached or agreed.
C. No specific clinic yet — we know the relationships exist and will select one later.
D. No — we intend to build first and find a pilot afterwards.
X. Other (please specify)

[Answer]: C. No specific clinic yet — we know the relationships exist and will select one later.

---

## Q10. Follow-up — which is the primary value story for the clinic?

Raised because Q1 frames the problem as front-desk overload (a staff-time
problem), while two of the three metrics chosen in Q3 measure call capture and
appointment conversion (a revenue problem). Both can be true, but the Problem
Statement needs to say which one leads.

A. Staff time — the agent exists to take repetitive load off the front desk; captured calls are a welcome side effect.
B. Captured revenue — the agent exists to make sure no call or appointment is lost; reduced staff load is a welcome side effect.
C. Equal weight — both are headline claims and neither leads.
D. Depends on the clinic — small clinics buy staff time, larger groups buy captured revenue.
X. Other (please specify)

[Answer]: A. Staff time — the agent exists to take repetitive load off the front desk; captured calls are a welcome side effect.

---

## Consolidated Summary Confirmation

Summary of all answers:

- The business problem is front-desk overload: clinic staff are buried in repetitive scheduling calls, causing burnout and turnover. [Q1]
- The customer segment follows AI Thinkers' existing healthcare relationships rather than a segment chosen in the abstract. [Q2]
- Success is measured by call answer rate, appointments booked or recovered and no-show reduction, and front-desk staff hours saved per clinic per week. Commercial metrics were deliberately not selected as success measures for this initiative. [Q3]
- The trigger is market opportunity — voice AI quality has crossed the threshold where patients accept it — rather than a specific client request. [Q4]
- Stakeholders are AI Thinkers internal (leadership and engineering), a pilot clinic, and that clinic's practitioners and patients as end users. External compliance counsel was not included as a stakeholder at this stage. [Q5]
- Deepak decides scope and priority; the engineering team influences. [Q6]
- No formal reporting cadence — informal updates as work progresses. [Q7]
- The `feature` scope is confirmed as-is: platform core plus the healthcare receptionist pack, full lifecycle through to operations. [Q8]
- No specific pilot clinic exists yet. The relationships are known to exist and one will be selected later, so the pilot clinic is a real stakeholder role with no named party behind it today. [Q9]
- Staff time is the primary value story; captured calls and appointments are a welcome side effect rather than the headline claim. [Q10]

Does this all look correct before I generate the artifact?

- Looks correct
- Request changes

[Answer]: Looks correct

## Assumption Confirmation

The two artifacts record the following as assumptions — things that are useful
to preserve but that no answer establishes as fact:

**From the intent statement:**

1. Numeric targets and measurement windows for the three success metrics are not yet defined, so success is currently directional rather than testable. [assumption]
2. The regulatory frameworks named in the initial description (US HIPAA, India DPDP) have not been confirmed against a specific deployment jurisdiction or named customer, because no pilot clinic is selected yet. [assumption]
3. Whether the first deployment targets the US tenant, the India tenant, or both at once is not established. [assumption]

**From the stakeholder map:**

4. The interests of AI Thinkers leadership, clinic practitioners, and patients were not elicited, so those rows remain open. [assumption]
5. The pilot clinic's authority over scope and priority once selected is not established. [assumption]
6. With no formal reporting cadence and no named pilot, there is currently no defined channel through which clinic-side feedback reaches the initiative. [assumption]

A. Accept assumptions
B. Convert to follow-up questions

[Answer]: A. Accept assumptions
