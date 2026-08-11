# NEXUS 2.0 Formalization & Reproducibility Package

This directory is the publication staging surface for PR #54. It packages the already-reviewed NEXUS 2.0 stable runtime and the already-reviewed PR #53 Lean 4 formalization without rewriting either one.

## Frozen identities

| Object | Identity |
|---|---|
| Stable software tag | `v2.0.0` |
| Stable software commit | `cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a` |
| PR #52 reviewed release head | `9c830dea68ef8877823f1aebb4f5f8ef2346cd08` |
| PR #53 reviewed formalization head | `247a1f97834cfac5221e5045dda21551c28907a8` |
| PR #53 merged commit | `faaff21fa926aa10bccc9d6cd66452ba1e2b065d` |
| Lean | `4.33.0` |
| Lean Linux archive SHA-256 | `4b3fb03c29a1e0a253fb1d11f9bae3725f19a0dc6fc09b3ea16d2c9df3349e2c` |
| Advertised theorem / lemma surface | `24 / 0` |
| Reserved Zenodo DOI | `10.5281/zenodo.21895577` |
| Publication date | `2026-08-12` |

The reviewed proof head and the GitHub merge commit are intentionally recorded separately. The publication bundle derives `LEAN4/` from the reviewed PR #53 head, while the merged commit records how that reviewed head entered `main`.

## What PR #54 adds

PR #54 adds publication machinery only:

- a deterministic bundle builder;
- an Actions workflow that verifies the complete identity chain;
- a byte-for-byte extraction of the reviewed Lean source at bundle-build time;
- an exact archive of the stable `v2.0.0` software source;
- PR #52 release-hardening evidence and PR #53 formal-verification evidence;
- a fresh standalone Lean audit executed against the extracted archive;
- SHA-256 inventory generation and verification;
- Zenodo-bound metadata and a short independent-recipient handoff guide.

It does **not** modify the NEXUS 2.0 stable tag, runtime semantics, theorem definitions, or theorem proofs.

## Build the upload candidate

From the repository root, with the pinned Lean toolchain available:

```bash
bash tools/build_nexus_2_formalization_bundle.sh
```

The command emits:

```text
publication/dist/
├── NEXUS-2.0-FORMALIZATION.tar.gz
└── NEXUS-2.0-FORMALIZATION.tar.gz.sha256
```

CI performs the same build and uploads those files as the `NEXUS-2.0-FORMALIZATION` workflow artifact. The builder reads publication metadata from the recorded publication commit rather than from uncommitted working-tree bytes, verifies the PR #52 and PR #53 merge-parent chain, and normalizes archive modes so identical inputs reproduce the same tarball across caller umasks.

## Zenodo binding

The publication identity is finalized as:

```text
ZENODO_DOI=10.5281/zenodo.21895577
ZENODO_PUBLICATION_DATE=2026-08-12
```

Those values are committed in `IDENTITY.env`, substituted into `ZENODO_METADATA.md`, and embedded in `CHAIN_OF_CUSTODY.json` in the generated archive. The publication workflow rejects malformed values and, for a ready-for-review PR, still fails closed if either value is ever reverted to `PENDING`.

The upload candidate generated from the final reviewed PR #54 head is therefore expected to carry this DOI and publication date as part of its frozen archival identity.

## Claim boundary

The publication claim remains deliberately narrow:

> Selected constitutional and protocol invariants of NEXUS 2.0 are formalized and machine-checked in Lean 4, with explicit correspondence to the tested stable runtime implementation.

This package does not claim that NEXUS creates AGI, that Council consensus is truth, that Six Hats necessarily improves answer quality, or that the complete Python/Rust implementation has been formally verified.
