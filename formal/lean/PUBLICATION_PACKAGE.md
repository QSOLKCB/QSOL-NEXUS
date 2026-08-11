# PR #54 Publication & Reproducibility Contract

This document defines the publication boundary that follows the NEXUS 2.0 stable release line and PR #53 Lean 4 formal verification.

## Fixed sequence

```text
PR #50 — The BBS Wall
  ↓
PR #51 — Final docs + release candidate + complete regression/recovery
  ↓
PR #52 — Post-Merge Grok Audit Closure
  ↓
NEXUS 2.0 STABLE
  ↓
PR #53 — Lean 4 Formal Verification
  ↓
PR #54 — Formalization + Reproducibility + Zenodo Publication
```

PR #53 proves selected protocol invariants in the explicit Lean model and audits their runtime correspondence. PR #54 does not invent new proofs or silently edit the reviewed formal model. It freezes and publishes the reviewed artifacts together with the exact stable runtime they describe.

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
│   │   └── AxiomAudit.lean
│   ├── audit.sh
│   ├── AUDIT_MANIFEST.tsv
│   ├── THEOREMS.md
│   ├── THEOREMS_AND_LEMMAS.md
│   ├── FORMAL_GAP_RANKING.md
│   ├── AXIOM_AUDIT.md
│   ├── ASSUMPTIONS_AND_NONCLAIMS.md
│   ├── RUNTIME_CORRESPONDENCE.md
│   └── PUBLICATION_PACKAGE.md
├── VALIDATION/
│   ├── formal-verification-report.txt
│   ├── release-hardening-report.json
│   └── test-summary.txt
├── REPRODUCIBILITY.md
├── README.md
└── SHA256SUMS
```

The `LEAN4/` directory MUST be byte-for-byte derived from the reviewed final PR #53 formalization head, except for publication metadata that cannot change theorem definitions or proofs.

The `SOFTWARE/` archive MUST identify the actual NEXUS 2.0 stable tag and commit. For this release line, `v2.0.0` must resolve to the exact merged PR #52 runtime commit:

```text
cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
```

A release candidate, moving branch head, or unrelated development snapshot is not an acceptable substitute.

## Reproduction targets

A recipient must be able to extract the archive and run the minimal kernel build:

```bash
cd LEAN4
lake build
```

They must also be able to run the complete declaration/axiom audit:

```bash
bash audit.sh
```

using the pinned `lean-toolchain` and obtain successful results without editing theorem sources or the audit manifest.

PR #54 SHOULD also record the exact Lean compiler release asset digest used by CI so that a verifier can reproduce the compiler/toolchain boundary as well as the source tree.

## Proof-integrity boundary

The publication package MUST NOT contain theorem proof holes such as `sorry` or `admit`, and MUST NOT introduce project-defined `axiom` or bare `constant` declarations merely to make an advertised theorem compile.

Every `A` or `A/R` theorem/lemma advertised in `AUDIT_MANIFEST.tsv` must be present in the shipped Lean source and accepted by the pinned Lean toolchain.

The shipped `Nexus/AxiomAudit.lean` must run Lean's `#print axioms` command across every advertised theorem. `formal-verification-report.txt` must record the resulting dependency audit.

For the compact constitutional layer, imported dependencies outside the explicitly reviewed standard Lean set (`propext`, `Classical.choice`, `Quot.sound`, or no axioms) require a documented trust-boundary change before publication.

## Formal gap/status record

`FORMAL_GAP_RANKING.md` MUST remain part of the publication package so that unresolved or empirical matters are not silently upgraded into theorem claims.

The publication must preserve the status vocabulary:

- `A` — formally established;
- `D` — proof obligation outstanding;
- `R` — exact stable-runtime correspondence pending;
- `E` — empirical rather than theorem-level;
- `N` — explicit non-claim.

Composite `A/R` entries may become publication-facing plain `A` only after the exact stable source/test correspondence and `v2.0.0` tag binding have been frozen and audited in PR #53.

## Runtime correspondence

Each advertised runtime-correspondence entry must identify:

1. Lean theorem name;
2. formal statement/invariant;
3. NEXUS 2.0 stable source location;
4. runtime regression test(s);
5. stable release tag;
6. stable release commit;
7. PR #53 final formalization commit.

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

PR #54 must record and publish:

- NEXUS 2.0 stable tag;
- NEXUS 2.0 stable commit SHA (`cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a` for this release line);
- PR #53 final formalization commit SHA;
- Lean version;
- official Lean release asset SHA-256;
- theorem/lemma counts from the final manifest audit;
- axiom-dependency audit output;
- SHA-256 for every publication payload file;
- the final Zenodo DOI.

The checksums and audit records are publication integrity metadata. They create no NEXUS authority, evidence promotion, vote weight, Citizenship, or governance privilege.

## Handoff package

The final research handoff is intentionally three-part:

1. finished NEXUS 2.0 stable software;
2. runnable Lean 4 source plus declaration/axiom audit that an independent recipient can execute;
3. an immutable Zenodo record containing the formalization, gap/status record, reproducibility metadata, validation evidence, hashes, and stable software reference.

The recipient should not need to trust screenshots, prose summaries, or a claim that the proofs were run elsewhere. They receive the source, the audit machinery, the exact declaration ledger, and can run the checker themselves.
