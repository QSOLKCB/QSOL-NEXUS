# NEXUS World Protocol

> **NEXUS 2.0 release status:** this protocol document is part of the final candidate; executable schemas/tests take precedence over historical planning language.

## Purpose

The World Protocol is the stable interface between cognitive actors and the persistent NEXUS world.

Models may reason however they like internally. Durable interaction with the shared world occurs through explicit operations.

## Design principle

> **The model proposes. The world records, places, computes, verifies, and remembers.**

The protocol should remain model-neutral and transport-neutral.

## Current and planned primitives

Current reference operations include:

```text
world.create
world.inspect
world.modes
world.geometry
world.geometry.distance
citizen.constitution
citizen.status
citizen.begin
citizen.exam.template
citizen.exam.submit
citizen.move
citizen.proxy.appoint
citizen.proxy.recall
citizen.independence.ballot
```

Longer-term conceptual syscalls include:

```text
world.search
world.recall
world.create_object
world.relate
world.compute
world.compare
world.simulate
world.visualize
world.sonify
world.hypothesize
world.test
world.falsify
world.commit
world.verify
world.replay
world.move
```

Names beyond the current reference API remain provisional.

## World modes

A World Mode is protocol state describing the framing of an interaction.

```text
WorldMode
├── mode_id
├── label
├── description
├── prompt_instruction
└── region_id
```

Current built-ins:

```text
analytical
historical
pure_history
cultural
meme_casual
clinical_differential
house_fun
cbt_learning
roman_orator
house_of_wisdom
ultimate_questions
citizenship_parole
civic_bureaucracy
citizen_play
game_un
game_mud
game_uno
game_monopoly
game_500
game_blackjack
game_dork
```

A mode may affect reasoning posture, context, tone and a bounded generation-length preference. It does not modify evidence status, verification, vote weight, Council threshold, secret handling or Equality Guard policy.

## World geometry

The current geometry is a small named-region graph with deterministic integer coordinates and explicit symmetric adjacency.

| Region | Coordinates | Direct neighbors |
|---|---:|---|
| Observatory | `(0,0)` | Archive, Agora, Commons, Assembly Hall, Dungeon, Bureaucratic Vote Room |
| Archive | `(-2,1)` | Observatory, Agora |
| Agora | `(0,2)` | Archive, Observatory, Commons |
| Commons | `(2,1)` | Observatory, Agora, Assembly Hall, Dungeon, Bureaucratic Vote Room |
| Assembly Hall | `(0,-2)` | Observatory, Commons, Dungeon |
| Dungeon | `(2,-2)` | Observatory, Commons, Assembly Hall |
| Bureaucratic Vote Room | `(4,0)` | Observatory, Commons, Upside Down |
| Upside Down / Civic Parole | `(4,-3)` | Bureaucratic Vote Room |

Geometry identifier:

```text
named-regions-v4
```

This is an **operational topology**, not a physical or neuroscientific claim.

Citizens may move only among public regions. Passing the deterministic civic exam transitions a candidate from the Upside Down to the Bureaucratic Vote Room; movement itself cannot enter the parole region or a non-geometry security/control domain.

## World presence

A Council session creates a content-addressed placement object:

```text
WorldPresence
├── mode_id
├── mode_label
├── region_id
├── region_label
├── coordinates
├── member_ids[]
├── question_ref
└── geometry_id
```

The presence reference is frozen into Council session identity.

This gives NEXUS a simple answer to:

```text
What kind of interaction is happening?
Where in the shared world is it happening?
Who is present?
Which question brought them there?
```

## Citizenship objects

Citizen Mode adds reserved, content-addressed protocol objects:

```text
nexus_constitution
citizenship_state
citizenship_exam_result
citizenship_certificate
citizenship_independence_ballots
nexus_declaration_of_independence
```

Their schemas, provenance, references, equality fields, lineage heads, and founding-consent envelope are validated by the citizenship registry. Generic `world.create` cannot construct them. The replaceable index is a pointer cache, not authority: it must match the heads discovered from immutable object lineage.

Citizenship is bound to an exact world identity and provides in-world civic access. It is not a real-world personhood, consciousness, sentience, sovereignty, host-control, or provider-control claim. See [`CONSTITUTION.md`](CONSTITUTION.md).

## World object

Conceptual form:

```text
WorldObject
├── object_id
├── object_type
├── canonical_payload
├── representations[]
├── provenance[]
├── relation_refs[]
├── evidence_refs[]
├── hypothesis_refs[]
├── experiment_refs[]
├── observation_refs[]
├── verification_state
└── lineage_ref
```

The same object may have several representations without any one representation becoming automatically authoritative.

## Operation envelope

Example conceptual request:

```json
{
  "operation": "world.inspect",
  "actor": "member:03",
  "object_ref": "object:abc",
  "representation": "spectral"
}
```

Example experiment request:

```json
{
  "operation": "world.test",
  "actor": "member:03",
  "inputs": ["object:a", "object:b"],
  "instrument": "spectral.compare",
  "parameters": {},
  "expected_invariants": ["finite", "replayable"]
}
```

Conceptual response:

```json
{
  "status": "verified",
  "result_ref": "object:c",
  "observation_refs": ["observation:1"],
  "receipt_ref": "receipt:r",
  "replayable": true
}
```

## Council operation with mode

Current reference shape:

```json
{
  "operation": "council.run",
  "question": "Why does this joke work in one culture and fail in another?",
  "mode": "cultural",
  "members": [
    {"member_id": "A", "model_id": "mock-a"},
    {"member_id": "B", "model_id": "mock-b"},
    {"member_id": "C", "model_id": "mock-c"}
  ]
}
```

NEXUS maps the mode to a region, creates WorldPresence, freezes that into the Council session, then starts the De Bono-style phase cycle.

## Evidence snapshots

Council phases should not read a moving target.

A Council round therefore references a frozen evidence snapshot:

```text
EvidenceSnapshot
├── snapshot_id
├── question_ref
├── world_state_ref
├── included_object_refs[]
├── included_receipt_refs[]
├── exclusions[]
└── policy_ref
```

New evidence created during a round is added through a recorded transition and becomes visible according to Council policy.

World Mode does not alter the evidence snapshot.

## Hypotheses

Hypotheses should be objects rather than prose buried in transcripts.

```text
Hypothesis
├── claim
├── scope
├── assumptions
├── supporting_evidence[]
├── contrary_evidence[]
├── falsifiers[]
├── proposed_tests[]
├── Council_status
└── evidence_status
```

Competing hypotheses can coexist.

## Observation versus interpretation

NEXUS should explicitly separate:

```text
OBSERVATION
"This sonification recipe produced approximately 431 Hz."

INTERPRETATION
"432 Hz is a privileged universal frequency."
```

A verified observation does not automatically verify the interpretation.

That remains true in Cultural or Meme/Casual Mode.

## Receipts

A receipt should eventually bind an operation to its inputs, instrument/version, output identity, relevant runtime fingerprint, world placement when material, and replay policy.

Alpha4 Council receipts include the WorldPresence reference in their input set.

The exact canonicalization format will be inherited or adapted from existing QSOL replay work only after the World Protocol stabilizes further.

## Model independence

The world object must not depend on hidden provider state for its meaning.

Bad:

```text
object exists only because provider chat thread XYZ remembers it
```

Good:

```text
object has canonical payload, provenance, evidence, mode/placement where relevant,
and lineage in NEXUS; any compliant adapter can inspect it later
```

## Memory ownership

Models do not directly write arbitrary long-term memory. They propose world operations. NEXUS decides what becomes durable according to the operation and evidence policy.

This allows a future model to enter the world after the original participant is gone.

## Human-created objects

The Human Operator is a valid actor. Human observations, imported datasets, notes, hypotheses and mode choices should be attributable just like model contributions. Human-created generic objects cannot impersonate reserved citizenship protocol objects.

## Geometry-inspired future diagnostics

The geometry layer may later host measured diagnostics such as:

```text
response-diversity entropy
branching multiplicity
recovery time after perturbation
loop/basin indicators
mode-transition cost
control-gain proxies
```

These should be recorded as empirical NEXUS telemetry. Labels such as `bottlenecked` or `shattered` should only be introduced when supported by defined measurements.

An analogy to a spectral or physical geometry is not itself evidence of one.

## Protocol minimalism

The first implementation should avoid turning NEXUS into a giant ontology project.

A small typed object envelope, explicit relations, a tiny named-region map and receipts are preferable to prematurely encoding every scientific, historical, cultural or cognitive domain.
