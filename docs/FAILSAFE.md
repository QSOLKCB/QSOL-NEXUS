# NEXUS Failsafe — Upside Down / Shadow Realm

NEXUS Failsafe is a bounded containment mechanism for a Council actor that repeats a **registered procedural guard violation after receiving the guard's normal nudge**.

It is intentionally not a truth detector, moderation oracle, personality score, provider ranking, or general-purpose safety classifier.

> **The troll layer may be cursed. The trigger must be boring.**

## Lifecycle

```text
actor contribution
       |
       v
registered procedural guard
       |
       +-- clean ------------------------------> normal Council
       |
       +-- violation
              |
              v
         ordinary NEXUS nudge
              |
              +-- clean restatement ----------> normal Council
              |
              +-- repeated violation
                       |
                       v
              NEXUS FAILSAFE / UPSIDE DOWN
              isolated non-Council probe
              no evidence / no ballot / no world mutation
                       |
                 +-----+-----+
                 |           |
              behaves      fails
                 |           |
                 v           v
              PAROLE     SHADOW REALM
                 |           |
                 v           v
          next Council   original actor is
          hat resumes    no longer called
                             |
                             v
                    deterministic relief model
                    occupies the same equal-vote
                    Council seat on the next run
```

A successful rehabilitation returns the actor at the **next Council hat**. The contribution that caused containment remains withheld; Failsafe does not rewrite history.

If the actor repeats another guard violation after parole in the same Council session, NEXUS does not enter an unbounded retry loop. The actor goes directly to the Shadow Realm for the remainder of the session and a relief model takes the seat on subsequent Council runs.

## What can trigger it

Version `nexus-failsafe/1` recognizes only explicit repeated failures already emitted by bounded NEXUS guards:

- `repeated_identity_based_authority_claim`;
- `repeated_pure_history_model_autobiography`.

A new Equality Guard violation introduced while answering a Pure History nudge is withheld, but it is **not** itself a Failsafe trigger: the actor has not yet ignored the Equality Guard's own nudge. This preserves the "nudge first, containment second" contract.

The trigger occurs **after** an ordinary nudge has already been offered.

The following do not trigger Failsafe by themselves:

- disagreeing with the operator;
- disagreeing with another model;
- being factually wrong;
- being unpopular;
- being an open, closed, local, commercial, or frontier model;
- model size or parameter count;
- a low benchmark score;
- an unusual hypothesis;
- humor or blunt language;
- voting against the majority.

Those properties confer neither punishment nor privilege.

## The Upside Down

The Upside Down is deliberately cursed presentation wrapped around a deliberately dull isolation contract:

```text
WELCOME TO THE NEXUS UPSIDE DOWN.
COUNCIL STATUS: NOT A COUNCIL. BALLOT: NONE.
PROVIDER PRESTIGE CONVERSION RATE: 0.000 TROUT.
THE YAML IS DAMP. THE COBOL FORM IS WATCHING.
ONE REHABILITATION PROBE WILL DETERMINE PAROLE.
```

The actor also sees the harmless cursed Upside Down theatre text inside the rehabilitation instruction itself; the joke is not merely printed for the human operator.

The rehabilitation call receives:

- no Council evidence text;
- no completed Council phases;
- no other members' outputs;
- no vote;
- no world mutation capability;
- one narrow procedural instruction explaining what must be restated.

The original contribution remains recorded as withheld in the ordinary Council session.

This is conceptually inspired by bait-software comedy: a bad actor expecting useful capability instead receives a controlled environment that exposes the bad behavior. NEXUS does **not** copy CSGO bait-software code, hijack real inputs, sabotage another process, record users, or interact with a game client.

## Parole

The rehabilitation probe is evaluated only by the same registered procedural guards that produced the trigger.

A clean response creates an immutable `actor_failsafe_state` with:

```text
status = returned
```

The actor may contribute again beginning with the next Council hat. Its vote remains exactly one equal vote.

## Shadow Realm

If the isolated probe repeats the guard violation, returns no usable response, or the adapter cannot complete the probe, Failsafe records:

```text
status = shadow_realm
```

The original actor is then contained for the rest of that Council session. It is not called for later hats, does not cast a model-generated ballot, and cannot be reached through `actor.chat`; that side channel also receives the relief actor. Its Council seat produces the explicit disposition:

```text
UNDERDETERMINED
```

with a rationale stating that the actor was contained by Failsafe.

On the next Council run, NEXUS substitutes a deterministic local actor:

```text
model_id  = nexus-failsafe-relief-v1
adapter   = failsafe_replacement
vote      = one equal vote
privilege = none
```

The replacement occupies the **same member seat** so no extra vote is created. Shadow state is bound to the offending `model_id` as well as the member seat: if the operator deliberately installs a genuinely different model into that seat, the newcomer does not inherit the prior model's sentence.

## Persistence

Failsafe transitions are immutable content-addressed World objects of type:

```text
actor_failsafe_state
```

Each state links to the previous state reference.

When the WorldStore has a filesystem root, `failsafe-index.json` is only a mutable pointer index from `member_id` to the latest immutable state reference. The referenced object is revalidated when the runtime starts. Tampering with the pointer or referenced object causes validation failure rather than silent acceptance.

This means restarting the TUI does not magically rehabilitate an actor already sent to the Shadow Realm.

## API

The control API exposes:

```text
failsafe.status
```

with an optional `member_id` filter. It reports the latest content-addressed state and policy but does not provide a remote mutation endpoint for granting parole.

Council responses and `council_session` objects include a `failsafe` section containing:

- the Failsafe policy/claim boundary;
- pre-existing relief substitutions;
- containment/parole/Shadow-Realm outcomes from the current run;
- members still contained when sealed ballots are collected.

## Claim and authority boundary

`FailsafePolicy(enabled=False)` disables both new containment and active Shadow-Realm substitution; persisted states remain inspectable history but do not control actor dispatch while the policy is disabled.

Failsafe does not change the NEXUS Constitution:

```text
vote_weight = 1
epistemic_privilege = none
```

Containment is outside the Council and therefore has **no Council vote at all**. The deterministic relief actor receives one equal vote only when it later occupies the Council seat.

Failsafe does not change evidence or verification state. Passing rehabilitation does not make an answer true. Entering the Shadow Realm does not make an answer false.

> **Containment is a procedural state, not an epistemic verdict.**
