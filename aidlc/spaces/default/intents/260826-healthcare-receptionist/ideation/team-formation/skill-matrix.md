# Skill Matrix and Gap Analysis

## Method

Required skills are derived from the proto-Units in
`../scope-definition/intent-backlog.md` and the constraints in
`../feasibility/constraint-register.md`. Availability is as answered in
`team-formation-questions.md`.

This is normally a matrix of people against skills. With a team of one [Q1] it
degenerates to a single column, so it is presented as a coverage table instead —
the same information without a grid that would imply a distribution that does not
exist.

## Coverage

| Skill area | Required by | Present? | Source |
|---|---|---|---|
| Real-time voice and telephony engineering — streaming audio, WebSocket media, latency tuning | P1 walking skeleton, P2 provider abstraction, P6 inbound agent | **Yes** | [Q3] |
| Healthcare compliance engineering — PHI handling, audit logging, consent, redaction | P3 compliance core, P8 analytics within the redaction boundary | **Yes** | [Q3] |
| AWS cloud infrastructure — multi-region deployment, IAM, networking | P3 region isolation, P4 multi-tenancy | **Yes** | [Q3] |
| Frontend — operator dashboard and read-only clinic view | P9 operator surface | **Yes** | [Q3] |
| Python — the implementation language for the agent runtime | P1, P2, P6, P7, P10, P11 | **Yes** | `../feasibility/feasibility-assessment.md` |

**No skill gaps.** Every capability the backlog requires is present today. There
is no remediation plan below because there is nothing to remediate, and inventing
one would be filling a template rather than reporting a finding.

## The real finding: concentration, not absence

Full coverage by one person is not the same as full coverage by a team, and the
difference is worth stating precisely.

**Bus factor is one.** Every skill area, and therefore every proto-Unit, depends
on the same individual. `team-topologies.md` treats bus factor as a primary
concern for teams below five people; at one it is not a concern to manage but a
structural property of the project.

**Knowledge transfer has no recipient.** `mob-programming-guide.md` names
"reduces bus factor to near zero" as mobbing's principal benefit and the fastest
route to spreading knowledge across a team. Neither is available here. Whatever
is learned about the vendor chain, the compliance boundary, or the tenancy model
stays with one person unless it is written down.

**Written artifacts are the only knowledge redundancy this project has.** That
gives the workflow's own outputs — the design documents, the decision records,
the diaries — a second purpose beyond process compliance: they are the sole
mechanism by which anything survives the person who built it. This is worth
knowing before Construction, when the temptation to skip documentation in favour
of throughput is strongest.

**No review by default.** Solo work has no second reader. This matters most for
P3, the compliance core, where PHI handling errors are breaches rather than
defects. `../feasibility/constraint-register.md` records C-R1 and C-R2 as Hard
constraints, and hard constraints normally get reviewed. How to compensate —
automated checks, an external review pass, or accepting the exposure — is a
practices-discovery question in Inception, not a team-formation one.

## Depth is unevidenced

[Q3] establishes presence, not depth, and this assessment cannot distinguish
between the two.

Two skill areas are worth flagging specifically, because the workflow has already
found them to be harder than they appear:

- **Real-time voice engineering.** `../feasibility/feasibility-assessment.md`
  rates Indic code-switching quality as High risk (R-01), and `docs/vendors.md`
  records that no vendor publishes an Indian-accent or 8kHz telephony benchmark.
  Working in this area competently is not the same as being able to resolve a
  question the vendor market itself has not answered.
- **Healthcare compliance engineering.** [Q8 of feasibility] chose to proceed on
  documented research with counsel engaged before real patient data. That places
  the compliance architecture decisions on the engineer rather than on counsel,
  in a domain where `docs/vendors.md` explicitly states its own compliance
  section is research and not legal advice.

Neither observation doubts the answer given. Both note that presence of a skill
and sufficiency for a specific hard problem are different claims, and only the
first has been established.

## Assumptions & Open Questions

- [Q3] records presence, not depth or years of practice. Depth cannot be
  cross-checked in a team of one. [assumption]
- No remediation plan is included because no gap exists. If depth proves
  insufficient in an area, that is a finding for Construction rather than a gap
  identifiable now. [assumption]
- Whether written artifacts will actually be maintained as the project's
  knowledge redundancy is an intention, not an established practice. It belongs
  to practices discovery. [assumption]
- Compensating for the absence of code review on PHI-handling components is
  unresolved and is deferred to practices discovery in Inception. [assumption]
