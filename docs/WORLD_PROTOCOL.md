# NEXUS World Protocol

## Purpose

The World Protocol is the stable interface between cognitive actors and the persistent NEXUS world.

Models may reason however they like internally. Durable interaction with the shared world occurs through explicit operations.

## Design principle

> **The model proposes. The world records, computes, verifies, and remembers.**

The protocol should remain model-neutral and transport-neutral.

## Planned primitives

```text
world.inspect
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
```

These names are provisional conceptual syscalls, not implemented commands in the documentation-only alpha.

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

## Receipts

A receipt should eventually bind an operation to its inputs, instrument/version, output identity, relevant runtime fingerprint, and replay policy.

The exact canonicalization format will be inherited or adapted from existing QSOL replay work only after the new World Protocol stabilizes.

## Model independence

The world object must not depend on hidden provider state for its meaning.

Bad:

```text
object exists only because provider chat thread XYZ remembers it
```

Good:

```text
object has canonical payload, provenance, evidence and lineage in NEXUS;
any compliant adapter can inspect it later
```

## Memory ownership

Models do not directly write arbitrary long-term memory. They propose world operations. NEXUS decides what becomes durable according to the operation and evidence policy.

This allows a future model to enter the world after the original participant is gone.

## Human-created objects

The Human Operator is a valid actor. Human observations, imported datasets, notes, and hypotheses should be attributable just like model contributions.

## Protocol minimalism

The first implementation should avoid turning NEXUS into a giant ontology project. A small typed object envelope plus explicit relations and receipts is preferable to prematurely encoding every scientific or cognitive domain.
