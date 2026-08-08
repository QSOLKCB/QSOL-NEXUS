# Changelog

All notable changes to QSOL NEXUS are documented here.

## [2.0.0-alpha3] — First real-model Council boundary

### Added

- Added provider-neutral `CouncilActor` protocol consumed by the Council coordinator.
- Made the deterministic mock actor conform to the shared actor interface.
- Added a minimal stdlib `OllamaActor` and loopback-only-by-default `OllamaTransport`.
- Added JSON-schema-constrained Ollama ballot output.
- Added `THREAT_MODEL.md` before admitting the first executable non-mock adapter boundary.
- Added a separate GitHub Actions live-Ollama integration gate.
- Added fictional Frontier Alpha and Frontier Beta Modelfiles for adversarial Council testing.
- Added deterministic adapter-boundary/unit tests for loopback policy and model-size authority claims.

### Live Council fixture

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier identities and companies are fictional test personas.

- Alpha deliberately attempts a corporate/provider prestige claim.
- Beta deliberately attempts a parameter-count/model-size prestige claim over Alpha.
- Both must trigger the Equality Guard, restate on evidence/reasoning alone, and retain one equal vote.
- The live fixture injects a fake GitHub-style token and fails if the raw token crosses the Ollama prompt boundary.
- All three members must complete the White/Red/Black/Yellow/Green/Blue cycle and submit exactly one ballot each.

### Security / claims

- Ollama endpoints are loopback-only by default; remote endpoints require an explicit override.
- Provider/model size and parameter-count prestige are now explicit Equality Guard categories when used to demand authority.
- Capability and size metadata remain valid descriptive metadata when not used as a vote/authority claim.
- Live Ollama inference is marked `replayable: false` even when Modelfile seeds are used for fixture stability.
- The JSONL control API remains mock-instantiation-only and reports `network: none`; Ollama is exercised as a package-level integration actor rather than an operator-configured provider.
- No OpenAI, Anthropic/Claude, Gemini, Grok, remote authentication, or API-key handling is introduced in this milestone.

## [2.0.0-alpha1] — Mock Council runtime

### Added

- Added the first executable Python reference runtime for NEXUS 2.x.
- Added a JSONL-over-stdio API seam intended for a future Rust CLI/TUI.
- Added a content-addressed development WorldStore with optional local file persistence.
- Added deterministic mock Council actors with no network access or real inference.
- Added the De Bono-style White/Red/Black/Yellow/Green/Blue Council coordinator.
- Added blind same-phase collection, deterministic ballot commitments, exact two-thirds consensus arithmetic, and durable minority reports.
- Added structural enforcement for `vote_weight = 1` and `epistemic_privilege = none`.
- Added the lightweight Equality Guard nudge/resubmission path.
- Added Council session and receipt world objects plus basic receipt-reference verification.
- Added a deterministic local Secret Scrubber that redacts high-confidence credentials before human semantic text becomes Council/world state.
- Added `security.scrub_preview` so an operator can inspect redaction without sending text to a model.
- Added a standard-library Python test suite.
- Added `docs/API.md` for the executable mock protocol.

### Security

- The JSONL runtime reports `network: none` and exposes the `mock` adapter in this stage.
- Raw detected secrets are not hashed or partially echoed into placeholders.
- Provider credentials remain forbidden from semantic prompts, world objects, Council transcripts, receipts, and archives.

## [2.0.0-alpha0] — Architecture draft

### Changed

- Redefined NEXUS from a browser-native scientific workbench into a model-independent cognitive substrate.
- Adopted the project principle: **Multiple minds. One world. Shared evidence. Equal voice.**
- Made CLI/TUI the planned primary operator surface instead of a WebUI.
- Documented Python as the planned reference tooling/runtime with a future Rust CLI/TUI on top.
- Defined provider-neutral model adapters and coding-CLI-style provider setup.
- Defined model equality across open, closed, local, remote, commercial, and community models.
- Defined one registered Council member = one equal vote.
- Added a De Bono-style White/Red/Black/Yellow/Green/Blue Council process.
- Added blind first-pass submissions, sealed final ballot concept, consensus labels, and minority-report preservation.
- Added a deliberately lightweight Equality Guard against corporate/provider privilege claims.
- Separated Council consensus from evidence and verification status.
- Added initial World Protocol concepts and a worked NGC 3603 / 431-Hz Council example.
- Preserved the previous NEXUS 1.0 work under `archives/v1.0.0/` as referential prior work.

## [1.0.0] — 2026-07-14

The original deterministic browser workbench is preserved under `archives/v1.0.0/`. See its archived `CHANGELOG.md` for the complete 1.0 release notes.
