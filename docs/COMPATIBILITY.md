# NEXUS 2.0 Compatibility

## Release target

```text
runtime / Python package / Rust TUI  2.0.0
control protocol                      nexus/0.14
release-validation Rust/Cargo        1.97.1
Python                                >= 3.11
```

The `2.0.0` identifiers describe the intended stable bits in PR #51. Stable release status begins only when the exact merged green #51 commit is tagged `v2.0.0`.

## Operator compatibility

The supported first-party operator path is the repository `./nexus` launcher plus the Rust IRC-style TUI. The control plane remains newline-delimited JSON over local stdio; NEXUS does not require an IRC daemon or browser application.

The launcher may create a local virtual environment, install the Python package editable for the checkout, build the Rust TUI, and create private local storage roots. Python 3.11+ is required. The final release validation toolchain pins Rust/Cargo 1.97.1 for reproducible CI review; future compatible compiler versions are not automatically a protocol change.

## Runtime/API compatibility

The stable candidate keeps protocol identifier `nexus/0.14`. Existing historical public Python API aliases are rebound to the final Wall-capable runtime so package-root and established import paths share the post-PR #50 operation surface.

Live model inference remains non-replayable even when a provider offers a seed. Deterministic runtime/game/instrument operations retain their own declared replay contracts.

## WorldStore compatibility

NEXUS 2.0 preserves canonical content-addressed `object:<sha256>` identity. WorldStore Continuity can baseline admitted legacy object history without changing existing object IDs, then uses replicated manifests/quorum recognition for durable history. Mutable indexes are reconstructable convenience.

Recovery is deliberately non-destructive: an Ark restores into a new empty target. Do not overwrite a source WorldStore with an Ark restore.

## LATTICE-address compatibility

The LATTICE-backed world-presence layer is additive to existing WorldStore identity. It pins the LATTICE v1 profile `qsol-3x3x3-sierpinski-derived-memory/1` with semantic fingerprint `sha256:6e7c4a9a781d552a2b561d334a8435c12efe2908fcd24a0f152935aded555bcf`.

Unknown profile majors, unknown profiles in the same major, and changed semantic fingerprints fail closed. Additive non-semantic descriptor metadata remains compatible. Historical LATTICE address identity is always the pair `(profile_id, address)` and an address/profile migration is recorded as a new derived presence event retaining both source and target identities.

Existing `object:<sha256>` IDs are never reinterpreted as LATTICE `content_ref` values. The LATTICE binding is a separate digest of canonical `WorldObject.as_dict()` serialization. Named NEXUS regions and LATTICE addresses remain independent explicit identities; neither implies truth, epistemic privilege, cognitive coordinates, or governance authority.

See `docs/LATTICE_WORLD_CONTRACT.md` and `fixtures/lattice/nexus-consumer-v1.json` for the executable consumer contract.

## Adapter compatibility

Admitted local backends are deterministic/mock, Ollama, LM Studio, AnythingLLM, and generic loopback OpenAI-compatible runtimes. Admitted cloud providers are xAI, OpenAI, Anthropic, Gemini, Groq, and Together through reviewed fixed-host transports.

A new provider, endpoint class, credential method, or tool-execution boundary is not automatically compatible merely because it speaks an OpenAI-shaped JSON protocol; it requires its own admitted adapter/security contract.

## Deliberate non-compatibilities

NEXUS 2.0 does not promise compatibility with:

- the archived NEXUS 1.0 browser workbench as a trusted control surface;
- arbitrary remote Ollama/OpenAI-compatible hosts;
- consumer/browser sessions imported as API credentials;
- unreviewed model-generated shell/tool execution;
- cryptographically anonymous voting;
- replay guarantees for live stochastic inference.

See `HOWTO.md`, `docs/API.md`, `SECURITY.md`, and `docs/ARK_PROTOCOL.md` for operational details.
