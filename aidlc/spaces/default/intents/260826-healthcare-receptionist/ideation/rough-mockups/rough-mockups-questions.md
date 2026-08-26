# Rough Mockups & Concept Visualization — Questions

**Mode:** guided

## Context

These build on the approved intent statement
(`../intent-capture/intent-statement.md`), the scope document
(`../scope-definition/scope-document.md`) and the intent backlog
(`../scope-definition/intent-backlog.md`).

**This initiative is neither a UI project nor a non-UI project, and the questions
below reflect that.** There is real screen work in scope — internal configuration
plus a read-only clinic view [scope-definition Q5] — but the primary interface
between the product and the people it serves is **a telephone conversation**.
Patients never see a screen. Clinic staff see one occasionally. The design surface
that determines whether this product works is the call itself.

So this stage treats conversation design as the main event and the screens as
supporting, rather than the other way round. Q1 asks you to confirm or correct
that reading before anything is drawn.

---

## Q1. Should this stage treat the call as the primary design surface?

A. Yes — design the conversation flow first and in depth; wireframe the screens at low fidelity as supporting material.
B. No — the screens are the deliverable for this stage; conversation design belongs to a later stage or to prompt engineering.
C. Both equally — full treatment of screens and conversation.
D. Not yet decided.
X. Other (please specify)

[Answer]: C. Both equally — full treatment of screens and conversation.

---

## Q2. Which screens does the MVP actually need?

`../scope-definition/scope-document.md` puts internal configuration and a
read-only clinic view in scope, and excludes clinic self-service.

A. Two surfaces — an internal operator console, and a clinic-facing read-only view of calls and bookings.
B. Three — the two above plus a per-call detail view with transcript and outcome.
C. One — a single console used by your team, with the clinic view deferred until a pilot asks for it.
D. Not yet decided.
X. Other (please specify)

[Answer]: D. Not yet decided.

---

## Q3. Who is the clinic-side viewer, and what do they need to see first?

The intent statement records the clinic's value as front-desk staff hours saved,
so the person opening this view is likely the person whose calls were answered.

A. Front-desk staff — they need to see what the agent handled while they were busy, so recent calls and new bookings lead.
B. The practice owner or manager — they need to see whether it is working, so volume, answer rate and hours saved lead.
C. Both, with the same view serving both needs.
D. Not yet known — depends on the pilot clinic.
X. Other (please specify)

[Answer]: D. Not yet known — depends on the pilot clinic.

---

## Q4. What device and form factor must the screens support?

A. Desktop only — this is a back-office tool used at a workstation.
B. Desktop primary, mobile-readable — a practice owner may check it on a phone.
C. Mobile-first — assume the clinic looks at this on a phone.
D. Not yet decided.
X. Other (please specify)

[Answer]: B. Desktop primary, mobile-readable — a practice owner may check it on a phone.

---

## Q5. What accessibility standard applies?

`accessibility-wcag.md` treats WCAG 2.1 AA as the baseline. Note that the voice
channel has its own accessibility considerations that are not covered by WCAG —
callers who are deaf or hard of hearing, or whose speech the recogniser handles
poorly, cannot use a voice agent at all, and reach the service only through the
human handoff or another channel.

A. WCAG 2.1 AA for the screens, and an explicit non-voice fallback path for callers the voice channel cannot serve.
B. WCAG 2.1 AA for the screens only; the voice fallback question is deferred.
C. Best-effort on the screens; no formal standard committed for the MVP.
D. Not yet decided.
X. Other (please specify)

[Answer]: D. Not yet decided.

---

## Q6. Are there existing brand guidelines or a design system to follow?

A. Yes — AI Thinkers has brand guidelines and/or a component library to reuse.
B. No — start from a plain, neutral utility style with no brand investment at MVP.
C. It should be white-labellable per clinic from the start, since the model is managed service.
D. Not yet decided.
X. Other (please specify)

[Answer]: A. Yes — AI Thinkers has brand guidelines and/or a component library to reuse.

---

## Q7. When a call goes wrong, what should the agent do?

`../market-research/market-trends.md` found patient acceptance is contingent on
the presence of a human, not on the technology. This makes failure behaviour a
design decision rather than an edge case.

A. Transfer to a human immediately on any difficulty — lowest patient frustration, highest load on the front desk the product exists to relieve.
B. One recovery attempt, then transfer — a single rephrase or clarification before handing off.
C. Take a message and promise a callback when no human is available, transferring during staffed hours.
D. Not yet decided.
X. Other (please specify)

[Answer]: B. One recovery attempt, then transfer — a single rephrase or clarification before handing off.

---

## Q8. Follow-up — what happens when recovery fails and no human is available?

Raised because [Q7] chooses "one recovery attempt, then transfer", which assumes
a human exists to receive the transfer. The scope includes 24/7 answering
(`../scope-definition/scope-document.md`), so for much of the day there is nobody
to transfer to. The flow needs an out-of-hours branch regardless of the
staffed-hours policy.

A. Take a message and promise a callback.
B. Offer specific callback slots the caller chooses from.
C. Route to the clinic's existing after-hours path (answering service, emergency line, voicemail).
D. Not yet decided — mark it as a decision point in the flow.
X. Other (please specify)

[Answer]: A. Take a message and promise a callback.

---

## Consolidated Summary Confirmation

Summary of all answers:

- **Both the conversation and the screens get full treatment** as design surfaces. [Q1]
- The screen set is **not yet decided**. [Q2]
- The clinic-side viewer and what they need first is **not yet known** — it depends on the pilot clinic. [Q3]
- Screens are **desktop primary, mobile-readable**. [Q4]
- The accessibility standard is **not yet decided**. [Q5]
- **AI Thinkers brand guidelines and/or a component library exist** and should be reused. [Q6]
- On call failure: **one recovery attempt, then transfer** to a human. [Q7]
- When recovery fails and no human is available: **take a message and promise a callback**. [Q8]

**An ambiguity that has to be resolved to draw anything.** [Q1] asks for full
treatment of the screens, while [Q2] leaves the screen set undecided and [Q3]
leaves their audience unknown. A surface cannot be given full treatment when
neither its inventory nor its reader is settled. Resolved as follows, rather than
by asking again:

- The **approved scope document is the authority** where the answers are silent.
  It puts internal configuration and a clinic-facing read-only view of "calls,
  transcripts and bookings" in scope. Transcript viewing implies a per-call
  detail level, so the wireframes cover **two surfaces, one of which has a list
  and a detail view** — which is the substance of both option A and option B of
  [Q2] without asserting a choice the human declined to make.
- Because [Q3] is unknown, the clinic view is designed to **serve both audiences
  from one screen** — recent activity for front-desk staff, a small summary strip
  for whoever is judging whether it works — and is marked provisional pending the
  pilot conversation.

**A limit on what [Q6] can mean at this stage.** The answer records that brand
guidelines exist, but none are present in this repository and none have been
provided. Low-fidelity wireframes are structural rather than visual, so this does
not block the stage — but the artifacts are **brand-neutral in fact**, and the
brand cannot be claimed as applied. Supplying the guidelines before Refined
Mockups in Inception is what makes [Q6] actionable.

**[Q5] is undecided, so a default is applied and labelled as one.** The wireframes
carry the WCAG 2.1 AA notes the stage requires — heading level, landmark regions,
keyboard entry point per screen — because `accessibility-wcag.md` treats AA as the
baseline and the phase rules require accessibility to be addressed. That is a
design default, not a committed standard.

The **voice-channel access gap remains open and unaddressed**: a caller who is
deaf or hard of hearing, or whose speech the recogniser handles poorly, cannot use
a voice agent at all. [Q5] deferred the decision on a non-voice fallback. For a
healthcare product this is recorded as an open question rather than a design
detail, because the consequence is a patient who cannot reach their clinic.

**[Q7] and [Q8] together form a complete and designable failure policy**, which
is the most useful outcome of this stage: one recovery attempt, then transfer
during staffed hours, then message-and-callback when unstaffed. Two consequences
follow. The promise of a callback is **an obligation on the clinic**, not on the
agent, so it needs the clinic's agreement before it is spoken to a patient. And
captured messages become **a work queue somebody has to see**, which the operator
and clinic views must therefore show.

Does this all look correct before I generate the artifacts?

- Looks correct
- Request changes

[Answer]: Looks correct
