# NEXUS 2.1.1 Compatibility

## Release target

```text
runtime / Python package / Rust TUI  2.1.1
control protocol                      nexus/0.15
release-validation Rust/Cargo        1.97.1
Python                                >= 3.11
candidate base                        merged PR #60
future tag                            v2.1.1
```

This document describes the PR #61 release candidate. Stable release status for `2.1.1` begins only if the exact reviewed-and-green merged PR #61 commit is subsequently tagged `v2.1.1`.

## Historical tag compatibility

Two older tags are immutable provenance inputs:

```text
v2.0.0 -> cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
v2.1.0 -> 839303ea512631e527073682343341742cead975
```

`v2.0.0` is the frozen stable/publication baseline associated with Lean PR #53 and Zenodo publication PR #54 / DOI `10.5281/zenodo.21895577`.

The existing `v2.1.0` tag is a historical premature post-stable marker at PR #55. It predates PRs #56–#60 and its source still identifies the runtime as `2.0.0`. NEXUS 2.1.1 preserves rather than moves that tag.

## Operator compatibility

The supported first-party operator path remains the repository `./nexus` launcher plus the Rust IRC-style TUI. The control plane remains newline-delimited JSON over local stdio; NEXUS does not require an IRC daemon or browser application.

The Rust remote-operator helper `nexus-remote-setup` is additive. It manages non-secret auth profile references, provider model discovery, and ephemeral roster configuration. It does not replace the runtime and does not accept raw provider credentials.

Python 3.11+ remains required. Candidate/release validation pins Rust/Cargo 1.97.1 for reviewed reproducibility; a future compatible compiler version is not automatically a protocol change.

## Protocol compatibility

NEXUS 2.1.1 uses `nexus/0.15`, up from `nexus/0.14` in v2.0.0.

This is classified as an **additive protocol-minor change**. PRs #55–#59 introduce new public operation families and typed objects without intentionally changing the meaning of established v2.0 operations:

- LATTICE world placement/movement/migration/presence;
- admitted instrument execution/receipt surfaces;
- typed persistent-world relations, hypotheses and experiments;
- minority/mode-history views and bounded persistent-world exchange;
- alpha11 integration/restart/Council demonstration helpers.

Clients that only use established v2.0 operations should not infer new authority semantics from the newer operation set. Clients that consume 0.15-specific operations must use the corresponding 0.15 contracts.

An unknown future protocol major remains fail-closed where versioned contracts require it.

## Runtime/API compatibility

The canonical package-root and established Python import aliases resolve to the additive `PersistentWorldNexusAPI` overlay. That overlay preserves the Wall, culture/progression, Continuity/Ark, civic/Guardian, provider and earlier runtime surfaces while adding the alpha8 persistent-world operations.

Programmatic clients should discover operations through:

```json
{"operation":"system.health"}
{"operation":"system.operations"}
```

rather than assuming a static list from documentation.

Live stochastic model inference remains non-replayable even when a provider offers a seed. Deterministic runtime/game/instrument operations retain only their explicitly declared replay contracts.

## WorldStore compatibility

NEXUS preserves canonical content-addressed `object:<sha256>` identity. Post-stable features are additive to the same WorldStore and do not create a second trusted database.

WorldStore Continuity can baseline admitted legacy object history without changing existing object IDs, then uses replicated manifests/quorum recognition for durable history. Mutable indexes remain reconstructable convenience.

Recovery remains deliberately non-destructive: a World Ark restores into a new empty target rather than overwriting a live source store.

## LATTICE-address compatibility

The world-presence layer pins LATTICE v1 profile:

```text
qsol-3x3x3-sierpinski-derived-memory/1
```

with the reviewed semantic fingerprint from the LATTICE consumer contract.

Historical address identity is the pair `(profile_id, address)`. Unknown majors, unknown same-major profiles, and semantic-fingerprint drift fail closed. Additive non-semantic descriptor metadata remains compatible.

Existing `object:<sha256>` IDs are never reinterpreted as LATTICE content references. Named NEXUS regions and LATTICE addresses remain independent explicit identities.

```text
LATTICE_POSITION != COGNITIVE_COORDINATE
```

## Instrument compatibility

Instrument admission is versioned and default-deny.

The first admitted executable instrument remains:

```text
nexus.integer-primality/1
```

Its input/output, side-effect, replay, and claim contracts are closed and bounded. Catalogued candidates are not executable merely because their names appear in the registry.

A future instrument version or a newly admitted instrument is a separately reviewed contract change.

```text
CATALOGUED != ADMITTED
ADMITTED != AUTHORITATIVE
```

## Persistent-world exchange compatibility

Portable persistent-world exchange is bounded and source-preserving. A foreign hash-valid WorldObject does not become a live local Council/governance object on import. Unless the exact source object already independently exists locally, it is preserved inside an inert quarantine wrapper plus import receipt.

This means portable exchange is not interchangeable with trusted World Ark recovery.

```text
IMPORT != AUTHORITY
EXPORT_HASH != SEMANTIC_TRUTH
```

## Adapter compatibility

Admitted local backends remain deterministic/mock, Ollama, LM Studio, AnythingLLM, and generic loopback OpenAI-compatible runtimes. Reviewed cloud providers remain xAI, OpenAI, Anthropic, Gemini, Groq, and Together through fixed-host transports.

A new provider, endpoint class, credential method, or tool-execution boundary is not automatically compatible merely because it speaks an OpenAI-shaped JSON protocol; it requires its own reviewed adapter/security contract.

Provider identity continues to confer no Council vote weight or epistemic privilege.

## Three Minds compatibility

The original alpha11 stage objects and public primality-probe export remain preserved, but the canonical demo now also binds alpha7 admitted receipts, alpha8 typed lineage, explicit LATTICE handoff, and persisted integration verification.

Restart verification requires one coherent persisted integration manifest. Valid refs from independent runs cannot be mixed into a synthetic verified result.

The optional Council demonstration remains equal-vote and preserves minority reports without promoting them to evidence.

## Empirical live-provider boundary

The live xAI acceptance harness is an operator-run empirical check. It is disabled by default and requires explicit live authorization.

A missing live acceptance archive does not make the hermetic software contracts false; conversely, a successful connection/Council archive does not prove scientific validity, truth, or provider superiority.

The 2.1.1 software release treats this empirical gate as open and non-blocking.

## Deliberate non-compatibilities

NEXUS 2.1.1 does not promise compatibility with:

- rewriting or moving historical release tags;
- the archived NEXUS 1.0 browser workbench as a trusted control surface;
- arbitrary remote Ollama/OpenAI-compatible hosts;
- consumer/browser sessions imported as API credentials;
- unreviewed model-generated shell/tool execution;
- cryptographically anonymous voting;
- replay guarantees for live stochastic inference;
- treating imported content hashes as local authority;
- treating LATTICE/world geometry as literal cognitive coordinates;
- treating the v2.0 Lean publication as formal coverage of every later 2.1.1 extension.

See `README.md`, `README4AI.md`, `HOWTO.md`, `docs/API.md`, `SECURITY.md`, `THREAT_MODEL.md`, `docs/ARK_PROTOCOL.md`, `docs/PERSISTENT_WORLD.md`, and `docs/RELEASE_NOTES_2.1.1.md` for operational details.
