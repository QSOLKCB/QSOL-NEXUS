# LATTICE-backed world-presence contract

## Purpose

This contract closes the NEXUS roadmap gap between the persistent WorldStore and the now-versioned QSOL LATTICE address contract. It adds explicit object placement, recorded `world.move` transitions, address/profile migration, and deterministic presence-lineage reconstruction without changing the authority model of either repository.

The core rule is deliberately boring in the best way:

```text
NEXUS world region != LATTICE address
LATTICE address != truth score
LATTICE address != cognitive coordinate
movement != epistemic authority
migration != silent rewrite
```

NEXUS regions remain the named operational topology defined by `geometry.py`. LATTICE references remain storage-only identities. A presence event may carry both, but NEXUS does not infer one from the other.

## Frozen LATTICE profile

The consumer contract pins:

```text
profile protocol     qsol-lattice-profile-descriptor/1
profile id           qsol-3x3x3-sierpinski-derived-memory/1
profile fingerprint  sha256:6e7c4a9a781d552a2b561d334a8435c12efe2908fcd24a0f152935aded555bcf
reference protocol   qsol-lattice-reference/1
migration protocol   qsol-lattice-migration/1
authority             storage-only
```

Compatibility follows LATTICE itself:

- the exact profile ID plus exact semantic fingerprint is compatible;
- additive non-semantic profile metadata is compatible;
- an unknown major is rejected;
- an unknown profile in the same major is rejected;
- a changed semantic fingerprint under the same profile ID is rejected and requires a versioned migration;
- historical address identity is `(profile_id, address)`;
- profile/address migration is explicit and derived, never an in-place historical rewrite.

`fixtures/lattice/nexus-consumer-v1.json` is the language-neutral conformance fixture used by NEXUS tests.

## NEXUS content binding

A NEXUS WorldStore object already has a domain-separated identity:

```text
object:<sha256>
```

That identifier is preserved exactly. NEXUS does **not** strip the `object:` prefix and pretend the remaining digest is a LATTICE `content_ref`.

When a WorldObject is placed, NEXUS derives the optional LATTICE content binding as:

```text
sha256(canonical_json(WorldObject.as_dict()))
```

and records it as `sha256:<hex>`. If a caller supplies a different `content_ref`, placement fails closed. This gives LATTICE a portable integrity reference without changing or relabelling the canonical NEXUS object identity.

## Presence event model

World presence is append-only history stored as ordinary immutable WorldStore objects.

Object types:

```text
world_presence_placement
world_presence_move
world_presence_lattice_migration
```

Every event records:

- the immutable subject `object:<sha256>`;
- a monotonically increasing lineage sequence;
- the named NEXUS region;
- the NEXUS geometry identity and topology reference;
- the storage-only LATTICE reference;
- the previous presence-event reference, or `null` for a placement root;
- transition-specific source/target identities;
- `authority_effect: none`.

Presence lineages are reconstructed from the supplied head event and are bounded to 4096 events. NEXUS verifies predecessor links, subject identity, sequence continuity, transition type, event provenance, region validity, LATTICE reference validity, and the canonical content binding before returning a lineage.

A presence head is lineage-relative, not a claim that the whole repository has one globally unique mutable position for the object. Multiple explicit lineage roots or branches are therefore detectable history, not silently overwritten state. The response advertises `branching_uniqueness_claimed: false`.

## Placement

`world.place` creates a lineage root from three independent facts:

```text
subject object_ref
explicit named NEXUS region_id
explicit storage-only LATTICE reference
```

There is no automatic region-to-address mapper and no semantic coordinate inference.

## Movement

`world.move` is one explicit adjacent-region transition. It requires:

- the subject object reference;
- the previous presence-event reference;
- a different target region;
- graph distance exactly one in the current named NEXUS topology;
- an explicit target LATTICE reference using the same LATTICE profile.

The move event retains source and target region IDs and source and target `(profile_id, address)` identities. A longer trip is represented by multiple immutable movement events. A LATTICE profile change cannot hitchhike on `world.move`; it requires `world.migrate`.

Changing an address during a move is not an in-place rewrite because the predecessor reference and both address identities are retained in the transition event.

## LATTICE migration

`world.migrate` validates the same migration semantics as LATTICE v1:

- `preserve_source_identity` must be exactly `true`;
- at most 10,000 mapping rows;
- source mappings are unique;
- `identity` migration cannot change the profile or address meaning;
- `explicit-map` requires at least one mapping;
- the current address must have an explicit mapping when `explicit-map` is used;
- source and target profile descriptors must be compatible with the frozen NEXUS consumer contract.

The 10,000-row value is the LATTICE contract ceiling. NEXUS control-plane aggregate-size and list-cardinality budgets are applied before operation dispatch and may impose a lower practical request bound.

The resulting presence event records the LATTICE-style migrated-reference envelope containing the complete old and new references plus explicit source and target address identities. The named NEXUS region does not change during LATTICE migration.

## Persistence, replay, and Ark recovery

Presence events are ordinary content-addressed WorldStore objects. The existing ContinuityWorldStore therefore supplies quorum persistence and continuity history without a second database. The existing World Ark mechanism includes those objects in normal WorldStore recovery inventory; tests restore an Ark into a new empty WorldStore and reconstruct the same presence lineage from the preserved head event.

This is deterministic replay of **world-presence lineage**, not a new claim that stochastic model inference is replayable.

## Public operations

The final public runtime adds:

```text
world.lattice.policy
world.lattice.validate_migration
world.place
world.move
world.migrate
world.presence
```

The three mutations pass through the established trap mutation gate. The three presence object types are reserved from raw `world.create`, so callers cannot bypass the validated placement/movement surface through the public control plane.

## Roadmap closure

This contract provides executable evidence for these previously deferred areas:

- final schema/version migration policy for the LATTICE-addressed world layer;
- explicit recorded `world.move` transitions;
- richer explicit object-to-region placement rules;
- persistent world-presence and movement history;
- persistent-world LATTICE migration/version policy;
- import/export and Ark recovery of those presence histories through the existing ContinuityWorldStore.

It does **not** close generalized replay of arbitrary model operations, semantic entropy scoring, cognitive-coordinate claims, truth scoring by position, distributed-database semantics, or any biological interpretation of LATTICE addresses.
