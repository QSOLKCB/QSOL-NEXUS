# QSOL NEXUS 1.0

**Deterministic Field Simulation and Sonification Workbench**

> Theory → Simulation → Observation → Sound → Proof

QSOL NEXUS is a zero-install browser laboratory for deterministic field simulation, tensor analysis, galaxy rotation-curve comparison, scientific sonification, and replay-verifiable experiment artifacts. It integrates the strongest **contracts and engines** from the QSOL ecosystem behind one runtime; it does not embed or concatenate the source repositories.

Open [`index.html`](index.html) directly in a modern browser. NEXUS uses no server, Node runtime, npm package, build pipeline, CDN, cloud service, telemetry, or hidden network request. Source data and generated artifacts remain local.

## Laboratories

| Laboratory | What it computes | Scientific status |
|---|---|---|
| **Qutrit Field** | Seeded three-state fields, deterministic update rules, entropy, recurrence, clusters, boundaries, event streams, and offline sonification | Classical information model; qutrit terminology is an encoding analogy |
| **Tensor Resonance** | Real symmetric 2×2 and 3×3 tensors, transformations, invariants, eigensystems, principal axes, and quadrature/residual sonification | Mathematical linear-algebra laboratory |
| **Galaxy Models** | SPARC-style data validation, baryonic baseline, NFW, named MOND interpolation, experimental UFF profile, transparent fitting, residual statistics, and comparative sonification | Mixed established, published phenomenological, and explicitly experimental models |

Each engine declares its ID, version, supported determinism modes, input and parameter contracts, claim class, claim boundary, and validation method.

## Quick start

1. Extract the release directory without changing its internal paths.
2. Open `QSOL-NEXUS/index.html`.
3. Choose a laboratory, determinism mode, seed, and preset.
4. Optionally load or paste local source data.
5. Select **Run Lab**. The recipe is frozen before execution.
6. Inspect measurements, claims, validation, waveform, and spectrogram.
7. Export individual artifacts or the deterministic experiment ZIP.

Run the browser-native verification suite by opening [`tests/index.html`](tests/index.html).

## Determinism modes

### Canonical Strict

The archival path. Identity-bearing data uses canonical JSON, a bundled SHA-256 implementation, versioned seeded randomness, explicit sorting and rounding, offline PCM16/WAV generation, and deterministic store-only ZIP output. Native image decoding and browser-dependent numeric procedures are refused or gated when they cannot satisfy the selected contract.

Strict output is a **cross-runtime candidate**, not an automatic cross-browser guarantee. A release earns that claim only after its golden hashes match in the supported browser matrix.

### Replay Safe

The deterministic scientific and creative iteration path. It permits float64 eigensolvers and fitting while freezing inputs and recording a runtime fingerprint. Its replay promise is scoped to the recorded runtime class when numerical output is runtime-sensitive.

### Creative

The explicitly non-deterministic performance path. It may use system entropy and mutable playback controls. Creative artifacts receive a conspicuous `NON-DETERMINISTIC` status and parameter/observation snapshot, never a reproducibility claim.

## Standard experiment bundle

Every completed deterministic experiment can export:

```text
experiment.wav
experiment.json
observations.json
manifest.json
contract.json
fingerprint.json
lineage.json
README_ORIGIN.txt
```

Engine-specific tables such as `field.csv`, `tensor.csv`, `rotation_curve.csv`, `residuals.csv`, or `events.json` are added when available.

The no-self-hash sequence is:

```text
frozen recipe
  → engine result and observations
  → offline PCM and WAV
  → artifact hashes
  → observation contract
  → manifest core and envelope
  → deterministic ZIP
```

Replay validates by recomputing identity-bearing results rather than trusting stored assertions. A changed source, seed, mode, engine version, parameter, observation, PCM/WAV payload, claim boundary, or required runtime fingerprint fails verification.

## Galaxy input

Canonical SPARC-style CSV columns are:

```text
radius_kpc
velocity_observed_kms
velocity_error_kms
velocity_gas_kms
velocity_disk_kms
velocity_bulge_kms
```

Legacy UFF aliases such as `R_kpc`, `V_obs_kms`, and `e_V_kms` may be converted only through an explicit normalization receipt. NEXUS does not silently repair negative radii, invalid uncertainty, duplicate or unsorted radii, unsupported units, missing observed velocity, or non-finite values.

Lower AIC or BIC is comparative evidence for a model under the selected dataset and likelihood assumptions. It is not proof that the model is physically correct.

## Claim boundaries

Claim boundaries are part of the engine descriptor, visible interface, observation contract, and manifest identity. In particular:

- Qutrit Field is a classical three-state simulation. It does not execute a physical qutrit or claim superposition, measurement, entanglement, or quantum advantage.
- Tensor Resonance demonstrates linear-algebra relationships. A quadrature phase pair does not establish physical self-duality.
- The NFW implementation is an established computational profile; MOND is a named published phenomenological model; `uff_experimental_v1` is an exploratory QSOL profile and is never displayed as a validated replacement for dark matter or MOND.
- Sonification is an observation mapping. It cannot validate a physical theory, change fitting results, or turn narration or aesthetics into evidence.

See [`CLAIMS.md`](CLAIMS.md) for the complete system.

## Privacy and security

Production code contains no `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, remote font or image, analytics, service worker, dynamic script injection, `eval`, or `new Function`. A restrictive Content Security Policy sets `connect-src 'none'`. Local file names, paths, history, playback state, viewport size, and visualization settings do not enter experiment identity.

See [`SECURITY.md`](SECURITY.md) for the threat model and audit commands.

## Architecture

NEXUS uses classic deferred scripts in a fixed dependency order. Versioned APIs attach to `window.QSOL_NEXUS` beneath:

```text
core · math · mappings · audio · visual · engines
provenance · storage · ui · tests
```

This avoids the inconsistent `file://` handling of ES-module imports while keeping components independently testable. See [`ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/DETERMINISM.md`](docs/DETERMINISM.md), and [`docs/ARTIFACT_FORMAT.md`](docs/ARTIFACT_FORMAT.md).

## Source lineage and attribution

NEXUS is an original Apache-2.0 implementation informed by:

- [QSOLKCB/SPECTRAL](https://github.com/QSOLKCB/SPECTRAL) — browser-native deterministic sonification, artifact, replay, visualization, and storage architecture (MIT).
- [QSOLKCB/QEC](https://github.com/QSOLKCB/QEC) — canonical receipts, recompute-not-trust validation, and source-bound claim architecture (CC BY 4.0).
- [QSOLKCB/QNTOY](https://github.com/QSOLKCB/QNTOY) — qutrit-grid audiovisual organism concept (MIT).
- [QSOLKCB/TFT](https://github.com/QSOLKCB/TFT) — tensor invariants, eigenvalue-to-frequency mapping, and quadrature-pair concept (CC BY 4.0).
- [QSOLKCB/UFF](https://github.com/QSOLKCB/UFF) — rotation-curve datasets, model comparison, experimental UFF profile, and sonification concepts (Apache-2.0).
- [QSOLKCB/QAI-UFT](https://github.com/QSOLKCB/QAI-UFT) — ternary, sexagesimal, codon, tensor-phase, and interface concepts (CC BY 4.0).
- [QSOLKCB/AIMM](https://github.com/QSOLKCB/AIMM) — future optional narration concept; no AIMM code or remote authority is included in the trusted numerical core.

See [`NOTICE`](NOTICE) for licence-specific attribution and modifications.

## Development

There is no dependency installation step. Edit the HTML, CSS, or classic JavaScript files and reload the page. Engine authors should begin with [`docs/ENGINE_AUTHORING.md`](docs/ENGINE_AUTHORING.md).

Before a release:

1. Open `tests/index.html` under Chromium, Firefox, Edge, and Safari where available.
2. Confirm all core, audio, laboratory, replay, tamper, cancellation, and security tests pass.
3. Compare Canonical Strict golden hashes across supported browsers.
4. Run the static no-network and remote-resource audit in `SECURITY.md`.
5. Archive example experiment bundles with the release metadata.

## Licence and citation

Original NEXUS source is licensed under the [Apache License 2.0](LICENSE). Source-derived attribution remains subject to the licences identified in [`NOTICE`](NOTICE).

For citation metadata, see [`CITATION.cff`](CITATION.cff) and [`.zenodo.json`](.zenodo.json).

Copyright © 2026 Trent Slade / QSOL-IMC.
