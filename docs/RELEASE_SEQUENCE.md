# NEXUS Release Sequence

This file records release chronology and exact release gates. `ROADMAP.md` retains the broader architectural history.

## Frozen NEXUS 2.0 line

```text
PR #49 — NEXUS 2.0 Hardening — MERGED
        ↓
PR #50 — The BBS Wall — MERGED
        ↓
PR #51 — Documentation / Final Release Candidate — MERGED
        ↓
PR #52 — Post-Merge Grok Audit Closure — MERGED
        ↓
v2.0.0 — STABLE
cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
        ↓
PR #53 — Lean 4 Formal Verification — MERGED
        ↓
PR #54 — Formalization / Reproducibility / Zenodo — MERGED
DOI 10.5281/zenodo.21895577
```

The v2.0 software, reviewed Lean source, and Zenodo publication are frozen historical identities. Later extension releases do not silently redefine which runtime the v2.0 proofs or publication describe.

## Post-stable extension line

```text
v2.0.0 frozen baseline
        ↓
PR #55 — LATTICE World Presence — MERGED
        ↓
PR #56 — Instrument Admission — MERGED
        ↓
PR #57 — Persistent World — MERGED
        ↓
PR #58 — Remote Operator Engineering — MERGED
        ↓
PR #59 — Three Minds, One World Completion — MERGED
        ↓
PR #60 — Post-Stable Extension Hardening — MERGED
        ↓
PR #61 — NEXUS 2.1.1 Release Candidate — CURRENT
        ↓
exact reviewed/green merged PR #61
        ↓
v2.1.1 — future release tag
```

## Historical v2.1.0 tag

A `v2.1.0` tag already exists at:

```text
v2.1.0 -> 839303ea512631e527073682343341742cead975
```

That is the PR #55 merge. It predates PRs #56–#60 and the source at the tag still reports runtime `2.0.0`.

NEXUS therefore treats `v2.1.0` as an immutable historical premature post-stable marker. It is **not moved, deleted, or reused** by the hardened release process.

The next release candidate is `2.1.1`.

> **Historical tag identity outranks cosmetic version sequencing.**

## PR #55 — LATTICE World Presence

Introduced the explicit LATTICE-backed placement/movement/migration layer while preserving canonical WorldStore object identity.

Gate:

> **LATTICE position is storage/world presence, not truth or a cognitive coordinate.**

## PR #56 — Instrument Admission

Introduced default-deny, versioned instrument admission with `nexus.integer-primality/1` as the first admitted executable instrument and content-addressed intent/execution/receipt verification.

Gate:

> **Instrument output is derived material, not semantic authority.**

## PR #57 — Persistent World

Added typed relations, hypothesis and experiment lineage, derived minority/mode-history views, bounded exchange, and quarantine-preserving import without creating a second persistence authority.

Gate:

> **Persistence records lineage. It does not promote truth. Import does not import authority.**

## PR #58 — Remote Operator Engineering

Added the Rust `nexus-remote-setup` operator surface and explicitly authorized live-xAI acceptance harness while keeping raw credentials out of the TUI/world/semantic boundary.

The live acceptance remains an operator empirical gate. CI may run only the hermetic self-test.

Gate:

> **Provider identity does not change the vote. Connection success does not create truth.**

## PR #59 — Three Minds, One World Completion

Completed the canonical alpha11 shared-world demonstration using the newer alpha7/alpha8/LATTICE contracts:

- task-bound persistent hypotheses;
- exact admitted-instrument replay;
- typed experiment lineage;
- final-hypothesis closure;
- explicit world-presence handoff;
- one persisted integration manifest for restart verification;
- optional equal-vote reference/configured Council proof;
- minority preservation without evidence promotion.

Gate:

> **Multiple minds may share history without sharing hidden memory or acquiring shared truth authority.**

## PR #60 — Post-Stable Extension Hardening

PR #60 created a release-independent machine hardening boundary for the PR #55–#59 extension line.

Reviewed head:

```text
0e3b0e94053081ee77a1d969d3d60b81aeeb997c
```

Merge commit:

```text
80cda46e614f44b47861471cb329e29a348cab43
```

Final reviewed hardening artifact:

```text
ID      9421970922
SHA256  16674e62495ed5b66f69269ec2e5fb9cdb300b39bf2b45212f00085daa83ffbb
```

PR #60 intentionally did not bump the executable version or create release authority.

After discovery of the pre-existing `v2.1.0` tag, PR #60's historical `2.1.0` target remains part of the audit record rather than being rewritten. PR #61 supersedes the release *target* with `2.1.1`.

## PR #61 — NEXUS 2.1.1 Release Candidate

PR #61 is release identity and reconciliation, not a feature phase.

Required candidate identity:

```text
runtime         2.1.1
Python package  2.1.1
Rust TUI        2.1.1
Cargo lock      2.1.1
protocol        nexus/0.15
future tag      v2.1.1
```

The protocol bump from `nexus/0.14` to `nexus/0.15` is additive and records the new public world-presence, instrument, persistence and integration operations.

PR #61 MUST verify:

- exact current release-version alignment;
- README / strict README4AI release coupling;
- `v2.0.0` remains bound to its stable commit;
- `v2.1.0` remains bound to PR #55;
- `v2.1.1` does not exist during candidate review;
- merged PR #60 is an ancestor of the candidate;
- the frozen v2.0 publication/DOI remains unchanged;
- all extension-specific and inherited release regressions pass;
- Rust test/check use the committed lockfile;
- candidate tracked bytes and commit/tree identity remain unchanged during verification;
- no unresolved substantive release-blocking review thread remains.

The live-xAI operator gate remains open and is explicitly non-blocking for the software release. No CI path may claim that it ran a real provider acceptance session.

## Post-merge v2.1.1 release gate

A green PR #61 is still not the tag.

After merge:

1. resolve the exact merged PR #61 commit;
2. verify the required workflows/report on that exact identity where applicable;
3. confirm `v2.1.0` still resolves to `839303ea...`;
4. create **new** `v2.1.1` tag on the exact merged PR #61 commit;
5. publish the GitHub Release from the same tag/commit;
6. do not move `v2.0.0` or `v2.1.0`.

## Release principle

> **Freeze published history. Add new capability with typed boundaries. Harden the extension line. Reconcile the candidate. Tag only the exact reviewed release commit.**
