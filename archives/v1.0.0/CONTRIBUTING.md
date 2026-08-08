# Contributing to QSOL NEXUS

NEXUS favours small, inspectable, versioned changes. It intentionally has no package manager or build pipeline.

## Before changing code

1. Read `ARCHITECTURE.md`, `CLAIMS.md`, `SECURITY.md`, and `docs/DETERMINISM.md`.
2. Identify whether the change affects experiment identity, only observation/UI, or neither.
3. Preserve the fixed script order and single `window.QSOL_NEXUS` namespace.
4. Check source licences before adapting an algorithm, figure, text, dataset, or test vector.

## Engine contributions

Use `docs/ENGINE_AUTHORING.md`. An engine must include:

- stable engine ID and semantic version;
- normalized parameter schema and explicit unknown-field policy;
- supported determinism modes;
- input adapters and output channels;
- claim class, status, boundary, and `does_not_claim` list;
- `compile`, `render`, `observe`, and `validate` operations;
- seeded randomness only in deterministic modes;
- bounded work and cancellation checks;
- known-answer fixtures and replay/tamper tests;
- an observation-to-audio mapping that cannot alter numerical output.

## Coding style

- Use strict-mode classic scripts and an IIFE.
- Attach one frozen public API to the appropriate namespace.
- Avoid mutable global state.
- Do not read the DOM outside `js/ui/`.
- Prefer typed arrays for numerical buffers.
- Reject invalid data; do not silently normalize scientific source input.
- Keep identity-bearing serialization canonical and domain-separated.
- Never use WebAudio output as exported PCM.
- Do not introduce network clients, remote assets, dynamic code execution, workers, or package-manager files.

## Tests

Open `tests/index.html` directly and run the full suite. Add or update tests for every identity-bearing behaviour. A bug fix that changes a golden artifact requires a documented version change and migration note, not an unexplained hash replacement.

For a publication-grade Canonical Strict claim, compare the same golden corpus in current Chromium, Firefox, Edge, and Safari where available.

## Claims and model status

Do not promote an experimental model by changing prose or colour alone. Model status is part of the descriptor and artifact identity. New physical-model code needs a source citation, named assumptions and units, parameter bounds, independent fixtures, and a clear statement of what the implementation does not establish.

## Pull requests

Keep changes focused. Explain the identity impact, test evidence, browser matrix, claim-boundary impact, source attribution, and any expected golden-hash change. Do not include private source data or machine-specific paths.
