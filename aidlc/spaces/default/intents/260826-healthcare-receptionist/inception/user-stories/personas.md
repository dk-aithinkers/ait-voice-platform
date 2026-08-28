# Personas

Four personas, per [Q1]. Derived from `../../ideation/intent-capture/stakeholder-map.md`,
`../../ideation/rough-mockups/user-flow.md` and
`../requirements-analysis/requirements.md`.

**These are inferred, not researched.** No clinic has been consulted and no
patient has been interviewed. Goals and pain points below are drawn from the
approved artifacts and stated as such; they are a working model to write stories
against, not findings.

---

## P1 — Priya, the patient

| | |
|---|---|
| **Role** | Someone who needs to see a doctor |
| **Tech comfort** | Irrelevant, and that is the point — she is on a telephone |
| **Frequency** | A few times a year at most |

**The defining fact about this persona, per [Q4]: she did not choose to use this
product.** She rang her clinic. Every other persona here opted in — the clinic
bought it, the operator configured it. Priya encountered it. She cannot uninstall
it, cannot switch provider, and in many cases would rather have reached a person.

That is not a complaint to be designed around. It is the reason
`../../ideation/market-research/market-trends.md` found acceptance contingent on
the presence of a human rather than on the technology, and it should shape every
story she appears in.

**Goals**
- Get the appointment made, moved or cancelled, and get on with her day
- Reach a person when the agent cannot help, without having to fight for it
- Not repeat herself

**Pain points**
- Calling the clinic during working hours she does not have
- Being on hold
- Explaining something twice — once to software, then again to a human

**What failure looks like from her side**
- Silence on the line with no explanation
- An agent that keeps trying when she has already asked for a person
- Being told someone will call back, and nobody does

---

## P2 — Sana, front-desk staff

| | |
|---|---|
| **Role** | Runs the clinic's front desk; the person whose overload created this initiative |
| **Tech comfort** | Medium — uses the practice system daily, has no time for a new one |
| **Frequency** | Checks between patients, in gaps of a minute or two |

**Goals**
- Know what the agent handled while she was busy
- See what still needs a human, without hunting for it
- Trust that a patient who wanted her actually reached her

**Pain points**
- The phone ringing while a patient is standing in front of her
- Discovering a missed obligation after the patient complains
- Another screen to check

**What failure looks like from her side**
- A callback promised to a patient that nobody told her about
- Having to read a transcript to work out what happened
- The agent booking something wrong and her finding out from the patient

---

## P3 — Dr Rao, the practice owner

| | |
|---|---|
| **Role** | Owns or manages the practice; approved the spend |
| **Tech comfort** | Medium; not a daily user of this product |
| **Frequency** | Weekly at most — checking whether it is working |

**Goals**
- Know whether this is worth what it costs
- Know that patients are not having a bad experience with it
- Not be the one who finds out about a problem last

**Pain points**
- Paying for something whose effect he cannot see
- Patient complaints he did not know were coming

**What failure looks like from his side**
- A dashboard of activity that does not answer whether it is working
- Learning from a patient that the agent mishandled a call

**Note.** `../../ideation/rough-mockups/wireframes.md` marks the clinic view
provisional because it is unknown whether Sana or Dr Rao opens it. Keeping them
as separate personas keeps that question visible rather than resolving it by
assumption.

---

## P4 — The operator (AI Thinkers)

| | |
|---|---|
| **Role** | Configures and runs agents for client clinics |
| **Tech comfort** | High — this is their tool |
| **Frequency** | Daily |

**Goals**
- Get a clinic live without breaking a compliance rule
- Know a configuration works before a patient meets it
- See which clinics need attention without checking each one

**Pain points**
- Configuration that appears saved but is not live
- Regional rules that differ and are easy to get wrong
- Finding out about an unmet callback from the clinic rather than the system

**What failure looks like from their side**
- A clinic configured into the wrong region, with the wrong vendors and the wrong rules
- Placing an outbound call in India before registration completes

**Note.** With one engineer, this persona and the person building the system are
the same human. The persona is kept separate because the operator's *goals* are
distinct from the builder's, and the operator console is a real surface with real
failure modes.

## Assumptions & Open Questions

- All four personas are inferred from approved artifacts; **no clinic, patient or
  staff member has been consulted**. [assumption]
- Whether the clinic view serves Sana or Dr Rao is unresolved and is a D-01
  question. [assumption]
- Priya's language is unknown, because the pilot clinic's patient population is
  unknown (FR7.3). [assumption]
- Patients who cannot use a voice channel at all are not represented by P1 and
  have no persona, because no fallback has been decided (R-10, NFR6.2).
  [assumption]
