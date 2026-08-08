# QSOL NEXUS Architecture

## Constitutional rules

QSOL NEXUS is a local-first scientific workbench, not a collection of embedded applications. It integrates versioned contracts and selected algorithms behind a shared runtime. The trusted numerical path has no network dependency, hidden randomness, mutable global engine state, wall-clock identity, or WebAudio export.

The application must continue to open from `index.html` through `file://` without a build step.

## Layer model

```text
UI values and local source bytes
        │
        ▼
input adapter + parameter normalization
        │
        ▼
frozen experiment recipe ───────────────┐
        │                               │ identity boundary
        ▼                               │
versioned laboratory engine             │
        │                               │
        ├── numerical result            │
        ├── observations                │
        └── one-way sonification        │
                  │                     │
                  ▼                     │
          offline PCM16 + WAV           │
                  │                     │
                  ▼                     │
 hashes → contract → manifest → ZIP ◄───┘
```

Visualization and playback observe completed output. Canvas dimensions, zoom, colour, FFT display settings, audio volume, and transport state are outside numerical identity.

## Namespace

Every classic deferred script extends `window.QSOL_NEXUS`:

| Namespace | Responsibility |
|---|---|
| `core` | canonical encoding, hashing, PRNG, decimal rules, scheduling, cancellation, input and schemas |
| `math` | matrices, eigensystems, statistics, interpolation, optimization, graphs and entropy |
| `mappings` | ternary, sexagesimal, codon, Fibonacci, phi and musical mappings |
| `audio` | oscillators, envelopes, spatialization, PCM quantization, WAV, fingerprint and ZIP |
| `visual` | Canvas, plots, waveform, spectrogram and laboratory views |
| `engines` | descriptor registry and laboratory engines |
| `provenance` | recipes, observations, manifests, replay validation, claims, lineage and bundles |
| `storage` | IndexedDB with explicit session fallback, history and user presets |
| `ui` | routing, controls, inspector, transport, exports and laboratory presentation |
| `tests` | browser-native test registration and reporting |

Scripts load in dependency order. A module must not read DOM state unless it is in `ui`, and an engine must not write to the DOM.

## Engine contract

Every descriptor provides:

```javascript
{
  id: "qutrit_field",
  display_name: "Qutrit Field",
  engine_version: "1.0.0",
  category: "simulation",
  supported_modes: ["canonical_strict", "replay_safe", "creative"],
  parameter_schema: {},
  input_adapters: [],
  output_channels: [],
  claim_class: "classical_information_model",
  claim_status: "demonstration",
  claim_boundary: "...",
  does_not_claim: [],
  compile(recipe, context) {},
  render(compiled, context) {},
  observe(result, context) {},
  validate(artifact, context) {}
}
```

The UI invokes engines through the registry. Engine-specific code may add a convenience `run` operation, but the lifecycle remains inspectable.

## Execution transaction

1. Read and normalize current UI values.
2. Validate source and parameters.
3. Create the runtime fingerprint when required.
4. Freeze the normalized recipe.
5. Lock identity-bearing controls.
6. Compile and render using a cancellation token and bounded yields.
7. Compute observations from results.
8. Derive audio from results only; audio never feeds the fit or simulation.
9. Generate offline PCM16 and WAV bytes.
10. Hash domain-separated artifacts.
11. Build contract and manifest without circular self-hashes.
12. Persist only after the transaction completes.

Cancellation discards the pending transaction. It may leave a non-identity-bearing preview on screen, but it produces no downloadable bundle or history entry.

## Determinism boundary

Canonical Strict forbids `Math.random`, system entropy, wall-clock identity, unsafe canonical JSON values, runtime-native image decoding, nondeterministic optimization termination, and mutable engine state. Replay Safe uses seeded randomness and records a runtime fingerprint for float64-sensitive work. Creative mode may use entropy, but its exported snapshot cannot receive a deterministic validation status.

All identity hashes use a domain prefix ending with a NUL byte. The manifest-core hash is computed before the envelope adds that hash; no file claims to contain a valid hash of itself.

## Storage boundary

IndexedDB stores completed jobs, presets, and compact history. If unavailable under a browser's local-file origin policy, NEXUS switches visibly to session memory. Storage contents, previous jobs, local filenames, and eviction order never affect deterministic artifacts.

## Security boundary

The CSP denies all connections. Production scripts contain no network client, dynamic code evaluation, worker registration, or remote asset loader. File and Blob APIs, Canvas, IndexedDB, object URLs, and user-initiated downloads are the intended browser capabilities.

## Extensibility

New engines are code-reviewed, versioned modules—not dynamically downloaded plugins. A future AIMM adapter must accept completed, non-secret observations only and remain outside the trusted numerical core. WebGPU, remote collaboration, hardware access, and live capture remain out of scope until separate threat and determinism contracts exist.
