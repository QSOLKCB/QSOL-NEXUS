# WorldStore Continuity / The Ark Protocol

PR #46 adds a continuity layer around the existing NEXUS WorldStore.

The existing `object:<sha256>` identity format is not replaced. Continuity adds replicated persistence, a quorum-selected history spine, deterministic scrub/repair, portable cold Arks, additive digest migration receipts and non-destructive recovery.

> **A degraded WorldStore may become read-only. It must not invent history merely to remain writable.**

## 1. Compatibility

A pre-#46 WorldStore remains valid. On first continuity-aware open, its already-validated immutable objects are bound into generation `0` as a `legacy_baseline` continuity manifest. Object bytes and object IDs are unchanged.

With one persistent root, the continuity quorum is `1`. Additional replicas are opt-in.

## 2. Replicas and quorum

When additional roots are configured, NEXUS requires a strict majority write/read quorum. For three replicas the default quorum is two.

Every committed object is therefore:

1. canonicalized and assigned its normal `object:<sha256>` identity;
2. persisted to the configured replica set;
3. admitted only when the object reaches quorum;
4. bound into the next immutable continuity manifest;
5. recognized only when that manifest becomes the majority HEAD.

A lone replica with a numerically newer generation has no authority to replace a history supported by quorum.

> **Quorum beats recency.**

## 3. Continuity manifests

Continuity manifests use schema `nexus-world-continuity/1` and content-addressed `world-manifest:<sha256>` references.

Generation `0` records the verified legacy inventory. Every later generation binds exactly one committed WorldStore object to its predecessor manifest.

The mutable `continuity/HEAD.json` file is only a pointer. It is not historical authority. A majority of validated HEAD pointers selects one immutable manifest ref; that ref cryptographically binds the chain behind it.

Cross-process continuity mutations are serialized through an owner-only lock.

## 4. Failure domains

Continuity status reports every replica and its detected backing-device failure domain. Raw replica count and independent failure-domain count are separate values.

Three directories on one physical filesystem are therefore reported as three replicas but one detected device failure domain. Redundancy claims must not confuse copy count with independent hardware failure resistance.

## 5. Scrub and repair

`world.continuity.scrub` is observational unless `repair: true` is explicitly requested.

Scrub walks the recognized manifest chain and recognized object set. A missing or corrupt replica copy may be repaired only from a source that independently passes the existing content-address verification for the expected ref.

Mutable HEAD pointers may be repointed only to a history already selected by quorum.

Repair is never based on newest timestamp, largest generation number or model opinion.

Zero-known-good-copy cases are reported as unrecoverable and are not guessed.

Successful repair produces an immutable `world-repair:<sha256>` receipt. The Guardian may record a `substrate_scar` pointing to that receipt, but the Guardian does not perform the repair and receives no storage authority.

## 6. World Arks

A NEXUS World Ark is a new, cold directory containing:

```text
NEXUS-ARK-.../
├── ARK_MANIFEST.json
├── SHA256SUMS
├── FORMAT.md
├── RECOVERY.md
├── objects/
└── manifests/
```

`ARK_MANIFEST.json` is canonical JSON and contains:

- Ark identity;
- recognized continuity HEAD;
- generation;
- Compute Epoch when the clock is available;
- complete recognized object-ref list;
- complete continuity-manifest-ref list;
- SHA-256 for every payload file;
- serialization and restore policy.

An Ark does not require NEXUS, a database, a daemon, a model provider or a cloud service merely to understand its storage format.

Ark creation requires a current read quorum for every recognized object. It refuses to snapshot a silently degraded subset.

## 7. Verification and recovery

Ark verification checks:

- canonical Ark manifest bytes;
- Ark content-address identity;
- every listed file digest;
- every WorldStore object's original content-address identity;
- every continuity manifest identity;
- generation/predecessor chain;
- the recognized Ark HEAD;
- the deterministic `SHA256SUMS` index.

Recovery is intentionally non-destructive:

```text
Ark
 ↓ verify
new empty target
 ↓ copy + reconstruct HEAD
verify recovered WorldStore
 ↓
operator may later choose it as the live root
```

An existing target is never overwritten by the recovery operation.

## 8. Digest and format migration

PR #46 does not silently redefine SHA-256 object identity.

Instead, a migration receipt may add an alternate SHA-512 digest for the exact canonical source bytes while retaining:

- original `object:<sha256>` ref;
- original source bytes;
- source format;
- migration provenance;
- explicit statement that the alternate digest is additive.

Future format migration must follow the same rule: preserve the source and create provenance for the successor representation rather than rewriting history in place.

## 9. Public runtime operations

```text
world.continuity.policy
world.continuity.status
world.continuity.scrub
world.continuity.migration.receipt
world.ark.create
world.ark.verify
world.recovery.inspect
world.recovery.restore
```

`system.health` publishes continuity state and `system.operations` publishes these operations.

## 10. Authority invariants

```text
ARK-I1  Existing WorldStore object identities remain valid.
ARK-I2  Multi-replica recognized history is selected by strict majority quorum, never recency alone.
ARK-I3  Every recognized object remains content-address verified.
ARK-I4  Repair requires a verified source already bound by recognized history.
ARK-I5  Zero-known-good and no-head-quorum conditions fail closed.
ARK-I6  Mutable HEAD indexes never outrank immutable manifests.
ARK-I7  Ark creation never snapshots an object set below read quorum.
ARK-I8  Ark verification is independent of model inference.
ARK-I9  Recovery restores only to a new target and never overwrites the live world.
ARK-I10 Digest migration is additive; source bytes and source refs remain preserved.
ARK-I11 Replica count, quorum and failure domain never create Council, evidence or civic authority.
ARK-I12 Guardian scars may observe verified repairs but the Guardian receives no storage authority.
```

The Ark Protocol is the final persistence foundation before the deferred 2.0-beta hardening pass.