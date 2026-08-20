# NEXUS 2.1.1 Release Notes

## Status

This document describes the **2.1.1 release candidate**. PR #61 does not create the `v2.1.1` tag or publish a GitHub Release.

The release gate is exact:

> **Only the exact reviewed-and-green merged PR #61 commit may receive `v2.1.1`.**

## Why 2.1.1 instead of 2.1.0

A historical `v2.1.0` tag already exists at:

```text
v2.1.0 -> 839303ea512631e527073682343341742cead975
```

That commit is the merged PR #55 LATTICE milestone. It predates PRs #56–#60 and its checked-in runtime still identifies itself as `2.0.0`.

NEXUS does **not** rewrite that history. The existing tag is preserved as an immutable historical premature post-stable marker. The first candidate containing the complete hardened PR #55–#60 extension line is therefore `2.1.1`.

```text
HISTORICAL_TAG != RELEASE_TARGET
```

## Frozen v2.0 baseline

NEXUS 2.1.1 is an additive post-stable release line. It does not redefine the published NEXUS 2.0 software/proof identity:

```text
v2.0.0          cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
Lean phase      PR #53
Publication     PR #54
Zenodo DOI      10.5281/zenodo.21895577
```

The v2.0 publication remains the formal-verification correspondence target for the proofs published with that record. New 2.1.1 extension behavior is tested and hardened here but is not silently claimed as covered by the old Lean publication.

## Release identity

```text
runtime         2.1.1
Python package  2.1.1
Rust TUI        2.1.1
protocol        nexus/0.15
candidate PR    #61
candidate base  merged PR #60
future tag      v2.1.1
```

The protocol moves from `nexus/0.14` to `nexus/0.15` because the post-stable line introduces additive public operations for world presence, instruments, persistent-world lineage/exchange, and integration workflows.

Existing operation semantics are not intentionally broken by this minor protocol bump.

## What is new since v2.0.0

### PR #55 — LATTICE-backed world presence and migration

- frozen LATTICE v1 consumer profile and semantic fingerprint;
- explicit `world.place`, adjacent `world.move`, `world.migrate`, and `world.presence` operations;
- immutable placement/movement/migration history;
- exact source/target LATTICE identity preservation;
- separate NEXUS object identity and LATTICE content binding;
- Ark/restart recovery coverage;
- unknown-major/profile/fingerprint-drift rejection.

Boundary:

> **LATTICE position is not a cognitive coordinate.**

### PR #56 — Default-deny instrument admission

- versioned `nexus-instrument-admission/1` policy;
- first admitted executable instrument: `nexus.integer-primality/1`;
- closed input/output and claim boundaries;
- deterministic content-addressed intent, execution, and receipt identities;
- receipt verification through re-execution of the admitted bounded instrument;
- non-admitted QEC/SPECTRAL/sonification/symbolic-numeric candidates remain non-executable.

Boundary:

> **Instrument result is not truth. Deterministic is not authoritative.**

### PR #57 — Persistent world

- typed relations;
- immutable hypothesis states and predecessor lineage;
- immutable experiment stages and predecessor lineage;
- searchable minority reports;
- derived mode history;
- migration/version policy;
- bounded portable export/import;
- quarantine wrappers for foreign hash-valid objects rather than direct authority import.

Boundaries:

```text
RELATION != FACT
HYPOTHESIS_STATE != TRUTH
EXPERIMENT_RECORD != EMPIRICAL_VERIFICATION
IMPORT != AUTHORITY
```

### PR #58 — Remote operator engineering

- Rust `nexus-remote-setup` terminal surface;
- non-secret auth-profile references only;
- live xAI model discovery and ephemeral mixed rosters;
- five-seat public Chair / four-seat xAI limits;
- explicit provider equality and zero-privilege boundaries;
- operator-authorized live-xAI acceptance harness with owner-only canonical archive;
- hermetic self-test with live network disabled in CI.

Raw credentials are not accepted by the Rust operator surface.

### PR #59 — Three Minds, One World completion

The canonical sequential demonstration now integrates the newer contracts rather than running as a parallel demo:

- Mind A persists a task-bound hypothesis, planned experiment, and admitted baseline instrument receipt;
- Mind B arrives later, discovers prior refs, performs exact baseline replay, and preserves critique/challenged lineage;
- Mind C receives the coordinator-owned full-fixture instrument result and attempts falsification;
- the CLOSED experiment binds the final Mind C hypothesis;
- a persisted integration manifest binds all restart-verifier refs;
- cross-run ref mixtures fail closed;
- LATTICE presence moves Observatory → Archive → Agora → Observatory;
- a deterministic reference Council preserves equal votes and a searchable minority report.

Boundary:

> **Persistent lineage is not truth. Multi-model consensus is not evidence.**

### PR #60 — Post-stable extension hardening

PR #60 created the separate machine hardening boundary for the #55–#59 extension line and preserved the old v2.0 publication as immutable historical input.

Final reviewed PR #60 head:

```text
0e3b0e94053081ee77a1d969d3d60b81aeeb997c
```

Merged PR #60 commit:

```text
80cda46e614f44b47861471cb329e29a348cab43
```

Hardening artifact:

```text
artifact ID  9421970922
SHA-256      16674e62495ed5b66f69269ec2e5fb9cdb300b39bf2b45212f00085daa83ffbb
```

PR #61 treats those as provenance evidence. A hardening report still does not create release authority.

## 2.1.1 candidate hardening

The PR #61 candidate adds an exact-commit verifier that requires:

- runtime/Python/Rust/Cargo-lock identity alignment at `2.1.1`;
- protocol `nexus/0.15` alignment;
- README and strict-JSON README4AI coupling;
- exact `v2.0.0` historical binding;
- exact `v2.1.0 -> 839303ea...` historical binding;
- `v2.1.1` to remain absent during candidate review;
- merged PR #60 to be an ancestor of the candidate;
- the v2.0 DOI/publication identity to remain unchanged;
- extension and historical regression suites;
- hermetic alpha9 self-test only;
- lockfile-strict Rust all-target tests/checks and rustfmt;
- clean tracked bytes and unchanged commit/tree before and after candidate execution.

## Live xAI empirical gate

A real xAI acceptance session remains **operator-run-required**.

It is deliberately non-blocking for this software release because the provider transport, auth boundary, hermetic conformance, and acceptance harness are already reviewed independently. CI does not receive a provider credential and cannot close the empirical gate.

No 2.1.1 release note may claim a successful live xAI session unless an actual operator archive exists.

```text
LIVE_ACCEPTANCE != SCIENTIFIC_VALIDATION
```

## Compatibility

NEXUS 2.1.1 preserves:

- canonical `object:<sha256>` WorldStore identity;
- one-member/one-vote Council arithmetic;
- existing provider/model equality rules;
- existing v2.0 operations and authority semantics;
- historical v2.0 tag/publication identity;
- historical v2.1.0 tag identity;
- live stochastic inference as non-replayable;
- credentials outside semantic/world state.

See [`COMPATIBILITY.md`](COMPATIBILITY.md) for the detailed protocol and persistence boundary.

## Explicit non-claims

NEXUS 2.1.1 does not claim that:

- Council consensus is truth or evidence;
- a persistent hypothesis or experiment is empirically verified merely because it is stored;
- instrument output automatically promotes evidence or truth;
- LATTICE addresses are physical/cognitive coordinates;
- foreign hash-valid imports become local authority;
- provider identity creates vote weight or epistemic privilege;
- a live xAI acceptance has occurred unless an operator actually ran and archived it;
- the v2.0 Lean proofs automatically cover every post-v2.0 extension;
- green CI itself creates release authority.

## Post-merge release procedure

After PR #61 is reviewed, fully green, and merged:

1. resolve the exact merged PR #61 commit;
2. verify the required workflows and exact-commit candidate report against that identity;
3. verify `v2.1.0` still points to `839303ea...`;
4. create **new** tag `v2.1.1` on the exact merged PR #61 commit;
5. publish the GitHub Release from that same tag/commit;
6. never move `v2.0.0` or `v2.1.0` as part of this release.

> **Release metadata records an authority decision. It does not manufacture one.**
