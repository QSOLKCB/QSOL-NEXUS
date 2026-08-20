# NEXUS post-stable extension hardening

NEXUS 2.0 is already a frozen public release with a separate Lean 4 and Zenodo reproducibility chain.

The later PR #55–#59 line adds substantial post-stable functionality:

```text
v2.0.0 stable baseline
        |
        +-- PR #55  LATTICE world presence / migration
        +-- PR #56  default-deny instrument admission
        +-- PR #57  persistent world
        +-- PR #58  remote operator / live-xAI acceptance harness
        +-- PR #59  Three Minds, One World integration
        |
        v
2.1 pre-release extension hardening
```

This phase exists so those additions cannot silently inherit the release authority, formal-verification claims, or publication identity of `v2.0.0`.

## Frozen v2.0 baseline

The extension line treats the following identity as immutable historical input:

```text
tag                 v2.0.0
stable commit       cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
Lean phase          PR #53
publication phase   PR #54
Zenodo DOI          10.5281/zenodo.21895577
```

The hardening runner verifies the tag-to-commit binding directly from Git history.

It does **not** rebuild, rewrite, move, or reinterpret the stable tag or the DOI-bound publication payload.

```text
V2_0_STABLE != POST_STABLE_EXTENSION_HEAD
```

## Exact extension merge chain

The first hardening candidate pins the exact merged chain:

```text
PR #55  839303ea512631e527073682343341742cead975
PR #56  c42414024a25e785dd29f406a829e3e02a8239bc
PR #57  f4c717bcab0e03811856d5061677678b35044ca1
PR #58  3244d439192769908fa74eac69a0c430ce5814ae
PR #59  0b2a3ee467faad89e5a56b51779dc20ba13ad75d
```

`tools/nexus_extension_hardening.py` requires every commit to exist, requires each to be an ancestor of the candidate HEAD, and requires the chain to remain monotonic in that order.

A PR number in prose is not enough to satisfy this gate.

## What is being hardened

### LATTICE world presence

The gate re-runs `tests/test_world_lattice.py` and preserves:

- exact supported LATTICE profile identity;
- explicit placement/movement/migration;
- source/target address preservation;
- content binding;
- Ark recovery;
- unknown-major and fingerprint-drift rejection;
- zero epistemic/governance authority.

```text
LATTICE_POSITION != COGNITIVE_COORDINATE
```

### Instruments and persistent world

The gate re-runs `tests/test_instruments.py` and verifies the machine contracts remain default-deny and source-preserving.

Only the bounded integer-primality instrument is currently admitted by the alpha7 contract. QEC receipt replay, SPECTRAL, sonification, and symbolic/numeric adapters remain catalogued but non-executable until separately reviewed.

Persistent-world import remains quarantine-first:

```text
INSTRUMENT_RESULT != TRUTH
IMPORT != AUTHORITY
PERSISTENT_LINEAGE != TRUTH
```

### Remote operator

The gate runs the hermetic live-xAI acceptance self-test plus the Rust `nexus-remote-setup` test target and rustfmt.

CI does not receive a provider credential and does not authorize a live xAI call.

The empirical alpha9 gate therefore remains open until an operator actually runs and archives the live acceptance harness.

```text
REMOTE_MODEL != PRIVILEGED_MODEL
LIVE_ACCEPTANCE != SCIENTIFIC_VALIDATION
```

### Three Minds, One World

The gate re-runs `tests/test_three_minds_demo.py`, including:

- admitted instrument receipts;
- exact replay binding;
- task-bound hypothesis lineage;
- closed experiment binding to the final hypothesis;
- restart verifier coherence;
- LATTICE handoff history;
- minority-report preservation;
- cross-run mixing rejection.

```text
MULTI_MODEL_CONSENSUS != EVIDENCE
```

## Inherited v2.0 regression boundary

The extension matrix also re-runs the key historical release-hardening, Grok-audit closure, post-merge audit, release-upgrade, and release-candidate regression modules.

The old `release/release_candidate.json` and `release/hardening_matrix.json` remain identified as the historical NEXUS 2.0 candidate material. The new extension line uses separate files:

```text
release/post_stable_extension_candidate.json
release/post_stable_extension_matrix.json
```

This separation is deliberate. A current development branch must not rewrite old release paperwork and then pretend the old publication always meant the new software.

## Version discipline

During this hardening phase the executable version remains:

```text
runtime        2.0.0
Python package 2.0.0
Rust TUI       2.0.0
```

The future release target is `2.1.0`, but **the hardening phase does not authorize the version bump**.

The intended sequence is:

```text
PR #60  post-stable extension hardening
        |
        | all required CI + review green
        v
separate 2.1 release-identity / documentation candidate
        |
        | exact candidate hardening + review green
        v
future v2.1.0 release decision
```

This avoids version metadata becoming evidence that the code has earned release status.

```text
VERSION_TARGET != VERSION_BUMP_AUTHORITY
HARDENING_PASS != RELEASE_AUTHORITY
```

## Machine report

The dedicated workflow emits:

```text
nexus-post-stable-extension-hardening-report/1
```

The report binds:

- exact checked-out Git commit and tree;
- exact stable v2.0 tag/commit;
- exact PR #55–#59 merge chain;
- candidate/matrix identities;
- contract audits;
- extension-focused Python regressions;
- hermetic alpha9 self-test;
- Rust remote-operator tests;
- Rust formatting;
- failed required checks;
- zero release/version/semantic authority.

A report can say `passed: true`. It still cannot move a tag or make an empirical claim.

## Core boundaries

```text
V2_0_STABLE != POST_STABLE_EXTENSION_HEAD
HARDENING_PASS != RELEASE_AUTHORITY
VERSION_TARGET != VERSION_BUMP_AUTHORITY
INSTRUMENT_RESULT != TRUTH
PERSISTENT_LINEAGE != TRUTH
IMPORT != AUTHORITY
REMOTE_MODEL != PRIVILEGED_MODEL
MULTI_MODEL_CONSENSUS != EVIDENCE
LATTICE_POSITION != COGNITIVE_COORDINATE
LIVE_ACCEPTANCE != SCIENTIFIC_VALIDATION
```
