# NEXUS Instruments

## Purpose

Alpha7 introduces a versioned admission boundary for computational instruments used by NEXUS.

An instrument is a bounded computational capability that can transform declared inputs into declared outputs. Instruments may support reasoning, analysis, visualization, sonification, replay, or numerical work, but they do not become NEXUS governance actors and they do not inherit semantic authority merely because their outputs are deterministic or machine-generated.

```text
INSTRUMENT != COUNCIL_MEMBER
INSTRUMENT_RESULT != TRUTH
DETERMINISTIC != AUTHORITATIVE
REPLAYABLE != EVIDENCE_AUTHORITY
MODEL_REQUEST != EXECUTOR_AUTHORITY
```

## Admission contract

The machine policy is `nexus-instrument-admission/1`.

Admission is **default deny**. A roadmap candidate is not executable merely because it appears in the catalog.

An admitted instrument must declare:

- exact versioned `instrument_id`;
- executor class;
- deterministic/replayable status;
- side-effect classification;
- closed input contract;
- structured output contract;
- explicit claim boundary;
- evidence effect;
- authority effect.

For this initial alpha7 slice, admitted instruments must have `authority_effect: none`.

## First admitted instrument

The existing Three Minds bounded primality probe is the first admitted instrument:

```text
nexus.integer-primality/1
```

It remains coordinator-owned and deterministic. Its claim is intentionally narrow: exact integer primality for the supplied bounded fixture only.

The alpha7 admission layer does not widen the range, semantics, or epistemic meaning of that existing probe.

## Candidate instruments

The catalog also records non-executable candidates for future review:

- QEC-derived receipt/replay concepts;
- SPECTRAL analysis;
- QSOL sonification;
- numerical/symbolic computation.

They remain `candidate_not_admitted` until their exact input/output, side-effect, provenance, failure, security, and claim contracts are frozen and tested.

```text
CATALOGUED != ADMITTED
ADMITTED != AUTHORITATIVE
```

## Execution receipts

`run_instrument()` creates two content-addressed identities:

```text
instrument-intent:<sha256>
instrument-execution:<sha256>
```

and one content-addressed receipt:

```text
instrument-receipt:<sha256>
```

The execution binds the exact input, result, executor, determinism/replay status, side effects, evidence effect, authority effect, and claim boundary.

`verify_instrument_receipt()` reruns the admitted deterministic instrument from the recorded input and requires the complete bundle to reproduce exactly. A self-consistent edited result therefore does not verify merely because somebody recomputed a hash around the edit.

## Model boundary

Models may request an admitted instrument or interpret a completed result. They do not receive direct executor authority from that request.

Future adapters that execute external programs, repositories, services, or network operations require separate security review before admission. The catalog entry alone is not permission to cross those boundaries.

## Creative modes

Instrument eligibility is not restricted to Analytical Mode. A creative, cultural, game, or casual mode may use an admitted instrument when the instrument contract fits the task.

Mode framing cannot change the instrument's claim boundary, evidence effect, or authority effect.

## Alpha7 status

This PR implements the **instrument admission foundation**, not the complete alpha7 candidate list.

The next instrument PRs should each admit one capability at a time with:

1. exact external/local implementation identity;
2. versioned input/output schema;
3. deterministic and replay semantics;
4. resource and side-effect bounds;
5. provenance and receipt handling;
6. security/threat-model extension when a new execution boundary is crossed;
7. adversarial tests;
8. operator/TUI exposure only after the runtime contract is stable.
