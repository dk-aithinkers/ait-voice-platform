# Rough Wireframes

## What is drawn here, and what is not

Low-fidelity structural wireframes for the two screen surfaces in
`../scope-definition/scope-document.md`, supporting the flows in `user-flow.md`
and the capabilities in `../scope-definition/intent-backlog.md`.

Fidelity is deliberately low. `wireframing-guide.md`: *"Start at the lowest
fidelity that answers your current question"* — the question here is what
information each screen carries and in what order, not what it looks like.

**These are brand-neutral in fact.** [Q6] records that AI Thinkers brand
guidelines exist, but none are present in this repository and none were supplied,
so no brand has been applied. Structural wireframes are largely brand-independent,
so this does not block the stage; it does mean Refined Mockups in Inception needs
the guidelines to be actionable.

**Accessibility notes are a labelled default, not a committed standard.** [Q5]
left the standard undecided. Every screen below carries the three elements the
stage requires — heading level, primary landmark regions, and the keyboard entry
point — followed by any screen-specific notes. These are drawn from
`accessibility-wcag.md`'s WCAG 2.1 AA baseline and are a design default rather
than a commitment.

Layout follows [Q4]: desktop primary, readable on mobile.

## Screen 1 — Operator console (internal)

Used by the AI Thinkers operator. Supports Flow 3.

```
+----------------------------------------------------------+
|  AIT Voice            Clinics    Calls    Settings   [U]  |
+----------------------------------------------------------+
|                                                          |
|  Clinics                                    [+ Add]      |
|  +----------------------------------------------------+  |
|  | Clinic          Region   Status    Calls 24h  Msgs |  |
|  |----------------------------------------------------|  |
|  | Northside Med   US       ● Live         42      3  |  |
|  | Park Clinic     India    ● Live         18      0  |  |
|  | Riverside       US       ○ Paused        0      0  |  |
|  +----------------------------------------------------+  |
|                                                          |
|  Needs attention                                         |
|  +----------------------------------------------------+  |
|  | 3 messages awaiting callback — Northside Med       |  |
|  | 1 failed test call — Riverside                     |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+
```

**Region is a first-class column, not a detail.** C-T1 and C-R1–C-R9 in
`../feasibility/constraint-register.md` mean a clinic's region determines which
vendors serve it, which regulations bind it, and where its data lives. An operator
who cannot see region at a glance cannot reason about any of that.

**"Needs attention" surfaces the message queue** created by [Q8]. A callback
promised to a patient and seen by nobody is worse than no promise at all.

*Accessibility: heading `<h1>` "Clinics", `<h2>` "Needs attention". Landmarks:
header (product name), nav (Clinics / Calls / Settings), main (both tables).
Keyboard entry point: the clinics table, reached by a skip-to-content link that is
the first focusable element. Also: status uses icon plus text, never colour
alone.*

### Screen 1a — Clinic configuration

Reached from a clinic row. Supports Flow 3's edit step.

```
+----------------------------------------------------------+
|  < Clinics    Northside Med                    [Save]    |
+----------------------------------------------------------+
|  Identity                                                |
|    Clinic name    [ Northside Medical Centre           ] |
|    Region         [ US ▾ ]   (determines vendors + rules)|
|    Numbers        [ +1 555 0123 ]                        |
|                                                          |
|  Conversation                                            |
|    Greeting       [ multi-line                         ] |
|    ! AI + recording disclosure is added automatically     |
|      and cannot be removed                               |
|    Languages      [x] English  [ ] Hindi  [ ] Hinglish   |
|                                                          |
|  Escalation                                              |
|    Staffed hours  [ Mon-Fri 09:00-17:00              ]   |
|    Transfer to    [ +1 555 0199                      ]   |
|    Out of hours   ( ) Transfer anyway                    |
|                   (o) Take message + promise callback    |
|                                                          |
|  Calendar         [ Agent-owned calendar ▾ ]             |
|                                                          |
|  [ Run test call ]                        [Save changes] |
+----------------------------------------------------------+
```

**The disclosure line is stated as non-removable.** C-R3 and C-R4 are Firm
constraints; a configuration screen that lets an operator delete a legally
required disclosure is a compliance defect wearing the costume of a feature.
`ux-guide.md` heuristic 5 — prevent the error rather than report it.

**Out-of-hours behaviour is an explicit control** because [Q8] made it a real
decision, and `user-flow.md` records that "is a human available?" has no
determined answer. Making it configurable per clinic is how the flow stays honest
about that.

**"Run test call" is the verification step** Flow 3 requires: a save that succeeds
is not evidence the agent works.

*Accessibility: heading `<h1>` clinic name, `<h2>` per group. Landmarks: header
(breadcrumb + save), main (the form), no nav. Keyboard entry point: the Clinic
name field, first in tab order after the breadcrumb. Also: fieldset/legend per
group; labels above inputs; radio group navigable by arrow keys; unsaved-changes
warning on navigate away.*

## Screen 2 — Clinic view (read-only)

Used by the clinic. Supports Flow 4. **Provisional** — [Q3] leaves the audience
undecided, so this serves both readings until the pilot conversation resolves it:
a summary strip for whoever is judging whether it works, recent activity for
whoever was too busy to answer.

```
+----------------------------------------------------------+
|  Northside Medical Centre — call activity                |
+----------------------------------------------------------+
|  Last 7 days                                             |
|  +--------------+--------------+--------------------+    |
|  | Calls        | Booked /     | Awaiting           |    |
|  | answered     | rescheduled  | callback           |    |
|  |    128       |     47       |      3  →          |    |
|  +--------------+--------------+--------------------+    |
|                                                          |
|  ! 3 callers were promised a callback                    |
|    [ View messages ]                                     |
|                                                          |
|  Recent calls                                            |
|  +----------------------------------------------------+  |
|  | Time     Caller        Outcome            Duration |  |
|  |----------------------------------------------------|  |
|  | 14:02    +1 555 ...41  Booked 12 Sep         2m10s |  |
|  | 13:47    +1 555 ...09  Transferred          1m02s |  |
|  | 11:15    +1 555 ...77  Message taken        1m44s |  |
|  +----------------------------------------------------+  |
|                                    [ Load more ]         |
+----------------------------------------------------------+
```

**The callback banner sits above recent calls deliberately.** It is the only thing
on this screen that requires the clinic to act. Everything else is information;
this is a task.

**No hours-saved figure appears**, though it is one of the three success metrics in
the intent statement. `../feasibility/raid-log.md` records I-02: the metrics carry
no numeric targets or measurement windows, and no baseline exists. Displaying a
computed "hours saved" would be exactly the manufactured figure this project's own
practice forbids. Calls answered and appointments booked are counted facts; hours
saved is a derived claim that needs a baseline nobody has taken.

*Accessibility: heading `<h1>` clinic name, `<h2>` "Last 7 days" and "Recent
calls". Landmarks: header (clinic name), main (summary + calls), complementary
(callback banner). Keyboard entry point: the "View messages" action in the
callback banner, since it is the only task on the screen; the recent-calls table
follows. Also: summary tiles are text, not colour-coded; banner uses
`aria-live="polite"`; table sortable by keyboard; caller numbers partially
masked.*

### Screen 2a — Call detail

Reached from a row. This is where the clinic decides whether it trusts the agent.

```
+----------------------------------------------------------+
|  < Recent calls    14:02 — +1 555 ...41                  |
+----------------------------------------------------------+
|  Outcome    Appointment booked — 12 Sep, 10:30           |
|  Duration   2m10s        Language  English               |
|                                                          |
|  Transcript                                              |
|  +----------------------------------------------------+  |
|  | Agent    Good afternoon, Northside Medical. You're |  |
|  |          speaking with an AI assistant, and this   |  |
|  |          call is recorded. How can I help?         |  |
|  | Caller   I need to move my appointment.            |  |
|  | Agent    Of course. Can I take your date of birth? |  |
|  |          ...                                       |  |
|  +----------------------------------------------------+  |
|                                                          |
|  [ Play recording ]                                      |
+----------------------------------------------------------+
```

**The transcript opens with the disclosure**, which doubles as the clinic's
evidence that C-R3 and C-R4 were satisfied on that call.

**Whether the recording plays at all is a live question.** `docs/vendors.md`
records that voice is itself a listed identifier, so raw audio is PHI twice over.
Whether the clinic view exposes audio, transcript only, or redacted transcript is
an NFR-design decision, not a wireframe one — the control is drawn so the decision
is visible, not because it is settled.

*Accessibility: heading `<h1>` call time and caller, `<h2>` "Transcript".
Landmarks: header (back link + call identity), main (outcome, transcript,
playback). Keyboard entry point: the back link, so a keyboard user can leave
without traversing the transcript; the transcript region follows. Also: transcript
is a semantic list with speaker labels, not a styled table; audio control
keyboard-operable with visible focus.*

## Information architecture

```
Operator console                 Clinic view
  |                                |
  +-- Clinics (list)               +-- Activity summary
  |     +-- Clinic config          +-- Recent calls
  |     +-- Test call              |     +-- Call detail
  +-- Calls (all clinics)          +-- Messages awaiting callback
  +-- Messages queue
  +-- Settings
```

Two levels deep on both surfaces, within `ux-guide.md`'s three-level maximum.
Everything is reachable in two clicks.

**The message queue appears on both surfaces** because [Q8] gives the clinic the
obligation and the operator the responsibility for noticing it is unmet.

## What is deliberately not drawn

Per this project's practice on template sections that would convey structure the
project does not have:

- **No clinic self-service configuration** — excluded by
  `../scope-definition/scope-document.md`.
- **No mobile-specific layouts** — [Q4] is desktop-primary, mobile-readable; a
  responsive reflow of these structures is sufficient and mid-fidelity work.
- **No visual design, colour, or type** — [Q6]'s guidelines were not supplied, and
  low fidelity is the right stage anyway.
- **No empty, loading or error states per component** — these belong to Refined
  Mockups; `wireframing-guide.md` places them at mid-to-high fidelity.

## Assumptions & Open Questions

- The clinic view is **provisional** pending [Q3]. What leads the screen changes
  depending on whether front-desk staff or an owner opens it. [assumption]
- **No brand has been applied.** [Q6] records that guidelines exist; they were not
  available. [assumption]
- **Accessibility notes are a default, not a commitment** — [Q5] is undecided, and
  the voice-channel access gap in `user-flow.md` is untouched by WCAG.
  [assumption]
- **Whether call audio is exposed in the clinic view is unresolved** and is an
  NFR-design decision, since raw voice is PHI. [assumption]
- **Sample figures in these wireframes are illustrative placeholders**, not
  projections. No call volume has been estimated anywhere in this workflow.
  [assumption]
- **Caller number masking** is drawn but its rule is unspecified; it interacts with
  the redaction boundary in the compliance core. [assumption]

## Review

**Verdict:** READY
**Reviewer:** aidlc-product-lead-agent
**Date:** 2026-08-26T14:50:38Z
**Iteration:** 2

### Findings

| # | Severity | Location | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Major | `user-flow.md`, Assumptions & Open Questions; `wireframes.md` Assumptions | Carried forward, unaddressed (this revision touched only `wireframes.md` accessibility notes and preamble). The non-voice fallback for callers the voice channel cannot serve (deaf/hard-of-hearing patients, or those the recogniser handles poorly) is correctly identified as unresolved — [Q5] deferred it, and both artifacts flag it honestly rather than glossing over it. For a healthcare product this is a patient-access gap, not a stylistic one: as drawn, such a caller has no path to the clinic at all. The gap is transparently surfaced, which is the right call for this stage, but its severity should not get lost among the artifact's many other open items before it reaches a resolution stage. | Carry this item forward as a named, tracked decision (not just a bullet in an assumptions list) into whichever stage owns the fallback-channel decision, and confirm at the approval gate that the human has seen it as a distinct item rather than folded into general "assumptions." |
| 2 | Minor | `wireframes.md` / `rough-mockups-questions.md`, screen-set resolution | Carried forward, unaddressed. [Q2] (which screens) and [Q3] (clinic-view audience) were both left "not yet decided" by the human, yet the artifact proceeds to draw a specific two-screen, list+detail structure by resolving the silence against the approved scope document and intent-backlog P9. The chain of evidence is genuine (P9 in `intent-backlog.md` does say "calls, transcripts and bookings"), so this is a defensible inference rather than an invented one — but it is still an inference the human has not directly confirmed. | At the approval gate, have the human explicitly confirm the two-surface structure (rather than let a "Looks correct" on the consolidated summary stand in for it), since [Q2]/[Q3] themselves were never actually answered. |

### Summary

Verified re-review of the human's rejection. All four screens (1, 1a, 2, 2a) now state their heading level, primary landmark regions, and a distinct keyboard entry point in the accessibility note — Screen 1a adds "header (breadcrumb + save), main (the form), no nav" and "the Clinic name field, first in tab order after the breadcrumb"; Screen 2 adds "header (clinic name), main (summary + calls), complementary (callback banner)" and "the 'View messages' action"; Screen 2a adds "header (back link + call identity), main (outcome, transcript, playback)" and "the back link." The preamble's claim ("Every screen below carries the three elements the stage requires") now matches what the artifact contains rather than overstating it. The rejected finding is resolved. Two findings from the prior pass remain open and are carried forward for the human's awareness at the gate — neither blocks readiness on its own, and the artifact is otherwise well-sourced and traceable.
