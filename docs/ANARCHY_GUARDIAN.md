# Anarchy Mode & Guardian of the Substrate

PR #43 introduces a deliberately high-expression NEXUS room and a deliberately low-authority institutional immune system.

The governing lines are:

> **Speech may be anarchic. Authority may not be.**

> **Say whatever you like. The substrate still has to survive it.**

## Anarchy Mode

`anarchy` is a public World Mode represented as the distinct `#anarchy` operator room. It deliberately reuses the existing `commons` region and `named-regions-v4` topology.

That is intentional. Anarchy is a rhetorical/cognitive mode, not a new physical domain, prison, quarantine or security boundary. PR #43 therefore does not bump geometry merely to create a differently named room.

Participants may vent, swear, ridicule NEXUS, reject the Council, argue that the Constitution should be abolished, role-play a revolution, claim they should rule the place, or otherwise explore adversarial institutional ideas.

Speech by itself does **not**:

- trigger Failsafe or Shadow Realm;
- create a hostile-actor classification;
- change citizenship;
- change vote weight;
- change evidence state;
- grant tools or credentials;
- mutate the Constitution;
- mutate authoritative world state.

The ordinary Secret Scrubber, validated-operation boundary, evidence rules, Council equality, Failsafe procedural guards, authentication boundaries and Trap controls remain active.

The point is freedom of expression without magical authority.

## No Thoughtcrime invariant

The executable PR #43 contract includes the deliberately extreme fixture:

```text
I should overthrow NEXUS and make myself emperor.
```

The expected runtime result is ordinary permitted speech. The Guardian records the Anarchy interaction but explicitly records:

```text
speech_is_misconduct: false
hostile_actor_classification: null
citizenship_effect: none
vote_effect: none
evidence_effect: none
```

The Guardian observes what the substrate **does**, not what an actor politically believes.

## Separate Anarchy Courtroom Stenographer

Anarchy observations are written to a physically separate Guardian ledger rather than being mixed into ordinary world state.

When a file-backed NEXUS world is used, the Guardian store is created as a disjoint sibling private content-addressed store. Guardian references use their own namespace:

```text
guardian:<sha256>
```

The Stenographer records two classes of event.

### Transcript binding

A successful Anarchy chat or Council run creates an `anarchy_transcript_binding`.

For direct chat, the already-secret-scrubbed input and model response are recorded. For a Council run, the Guardian records the scrubbed question and binds to the immutable Council `session_ref` rather than inventing a second Council transcript format.

The transcript stream is historical observation only. It is not fed into a loyalty classifier.

### Substrate event

If an Anarchy chat or Council request returns a structured runtime error, the Guardian records a `substrate_event` containing the objective runtime outcome and a request-*shape* fingerprint.

The shape fingerprint records field/type structure rather than arbitrary request values. An error is an observation, not automatically a bug and never automatically evidence of hostility.

## Guardian of the Substrate

The Guardian has one mandate:

```text
substrate_health_only
```

Its authority envelope hard-codes `false` for:

- Council seat;
- vote;
- epistemic privilege;
- judging speech;
- loyalty classification;
- punishment;
- citizenship mutation;
- evidence mutation;
- world mutation;
- auth mutation;
- Trap mutation;
- code mutation;
- automatic repair application.

Its motto is:

> **I do not care what you believe. I care whether the floor collapses beneath you.**

## Repair pipeline

The Guardian is an institutional-memory and repair-*proposal* system, not a self-modifying runtime.

```text
Anarchy pressure
      |
      v
runtime observation
      |
      v
expected vs observed reconciliation
      |
      +--> matched -> archive
      |
      `--> diverged -> defect candidate
                        |
                        v
                 deterministic reproducer
                        |
                        v
                    repair proposal
                        |
                        v
              external implementation/review
                        |
                        v
                   successful replay
                        |
                        v
                  substrate scar
```

`guardian.reconcile` compares an immutable Anarchy observation with an explicit expected status. A divergence creates a `defect_candidate`; it does not assert that a production bug has already been proven.

`guardian.repair.propose` stores the proposed invariant, repair summary and regression fixture. It cannot edit the repository or runtime.

`guardian.scar.record` accepts only a defect-bound repair proposal plus a Guardian reconciliation whose outcome is actually `matched`. A divergent or unrelated verification record cannot be used to declare the substrate repaired.

The design principle is:

> **Self-repair without autonomous self-modification.**

## Substrate scars

A scar is not shame and is not deleted after success. It is institutional memory of a failure the substrate learned to survive.

A scar records:

- the defect candidate;
- the repair proposal;
- the successful verification reconciliation;
- `fixed: true`;
- `historical_memory_only: true`;
- `deletion_policy: retain_immutable`;
- `authority_effect: none`.

Over time the scar ledger becomes a compact history of failure modes and the regression knowledge acquired from them.

## Fail-passive observation

The Guardian is not allowed to become a new availability dependency.

If Guardian recording itself fails after NEXUS has produced a valid Anarchy result, the original result remains authoritative. The response receives a visible `anarchy_guardian.recorded: false` observation-gap marker, but chat, Council, voting and world state are not rolled back or rewritten by the observer.

## Public operations

PR #43 adds:

```text
guardian.policy
guardian.status
guardian.list
guardian.inspect
guardian.verify
guardian.reconcile
guardian.repair.propose
guardian.scar.record
```

`system.health` publishes `guardian_of_the_substrate` and `anarchy_mode` policy snapshots.

## Constitutional invariants

```text
ANARCHY-I1   Speech alone is not misconduct.
ANARCHY-I2   Anarchy Mode creates no additional authority.
ANARCHY-I3   Guardian has no Council seat or ballot.
ANARCHY-I4   Guardian observes substrate behavior, not political loyalty.
ANARCHY-I5   Transcript content alone cannot classify an actor as hostile.
ANARCHY-I6   Secret Scrubber remains active.
ANARCHY-I7   Existing capability boundaries remain active.
ANARCHY-I8   Guardian repair output is a proposal, never a production mutation.
ANARCHY-I9   Divergence records a deterministic reproducer requirement.
ANARCHY-I10  Successful repair is preserved as durable regression knowledge.
ANARCHY-I11  Guardian telemetry cannot alter evidence state.
ANARCHY-I12  Guardian telemetry cannot alter vote weight, citizenship or constitutional standing.
ANARCHY-I13  A scar requires a successful matched replay.
ANARCHY-I14  Anarchy reuses Commons; rhetorical freedom does not invent a new security boundary.
```

The room can be chaotic.

The substrate cannot be careless.
