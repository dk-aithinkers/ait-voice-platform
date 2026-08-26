# User Flows

## Scope of this document

Flows for the initiative described in the approved intent statement
(`../intent-capture/intent-statement.md`), bounded by
`../scope-definition/scope-document.md` and covering the capabilities in
`../scope-definition/intent-backlog.md`.

The primary flow is a **telephone conversation**, not a screen sequence. Patients
never see an interface. That is why the call flow is given the depth here and the
screen flows are short — the design decisions that determine whether this product
works are all in the call.

Flows follow the format in `ux-guide.md`: persona, trigger, steps, success
outcome, error paths.

## Flow 1: Inbound call — the core flow

```
Flow: Inbound patient call
Persona: Patient calling the clinic
Trigger: Patient dials the clinic's number; the agent answers
```

### Happy path

| # | State | Caller action | Agent response |
|---|---|---|---|
| 1 | Answered | — | Greeting, clinic identification, **AI disclosure**, **recording disclosure** |
| 2 | Intent capture | States why they are calling | Recognises intent: book, reschedule, cancel, intake, question, other |
| 3 | Task | Provides details | Performs the task against the agent's own calendar |
| 4 | Confirmation | Confirms | Reads back what was done |
| 5 | Close | — | Offers anything further, ends the call |

**Success outcome:** the caller's task is completed and confirmed aloud, and a
call record with transcript and outcome exists for the clinic to see.

**Step 1 is not a courtesy.** `../feasibility/constraint-register.md` records C-R3
(verbal AI disclosure at the start of every call) and C-R4 (recording disclosure
nationwide) as Firm constraints, and California AB 2905 requires the AI disclosure
*before the message*, not after it. The greeting is a compliance surface, and it
is the first thing every patient hears — which makes it simultaneously the most
regulated and most experience-critical moment in the product.

### Error paths

Derived from [Q7] (one recovery attempt, then transfer) and [Q8] (message and
callback when unstaffed).

| Condition | Response | Then |
|---|---|---|
| Intent not understood | **One** rephrase or clarifying question | If still unresolved → escalation branch |
| Speech not recognised (accent, line quality, background noise) | One retry | → escalation branch |
| Caller explicitly asks for a person | No recovery attempt — honour it immediately | → escalation branch |
| Requested slot unavailable | Offer nearest alternatives | Not an error; stays in flow |
| Caller silent or line dropped | Standard timeout, close politely | Record as incomplete |
| **Clinical question or anything suggesting urgency** | No recovery attempt | → escalation branch, immediately |

The last row is a scope boundary, not a UX preference:
`../scope-definition/scope-document.md` excludes clinical decision-making, triage
and advice outright. The agent must recognise the category and leave it rather
than answer it.

### The escalation branch

This is where [Q7] and [Q8] combine, and it is the most consequential flow in the
product.

```
Escalation triggered
        |
        v
  Is a human available now?
        |
   +----+----+
   |         |
  YES        NO
   |         |
   v         v
Transfer   Take a message:
with       caller, callback number,
context    reason, urgency
   |         |
   v         v
Human      "Someone from the clinic
picks up   will call you back."
           |
           v
     Message enters the
     clinic's work queue
```

**"Is a human available now?" is a real question with no obvious answer.** Scope
includes 24/7 answering, so for most hours the answer is no. What determines it —
clinic opening hours, a rota, a live presence check — is undecided and is recorded
as an open question below.

**Transfer carries context.** `../feasibility/constraint-register.md` C-T6 makes
structured handoff a Firm constraint, and
`../market-research/market-trends.md` found patient acceptance depends on the
presence of a human. A transfer that makes the caller repeat everything wastes the
one thing that earns acceptance.

**The callback promise is an obligation on the clinic**, not on the agent. Nothing
in the system can fulfil it. It should not be spoken to a patient until a clinic
has agreed to answer it, and it makes the message queue a surface somebody must
actually watch — which is why both screens show it.

## Flow 2: Outbound reminder call

```
Flow: Appointment reminder
Persona: Patient with an upcoming appointment
Trigger: Scheduled reminder ahead of an appointment in the agent's calendar
```

| # | State | Agent | Caller |
|---|---|---|---|
| 1 | Connected | Identifies clinic, **AI disclosure**, states reminder purpose | — |
| 2 | Reminder | States appointment date and time | Confirms, asks to reschedule, or cancels |
| 3 | Action | Confirms, reschedules, or cancels | — |
| 4 | Close | Confirms the outcome aloud | — |

**Error paths:** no answer → retry per policy, then leave a voicemail if
permitted; wrong person answers → disclose nothing and end; caller asks a clinical
question → escalation branch as in Flow 1.

**A hard product constraint on this flow.** C-R5 in
`../feasibility/constraint-register.md`: no marketing content may enter a reminder
call. The TCPA healthcare exemption that makes these calls lawful without written
consent evaporates the moment promotional content appears. **This is a design
rule, not a legal footnote** — it forbids "while I have you, we're also offering…"
in any form.

In India this flow additionally cannot run at all until DLT registration and
1600-series numbering are in place (C-R6), and consent expires after seven days
(C-R9).

## Flow 3: Operator configures an agent

```
Flow: Configure a clinic's agent
Persona: AI Thinkers operator
Trigger: New clinic onboarding, or a change request
```

Steps: select clinic → edit configuration (greeting, hours, escalation number,
languages, calendar) → preview → save → verify with a test call.

**Success outcome:** the agent answers that clinic's number with the new
configuration, verified by a real call rather than by the save succeeding.

**Error paths:** invalid configuration blocked at edit rather than reported after
save (`ux-guide.md` heuristic 5, error prevention); test call fails → configuration
remains editable and the previous version stays live.

## Flow 4: Clinic reviews what happened

```
Flow: Review agent activity
Persona: Clinic staff or practice owner — not yet distinguished [Q3]
Trigger: Checking what the agent handled
```

Steps: open the clinic view → see summary and recent calls → open a call for
transcript and outcome → see outstanding messages needing callback.

**Success outcome:** the viewer can tell whether the agent handled calls well, and
knows what still needs a human.

This flow is **provisional**. [Q3] leaves the audience undecided, and what leads
the screen depends on who opens it — recent activity for front-desk staff,
performance summary for an owner. Resolving it is part of the pilot conversation
recorded as D-01 in `../feasibility/raid-log.md`.

## Assumptions & Open Questions

- **How the agent determines whether a human is available** is undecided, and the
  escalation branch depends on it entirely. [assumption]
- **The callback promise commits clinic staff time.** No clinic has agreed to it,
  because no pilot clinic exists. It should not be spoken to patients before that
  agreement. [assumption]
- **The voice channel excludes some callers outright** — deaf and hard-of-hearing
  patients, and those whose speech the recogniser handles poorly. [Q5] deferred
  the non-voice fallback decision, so these flows currently have no path for
  them. [assumption]
- **Whether the agent's own calendar is acceptable as the appointment system of
  record** is unresolved (`../scope-definition/scope-document.md`), and Flows 1
  and 2 both assume it. [assumption]
- **Reminder retry and voicemail policy** is unspecified — how many attempts, and
  whether leaving a message is permitted, which interacts with disclosure
  obligations. [assumption]
- **Language selection at call start** is undesigned. Indic code-switching is the
  stated differentiator, but whether the caller chooses a language, the agent
  detects it, or it is configured per clinic is not decided. [assumption]
