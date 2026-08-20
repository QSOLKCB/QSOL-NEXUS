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
             +-- bounded exact-object export
             +-- quarantined source-preserving import
```

There is no second canonical database and no vector index with authority over WorldStore history.

## Relations

`world_relation` is an explicit typed edge between two already-existing local WorldStore objects.

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

An initial record must be `PLANNED`. Observation/result records bind exact existing local WorldStore references. Recording a result reference establishes lineage, not empirical truth.

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

Council sessions remain ordinary locally committed `council_session` WorldStore objects.

World placement, adjacent movement, and explicit LATTICE migration remain the existing `nexus-world-lattice/1` event objects.

`world.mode.history` is a bounded derived view across these existing records.

```text
MODE_HISTORY != COGNITIVE_GEOMETRY
```

## Searchable minority reports

`world.minority.search` scans locally committed `council_session` objects and returns the existing `result.minority_reports` records with their session, question, mode, and evidence-state context.

The search view does not duplicate or promote the minority report.

```text
MINORITY_REPORT != EVIDENCE_PROMOTION
SEARCH_MATCH != EVIDENCE
```

Foreign objects received through `world.import` are quarantined as `world_imported_object` wrappers, so a hash-valid foreign `council_session` cannot silently enter local Council history or minority-report search.

## Portable export

`world.export` produces a bounded `nexus-persistent-world-export/1` envelope containing exact canonical WorldObject records in deterministic source order.

The bundle is content addressed as:

```text
world-export:<sha256>
```

The maximum alpha8 exchange bundle contains 256 objects and is also capped at 1,048,576 canonical UTF-8 bytes. Larger worlds must select an explicit subset.

```text
EXPORT_HASH != SEMANTIC_TRUTH
```

## Quarantined import

`world.import` is for portable exchange, not recovery authority. Exact recovery of a trusted local NEXUS history remains the job of the existing World Ark / Continuity machinery.

Import therefore follows a stricter boundary:

1. validate the complete `nexus-persistent-world-export/1` envelope before mutation;
2. enforce the object-count and canonical-byte ceilings;
3. verify every source `object:<sha256>` identity;
4. reject duplicate identities and unknown export versions;
5. reject credential-shaped or credential-labelled source material rather than rewriting it;
6. if an exact source object is already independently present in local history, record it as already local;
7. otherwise preserve the complete source WorldObject inside an inert `world_imported_object` wrapper in the same WorldStore;
8. never materialize a foreign source object type directly as a live local Council, governance, security, evidence, or runtime object;
9. append a separate `world_import_receipt` binding the source bundle, already-local references, and quarantine wrappers.

The wrapper preserves the exact source object reference and exact source object body while making the authority boundary mechanically visible:

```text
IMPORTED_OBJECT != LOCAL_COMMITTED_OBJECT
IMPORT != AUTHORITY
```

Re-importing the same source object reuses the same deterministic quarantine wrapper when its preserved source bytes match.

An infrastructure failure during a multi-object append cannot be rolled back without rewriting append-only history. Any already-created quarantine wrapper remains an inert exact historical record, and retrying the same bundle is identity-safe.

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

All alpha8 object creation routes through the existing real-world mutation gate. Generic `world.create` cannot forge alpha8 runtime-owned relation, hypothesis, experiment, imported-object, or import-receipt objects.
