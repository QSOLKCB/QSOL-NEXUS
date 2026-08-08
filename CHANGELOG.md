# Changelog

All notable changes to QSOL NEXUS are documented here.

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

- The runtime reports `network: none` and only exposes the `mock` adapter in this stage.
- Raw detected secrets are not hashed or partially echoed into placeholders.
- Provider credentials remain forbidden from semantic prompts, world objects, Council transcripts, receipts, and archives.
- Real provider adapters remain blocked on the dedicated adapter threat model.

### Not implemented

This milestone intentionally adds no OpenAI, Anthropic/Claude, Gemini, Grok, Ollama, or generic remote provider integration; no provider authentication; no Rust TUI; and no claim of final QEC-level replay/proof semantics.

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

### Not implemented

This milestone intentionally added no new NEXUS 2.x runtime, provider SDK, authentication mechanism, Council executor, persistent world database, or Rust/Python application code.

## [1.0.0] — 2026-07-14

The original deterministic browser workbench is preserved under `archives/v1.0.0/`. See its archived `CHANGELOG.md` for the complete 1.0 release notes.
