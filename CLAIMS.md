# Scientific and Interpretive Claim Boundaries

QSOL NEXUS makes claim status a machine-readable part of every engine and experiment. A label is not cosmetic: changing the claim class, boundary, status, or `does_not_claim` list changes the contract and must fail replay against the earlier artifact.

## Claim classes

| Class | UI label | Meaning |
|---|---|---|
| `mathematical_transform` | MATHEMATICAL | A mathematical operation or relationship is computed under stated assumptions |
| `classical_information_model` | CLASSICAL SIMULATION | A classical system uses information-theoretic or quantum-inspired notation |
| `published_physical_model` | PUBLISHED MODEL | A versioned implementation of a named model from the scientific literature |
| `experimental_physical_model` | EXPERIMENTAL | An exploratory physical profile without empirical validation through NEXUS |
| `statistical_observation` | STATISTICAL | A statistic derived from supplied data and stated likelihood assumptions |
| `creative_symbolic_mapping` | CREATIVE MAPPING | A symbolic or aesthetic mapping without evidentiary force |
| `audio_visual_observation` | AUDIOVISUAL | A visual or sonic encoding of a completed result |

`REPLAY VERIFIED` describes artifact consistency only. It does not certify truth, empirical validity, authorship, originality, safety, or scientific consensus.

## Qutrit Field

**Class:** `classical_information_model`

The engine evolves a `Uint8Array` whose cells take values 0, 1, or 2. It computes deterministic classical transition rules and information statistics.

It does not claim:

- physical qutrit preparation or execution;
- quantum superposition or state amplitudes;
- physical measurement or wave-function collapse;
- entanglement, nonlocality, quantum speedup, or quantum advantage;
- a simulator of a particular quantum processor.

Words such as *qutrit*, *state*, and *measurement* refer to an encoding analogy unless a future, separately validated hardware adapter says otherwise.

## Tensor Resonance

**Class:** `mathematical_transform`

The engine computes real symmetric rank-2 matrices, eigensystems, transformations, invariants, and numerical residuals. Orthogonal similarity is expected to preserve trace, determinant, Frobenius norm, and eigenvalues within the declared numerical contract.

It does not claim:

- an arbitrary high-rank symbolic tensor calculus;
- a physical field equation or conserved quantity beyond the implemented mathematics;
- that a π/2 audio phase offset establishes self-duality in nature;
- empirical validation of Tensor Field Theory or a Unified Field Framework.

The **Quadrature Phase Pair** preset is an audio mapping, not a physical result.

## Galaxy Models

The galaxy laboratory deliberately displays model status at the model level.

### Baryonic baseline

**Status:** established computational combination.

The engine combines supplied gas, disk, and bulge velocity components in quadrature using explicit mass-to-light scale factors. Its validity is limited by the supplied components, units, distance and inclination assumptions.

### NFW

**Status:** established computational model.

The versioned implementation evaluates a Navarro–Frenk–White halo profile with explicit units and bounded parameters. NEXUS does not infer that an NFW fit proves a dark-matter ontology.

### MOND simple interpolation

**Status:** published phenomenological model.

The model uses a named, versioned interpolation function. A comparative fit is evidence only under the selected dataset, error model, parameter bounds, and likelihood assumptions.

### `uff_experimental_v1`

**Status:** experimental QSOL model.

This engine reimplements the exploratory core-plus-power-law profile described by QSOLKCB/UFF. The source repository explicitly describes the current base law as a placeholder that users may replace. NEXUS therefore never presents it as a validated physical law or as a proven replacement for dark matter, MOND, general relativity, or another cosmological model.

### Model comparison

Weighted residual sums, reduced chi-square, RMSE, MAE, AIC, BIC, maximum residual, and residual autocorrelation are statistical observations. Lower AIC or BIC is comparative evidence under shared assumptions—not proof that a model is physically correct. Parameter recovery from a synthetic fixture validates implementation behaviour against that fixture, not nature.

## Sonification and visualization

Audio and images are one-way observation mappings derived after numerical computation. They can reveal patterns, support accessibility, teach relationships, or create musical material. They cannot:

- alter fitted parameters or numerical identity;
- establish causality or scientific validation;
- make an experimental model established;
- convert symbolic E8, codon, sexagesimal, Fibonacci, phi, or musical mappings into physical evidence;
- guarantee external platform acceptance or copyright status.

## Future narration

A future AIMM adapter may explain controls, summarize completed observations, narrate comparisons, suggest presets, or add humour. It must not modify a frozen recipe, certify a model, invent missing data, silently change a claim boundary, or convert narration into evidence.
