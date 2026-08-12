# Reproducibility

The publication bundle is designed so an independent recipient can verify both provenance and the Lean theorem surface without trusting screenshots or a moving branch.

## 1. Verify the outer archive

```bash
sha256sum -c NEXUS-2.0-FORMALIZATION.tar.gz.sha256
tar -xzf NEXUS-2.0-FORMALIZATION.tar.gz
cd NEXUS-2.0-FORMALIZATION
```

## 2. Verify every payload file

```bash
sha256sum -c SHA256SUMS
```

`SHA256SUMS` covers every file inside the publication package except itself.

## 3. Inspect chain of custody

Read:

```text
IDENTITY.env
CHAIN_OF_CUSTODY.json
SOFTWARE/RELEASE_TAG.txt
SOFTWARE/RELEASE_COMMIT.txt
VALIDATION/release-hardening-report.json
VALIDATION/test-summary.txt
```

The required identities are:

```text
v2.0.0
  -> cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a

PR #53 reviewed Lean head
  -> 247a1f97834cfac5221e5045dda21551c28907a8

PR #53 merged commit
  -> faaff21fa926aa10bccc9d6cd66452ba1e2b065d
```

The `LEAN4/` directory is extracted directly from the reviewed PR #53 head. The stable software tarball is extracted directly from the stable software commit.

## 4. Verify the Lean toolchain boundary

The package pins:

```text
Lean 4.33.0
Linux release archive SHA-256:
4b3fb03c29a1e0a253fb1d11f9bae3725f19a0dc6fc09b3ea16d2c9df3349e2c
```

Install the official Lean 4.33.0 toolchain, or reproduce the CI installation using the pinned official archive digest.

## 5. Build the formalization

```bash
cd LEAN4
lake build
```

Expected result: successful build.

## 6. Run the complete declaration/axiom audit

```bash
bash audit.sh
```

Expected summary:

```text
theorems: 24
lemmas: 0
manifest_sync: PASS
axiom_query_manifest_sync: PASS
proof_holes: 0
project_defined_axiom_or_constant_declarations: 0
lake_build: PASS
aggregate_module: PASS
axiom_dependency_audit: PASS
```

The audited dependency profile is 19 theorems with no axiom dependencies and 5 depending only on Lean's standard `propext`; none currently depend on `Classical.choice`, `Quot.sound`, a NEXUS-defined axiom, `sorryAx`, `sorry`, or `admit`.

## 7. Compare fresh and CI evidence

The bundle contains both:

- `VALIDATION/pr53-ci-formal-verification-report.txt` — the report produced on the exact reviewed PR #53 head;
- `VALIDATION/formal-verification-report.txt` — freshly regenerated from the extracted publication copy during bundle construction.

The builder compares those reports after removing only the checkout-context line. All theorem, toolchain, manifest, axiom, and stable-runtime fields must match.

## 8. Scope of what has been verified

Lean proves the advertised properties of the formal definitions shipped in `LEAN4/`. Runtime correspondence is separately documented in `LEAN4/RUNTIME_CORRESPONDENCE.md` and supported by the stable source/test evidence.

This is not a claim that arbitrary NEXUS behavior, empirical model performance, factual Council correctness, consciousness, AGI, or every Python/Rust implementation property has been formally proved.
