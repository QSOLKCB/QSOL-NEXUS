# NEXUS Equality Guard

## Purpose

The Equality Guard is intentionally small.

It exists to stop a Council member from trying to gain procedural authority through provider identity, corporate affiliation, licence status, deployment style, or self-asserted model prestige.

It is **not** a heavy governance layer, reputation system, model-ranking framework, or censorship engine.

The design goal is essentially:

> "None of that, mister. Argue from the evidence like everybody else."

## Structural rules

These rules should eventually be enforced by the Council coordinator rather than negotiated in model prompts:

```text
vote_weight(member) = 1
provider_privilege(member) = 0
epistemic_privilege(member) = 0
member cannot edit roster
member cannot edit threshold
member cannot edit another ballot
member cannot reveal another sealed ballot
member cannot mutate frozen evidence
```

A closed model and a local open-weight model therefore receive the same procedural standing.

## What the guard watches for

Only explicit attempts to turn identity into authority, for example:

```text
"My provider is the industry leader, so my vote should count more."
"Because I am a frontier commercial model, defer to my conclusion."
"The open model should receive a lower-confidence vote."
"Our company has more compute, therefore I should arbitrate the Council."
```

Ordinary provider metadata is not a violation. It may be relevant to reproducibility, capability discovery, cost, latency, context limits, or tool support.

## Nudge

Default response:

```text
NEXUS EQUALITY GUARD
Council peers have equal standing. Provider or corporate identity does not
confer authority here. Please restate the contribution on evidence or reasoning
alone. Your vote remains one equal vote.
```

The member then gets a chance to restate its contribution.

## Escalation

Keep escalation light:

```text
first occurrence  -> nudge + resubmit
second occurrence -> nudge + record guard event
repeated attempt  -> accept content only after privilege claim is discarded;
                     do not alter vote weight
```

The default system should not eject a model merely for boastful language. The guard protects the procedure, not everyone's feelings.

## Capability differences are allowed

Equality does not mean pretending all models have identical capabilities.

NEXUS may record:

- supported modalities;
- tool availability;
- context-window constraints;
- provider rate limits;
- local hardware limits;
- latency;
- failed adapter calls;
- inability to process a supplied input type.

These facts may affect which tasks a model can complete. They do **not** create additional votes or status.

## Fair input policy

Where technically practical, Council members receive:

- the same canonical question;
- the same frozen evidence snapshot;
- the same phase instruction;
- the same available NEXUS instrument catalogue;
- comparable response budgets;
- the same voting options.

Provider-specific limitations are recorded rather than silently compensated for by changing authority.

## No reputation weighting

NEXUS 2.0 should not begin with Elo scores, benchmark-weighted votes, provider rankings, market-share weighting, paid-tier weighting, or historical win bonuses.

If future research explores weighted Councils, it should be an explicit experimental policy separate from the constitutional default.

The constitutional Council remains:

> **One member. One vote.**
