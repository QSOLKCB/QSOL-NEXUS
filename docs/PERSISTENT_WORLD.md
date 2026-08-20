# Persistent World — alpha8

QSOL-NEXUS alpha8 does not replace the existing WorldStore, Continuity, Ark, Council-session, or LATTICE world-presence machinery.

It makes those existing durable primitives easier to use as one inspectable research world.

## Architecture

```text
existing content-addressed WorldStore objects
             |
             +-- existing Continuity / Ark history
             +-- existing council_session objects
             +-- existing world-presence / movement objects
             |
             +-- alpha8 world_relation
             +-- alpha8 world_hypothesis
             +-- alpha8 world_experiment
             |
             +-- derived minority-report search
             +-- derived mode history
             +-- bounded exact-object export/import
```

There is no second canonical database and no vector index with authority over WorldStore history.

## Relations

`world_relation` is an explicit typed edge between two already-existing WorldStore objects.

A relation says that NEXUS recorded an edge. It does not prove that the semantic interpretation of the edge is true.

```text
RELATION != FACT
```

Public operations:

```text
world.relation.create
world.relation.search
```

Relation search is a deterministic derived view. Text matches and relation labels create no evidence authority.

## Hypotheses

Hypotheses are immutable workflow records with predecessor lineage.

States are:

```text
PROPOSED
ACTIVE
CHALLENGED
RETIRED
```

The state is a workflow label, not a truth classification.

A `RETIRED` hypothesis is terminal. Historical objects are never edited to reactivate it; a new hypothesis lineage can be created instead.

Public operations:

```text
world.hypothesis.create
world.hypothesis.search
```

```text
HYPOTHESIS_STATE != TRUTH
```

## Experiment lineage

Experiments use immutable predecessor-linked records.

Stages are:

```text
PLANNED
OBSERVED
CLOSED
```

An initial record must be `PLANNED`. Observation/result records bind exact existing WorldStore references. Recording a result reference establishes lineage, not empirical truth.

```text
EXPERIMENT_RECORD != EMPIRICAL_VERIFICATION
```

Public operations:

```text
world.experiment.create
world.experiment.search
```

## Existing Council and movement history

Alpha8 reuses existing canonical objects instead of copying them into a new format.

Council sessions remain ordinary `council_session` WorldStore objects.

World placement, adjacent movement, and explicit LATTICE migration remain the existing `nexus-world-lattice/1` event objects.

`world.mode.history` is a bounded derived view across these existing records.

```text
MODE_HISTORY != COGNITIVE_GEOMETRY
```

## Searchable minority reports

`world.minority.search` scans committed `council_session` objects and returns the existing `result.minority_reports` records with their session, question, mode, and evidence-state context.

The search view does not duplicate or promote the minority report.

```text
MINORITY_REPORT != EVIDENCE_PROMOTION
SEARCH_MATCH != EVIDENCE
```

## Portable export and import

`world.export` produces a bounded `nexus-persistent-world-export/1` envelope containing exact canonical WorldObject records in deterministic source order.

The bundle is content addressed as:

```text
world-export:<sha256>
```

The maximum alpha8 exchange bundle contains 256 objects. Larger worlds must select an explicit subset.

`world.import`:

1. validates the complete envelope before mutation;
2. verifies every `object:<sha256>` identity;
3. rejects duplicate identities and unknown export versions;
4. rejects credential-shaped material rather than rewriting it;
5. preserves exact source object type, payload, provenance, and object identity;
6. reuses exact objects already recognized locally;
7. appends a separate `world_import_receipt`.

Imported objects are not relabelled or re-authored as NEXUS claims.

```text
IMPORT != AUTHORITY
EXPORT_HASH != SEMANTIC_TRUTH
```

An infrastructure failure during a multi-object append cannot be rolled back without rewriting append-only history. Any already-committed source object remains a valid exact content-addressed object; retrying the same bundle is identity-safe and reuses it.

## Migration/version policy

Alpha8 freezes persistent-world major version 1.

Pre-alpha8 WorldStore objects remain valid. They are not rewritten merely to gain alpha8 metadata.

New semantic records are additive objects.

Unknown persistent-world export majors fail closed.

Historical objects are never reinterpreted in place.

```text
MIGRATION != REINTERPRETATION
PERSISTENCE != EPISTEMIC_PRIVILEGE
```

## Public operations

```text
world.persistence.policy
world.relation.create
world.relation.search
world.hypothesis.create
world.hypothesis.search
world.experiment.create
world.experiment.search
world.minority.search
world.mode.history
world.export
world.import
```

All alpha8 object creation routes through the existing real-world mutation gate. Generic `world.create` cannot forge alpha8 runtime-owned relation, hypothesis, experiment, or import-receipt objects.
