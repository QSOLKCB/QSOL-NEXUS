# PR #53 Publication & Reproducibility Contract

This document defines the publication boundary that follows the NEXUS 2.0 stable release and PR #52 Lean 4 formal verification.

## Fixed sequence

```text
PR #50 — The BBS Wall
  ↓
PR #51 — Final docs + release candidate + complete regression/recovery
  ↓
NEXUS 2.0 STABLE
  ↓
PR #52 — Lean 4 Formal Verification
  ↓
PR #53 — Formalization + Reproducibility + Zenodo Publication
```

PR #52 proves selected protocol invariants. PR #53 does not invent new proofs or silently edit the reviewed formal model. It freezes and publishes the reviewed artifacts together with the stable runtime they describe.

## Mandatory publication payload

The Zenodo package MUST contain, at minimum:

```text
NEXUS-2.0-FORMALIZATION/
├── SOFTWARE/
│   ├── NEXUS-2.0-stable-source.tar.gz
│   ├── RELEASE_TAG.txt
│   └── RELEASE_COMMIT.txt
├── LEAN4/
│   ├── lean-toolchain
│   ├── lakefile.toml
│   ├── Nexus.lean
│   ├── Nexus/
│   ├── THEOREMS.md
│   ├── ASSUMPTIONS_AND_NONCLAIMS.md
│   └── RUNTIME_CORRESPONDENCE.md
├── VALIDATION/
│   ├── lean-build-report.txt
│   ├── release-hardening-report.json
│   └── test-summary.txt
├── REPRODUCIBILITY.md
├── README.md
└── SHA256SUMS
```

The `LEAN4/` directory MUST be byte-for-byte derived from the reviewed PR #52 formalization head, except for publication metadata that cannot change theorem definitions or proofs.

The `SOFTWARE/` archive MUST identify the actual NEXUS 2.0 stable tag and commit. A release candidate, moving branch head, or unrelated development snapshot is not an acceptable substitute.

## Reproduction target

A recipient must be able to extract the archive and run:

```bash
cd LEAN4
lake build
```

using the pinned `lean-toolchain` and obtain a successful build without editing theorem sources.

PR #53 SHOULD also record the exact Lean compiler release asset digest used by CI so that a verifier can reproduce the compiler/toolchain boundary as well as the source tree.

## Proof-integrity boundary

The publication package MUST NOT contain theorem proof holes such as `sorry` or `admit`, and MUST NOT introduce user-declared axioms merely to make an advertised theorem compile.

Every theorem advertised in `THEOREMS.md` must be present in the shipped Lean source and accepted by the pinned Lean toolchain.

## Runtime correspondence

Each advertised runtime-correspondence entry must identify:

1. Lean theorem name;
2. formal statement/invariant;
3. NEXUS 2.0 stable source location;
4. runtime regression test(s);
5. stable release tag;
6. stable release commit;
7. PR #52 formalization commit.

This prevents the publication from claiming that a theorem about one formal model automatically proves an unrelated implementation.

## Explicit non-claims

Publication language must remain narrower than the proof surface.

The Lean package does not prove that:

- AGI exists;
- NEXUS creates AGI;
- Council consensus is truth;
- a model answer is correct merely because a Council accepted it;
- Six Hats necessarily improves reasoning quality;
- every property of the complete NEXUS runtime has been formally verified.

The intended claim is:

> Selected constitutional and protocol invariants of NEXUS 2.0 have been formalized and machine-checked in Lean 4, with explicit correspondence to the tested stable runtime implementation.

## Chain of custody

PR #53 must record and publish:

- NEXUS 2.0 stable tag;
- NEXUS 2.0 stable commit SHA;
- PR #52 final formalization commit SHA;
- Lean version;
- official Lean release asset SHA-256;
- SHA-256 for every publication payload file;
- the final Zenodo DOI.

The checksums are publication integrity metadata. They create no NEXUS authority, evidence promotion, vote weight, Citizenship, or governance privilege.

## Handoff package

The final research handoff is intentionally three-part:

1. finished NEXUS 2.0 stable software;
2. runnable Lean 4 source that an independent recipient can execute;
3. an immutable Zenodo record containing the formalization, reproducibility metadata, validation evidence, hashes, and stable software reference.

The recipient should not need to trust screenshots, prose summaries, or a claim that the proofs were run elsewhere. They receive the source and can run the checker themselves.
