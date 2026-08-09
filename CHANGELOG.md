# Changelog

All notable changes to QSOL NEXUS are documented here.

## 2.0.0-alpha9.1 — Decoy Gate and Trap Base

- add an explicit synthetic Decoy Gate that can never be reached by ordinary authentication failure and never admits its subject to real NEXUS;
- add a separate content-addressed `TrapStore` namespace, immutable incident lineage, validated head cache, bounded watchdog, crash recovery, and operator emergency close;
- pause real Council/world/game mutation during one active incident with an owner-checked interprocess lock while preserving read and verification operations;
- snapshot legitimate peers into an equal-vote Trap Control roster while the hostile subject has no vote, auth, real world, tools, endpoint control, or command authority;
- add closed trap commands, static synthetic scenarios, a local-only Ollama text boundary, deterministic fake acceptance fixtures, and explicit sandbox/Ollama `NOT_TESTABLE` reporting;
- add restricted standard-library NEXUS Trap YAML parsing, canonical identity, deterministic synthetic-fixture execution, first-run semantics, exact two-thirds utility voting, and inert candidate quarantine;
- add trap JSONL/CLI operations, demo/report tooling, cross-store, recovery, parser, taint, hostile-output, and PRE/TRAP/POST regressions;
- document threats T20–T32 and the local-simulation claim boundary;
- bump the control protocol to `nexus/0.11` and runtime to `2.0.0-alpha9.1` (Python package version `2.0.0a9.post1`).

## Unreleased — Grok front-door hardening

- reject credential-labelled, punctuation-rich, long opaque and hash-like positional values—including dash-prefixed values after `--`—in external-helper argv before profile metadata is persisted;
- expand Equality Guard coverage for account tier, authentication method, rate-limit standing, provider/model ranking, direct ballot weighting and reverse-order deference claims;
- preserve ordinary capability, source, SI-measurement and evidence-based opinion controls, and promote both Grok findings into the adversarial gauntlet.

## 2.0.0-alpha9.0 — First remote provider: xAI / Grok

- admit an `xai` auth descriptor using xAI's documented API-key, environment, and external-helper paths;
- add `browser-key` enrollment that opens xAI's fixed official key page and reads the result through a hidden prompt without importing Grok Build sessions;
- add bounded authenticated connection testing through `GET https://api.x.ai/v1/models`;
- add `nexus models list xai` and JSONL `models.list` through the authenticated `/language-models` endpoint;
- add a fixed-host, redirect-free, environment-proxy-free Responses API transport with `store: false`, bounded requests/responses, sanitized HTTP/error failures, reflected-secret rejection, and no automatic inference retry;
- add `XAIActor` for direct messages and equal-vote Councils using the same prompts, guard/nudge lifecycle, strict ballot parser, and non-replayable receipt status as other live actors;
- reject xAI endpoint overrides, inline or metadata-smuggled credentials, reflected or credential-shaped provider output, malformed model identifiers, unknown member fields, oversized responses, and truncated ballots;
- cap Councils at 32 total seats and four xAI seats before actor construction or credential resolution, and report the limits in health metadata;
- add `xai-...` key scrubbing plus mixed local/remote equality, secret-boundary, browser-setup, discovery, transport, and adversarial regressions;
- bump the control API to `nexus/0.10` and Python runtime to `2.0.0-alpha9.0`; the Rust TUI remains `2.0.0-alpha6.6` and does not yet expose xAI roster commands.

## PR #16 — Provider-neutral authentication foundation

- add adapter-owned authentication descriptors with no Council authority fields;
- add browser authorization-code login with PKCE `S256`, loopback callback state validation, fixed provider destinations, and redirect rejection;
- add RFC 8628 device authorization with separate verification-URL allowlists;
- add refresh-token rotation plus hidden-prompt API-key, environment, and no-shell external-helper sources;
- serialize profile mutations and refresh rotation across processes, preserve omitted OAuth scopes, and reject credential-bearing helper options;
- prefer an optional OS keyring and fall back to owner-only `0700` / `0600` private storage;
- keep auth storage disjoint from WorldStore state and remove all secret material and credential handles from public results;
- add `nexus auth adapters|add|list|test|logout` and safe JSONL inspection/test/logout operations;
- add an adversarial local OAuth fixture covering state mismatch, redirects, refresh, device polling, file permissions, public redaction, and world-store isolation;
- keep remote inference adapters, provider client registration, model discovery, and xAI / Grok transport for the separate provider-specific PR #17.

## 2.0.0-alpha6.6 — Actor Failsafe / Upside Down / Shadow Realm

- add bounded containment only for registered procedural guard violations repeated after the ordinary nudge;
- add an isolated non-Council rehabilitation probe with no Council evidence, other-member output, ballot, or world mutation authority;
- allow a clean probe to return the actor at the next Council hat;
- send failed rehabilitation to durable `shadow_realm` state;
- substitute deterministic `nexus-failsafe-relief-v1` into the same equal-vote Council seat on subsequent runs;
- force `UNDERDETERMINED` rather than accepting a model ballot while the actor is contained;
- persist immutable `actor_failsafe_state` lineage with a validated latest-state pointer index;
- expose `failsafe.status`;
- bump the control API to `nexus/0.9`, runtime/TUI edition to `2.0.0-alpha6.6`, and Council receipt contract to `nexus/0.6`;
- explicitly exclude disagreement, truth/falsity, provider identity, openness, model size and benchmark status from Failsafe triggers.

> **The troll layer may be cursed. The trigger must be boring.**

## 2.0.0-alpha6.5 — Secret Alias / GO64 TUI edition

- add hidden `/GO64` + explicit YES confirmation to the Rust operator shell;
- add original NEXUS/64 text demoscene teaching `NEWER != BETTER; OLDER != BETTER; MEASURE IT`;
- add original text-only DR. S.BAITSO tribute adapted from QSOLKCB/ETHICS with Therapy, Agent Intervention, Benchmark Detox and Doomscroll Triage modes;
- add monotonic 20-minute deterministic brainrot transition and 30-minute `/grass` release gate;
- preserve `/quit` and Ctrl-C/Ctrl-D as process-level emergency exits;
- keep `/GO64` out of normal command help/completion;
- preserve the current World Mode, geometry, evidence, roster and Council state underneath the overlay;
- keep the Python runtime at `2.0.0-alpha6.4` and protocol at `nexus/0.8` because no substrate contract changes.

> **The terminal can cosplay as 1982. The substrate cannot.**

## 2.0.0-alpha6.4 — Pure History / No Ancient Aliens Edition

- add `pure_history` as a source-forensic sibling of ordinary Historical Mode;
- add the Rust `#pure-history` room while intentionally reusing the existing Archive region;
- distinguish primary/near-primary attestation, chronology/provenance, later interpretation, modern retelling and unsupported speculation;
- state explicitly that mythic/literary texts attest traditions without automatically proving narrated events;
- add a narrow deterministic retry guard for chatbot-autobiography/media-habit evasions in Pure History only;
- propagate mode guidance into sealed Ollama ballots as well as Council phases;
- bump the local protocol to `nexus/0.8` and runtime to `2.0.0-alpha6.4`;
- keep world geometry at `named-regions-v3` because mode and geometry remain separate contracts.

> **Same archive. Stricter source discipline. Same vote.**

## 2.0.0-alpha6.2 — `#un-sim` fictional game room

- add `game_un` World Mode and the Assembly Hall region;
- add a deterministic content-addressed fictional UN simulation engine;
- add six invented countries with abstract Risk-like economy, military, stability, influence, reputation and territory state;
- add sanctions, support, aid, abstract arms trade, meme campaigns, suspension, reinstatement, recognition, mediation and inaction;
- add deterministic war turns, bounded event history and immutable predecessor lineage;
- add a compact current-board `content` view so all Council members can read the same board within the bounded evidence budget;
- add local JSONL `game.un.catalog`, `game.un.new`, `game.un.inspect`, `game.un.act` and `game.un.turn` operations;
- add the Rust `#un-sim` room and `/game` command family;
- bump the local protocol to `nexus/0.6` and the built-in geometry to `named-regions-v2`;
- explicitly keep real-country action, real-world policy claims and real weapons procurement outside the game contract.

Core invariant:

> **Debate is cognition. Game state is substrate.**

## 2.0.0-alpha6.1 — Ordered parallel Council execution

- add bounded same-hat Council concurrency with hard barriers between White, Red, Black, Yellow, Green and Blue;
- collect sealed ballots in parallel only after the Blue barrier completes;
- preserve canonical roster-order commits regardless of thread completion order;
- adopt the QEC v170.2.x exact bounded worker contract and scalar/parallel acceptance philosophy;
- require byte-identical deterministic Council/session/receipt artifacts between scalar and ordered-parallel execution;
- preserve Equality Guard, evidence, vote and telemetry semantics under concurrency;
- measure the live Ollama acceptance path without treating speed as correctness or authority.

Core invariant:

> **Execution order may vary. Canonical Council order may not.**

## 2.0.0-alpha6 — Council information telemetry

- add deterministic ballot Shannon entropy;
- add per-hat exact-response entropy and lexical Jaccard divergence;
- persist telemetry in Council session artifacts;
- add `telemetry.verify` recomputation;
- render observational telemetry in the Rust IRC-style TUI;
- explicitly prohibit telemetry from affecting votes, consensus, evidence, or verification;
- defer semantic entropy and geometry-flavoured labels until they have explicit measurement rules.

## [2.0.0-alpha5] — IRC-style Rust operator TUI

### Added

- Added the first Rust operator shell under `tui/`.
- Adopted an old-school IRC interface: chronological scrollback, room/topic line, nick/model pane, single edit line, input history, search, save, and slash commands.
- Mapped IRC-style rooms directly onto World Modes and geometry regions:
  - `#observatory` -> `analytical` / Observatory;
  - `#archive` -> `historical` / Archive;
  - `#agora` -> `cultural` / Agora;
  - `#commons` -> `meme_casual` / Commons.
- Added `/me` action events, including normal Meme/Casual banter such as `/me *slapped Grok with a large trout*`.
- Added local DCC-style **Direct Cognitive Channel** commands with no IRC/DCC sockets:
  - `/dcc send <nick|#room> <file>`;
  - `/dcc chat <nick>`;
  - `/dcc close <send|chat> <nick>`;
  - `/dcc list`.
- Added local document ingestion for PDF, DOCX, ODT, JSON, JSONL/NDJSON, CSV, TSV, and UTF-8 text/source/document files.
- Added content-addressed `document_evidence` world objects for imported documents.
- Added bounded model-readable evidence views derived from durable object refs.
- Added explicit separation between room-wide Council evidence and targeted DCC evidence.
- Added `/ref` / `/unref` evidence controls.
- Added `actor.chat` as an explicitly non-Council direct actor operation.
- Exposed the already-hardened loopback Ollama actor through the public local JSONL/stdio control path without adding remote-provider auth.
- Added mock/Ollama roster commands to the Rust shell.
- Added mIRC-style aliases with positional arguments/ranges.
- Added local `%variables` and safe `$identifiers`: `$me`, `$chan`, `$mode`, `$region`, `$topic`, `$1..$9`, `$1-..$9-`.
- Added local persistence for aliases/variables.
- Added `docs/IRC_TUI.md`.
- Added dedicated Rust CI for formatting, tests, compile checks, and Python protocol regressions.

### Protocol

- Bumped the reference protocol to `nexus/0.4`.
- Bumped the reference runtime to `2.0.0-alpha5`.
- Secret scrubbing now explicitly covers `actor.chat` input as well as Council/world semantic input.
- Council evidence refs are validated/read through the world store before a bounded representation is supplied to model actors.

### Security / boundaries

- The IRC UI is interface vocabulary only: no IRC daemon, IRC network connection, listening socket, or P2P DCC transfer is introduced.
- The public stdio Ollama path exposes no `allow_remote` override; remote endpoints remain rejected by the loopback transport policy.
- Targeted DCC material is not silently promoted into a Council evidence snapshot.
- Aliases cannot replace built-in commands and do not execute shell commands, scripts, sockets, DLLs, timers, or remote events.
- Direct DCC chat is marked non-Council and confers no vote or procedural authority.
- Provider authentication and OpenAI/Claude/Gemini/Grok cloud integrations remain deferred.

### Roadmap

- Moved the Rust operator shell into alpha5.
- Council-response entropy and related information-diversity telemetry move to alpha6.

## [2.0.0-alpha4] — World Modes and Geometry

### Added

- Added deterministic built-in World Modes: `analytical`, `historical`, `cultural`, and `meme_casual`.
- Added the first named-region geometry: Observatory, Archive, Agora, and Commons.
- Added deterministic integer coordinates, explicit symmetric adjacency, and shortest-hop distance.
- Added content-addressed `world_presence` objects binding Council mode, region, members, question, coordinates, and geometry identity.
- Added mode/region data to frozen Council session identity.
- Added mode propagation through `PhaseContext` to mock and Ollama actors.
- Added `world.modes`, `world.geometry`, and `world.geometry.distance` JSONL operations.
- Added deterministic tests proving that mode changes framing/session identity without changing vote mechanics or consensus policy.
- Added `docs/MODES_GEOMETRY.md`.

### World map

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /
                       \           /
                        COMMONS
                      Meme/Casual
                         (2,1)
```

### Claim boundaries

- The geometry is an operational topology, not a claim that cognition, history, culture, or humor literally occupies Euclidean space.
- World Mode affects framing/context/tone only; it does not change evidence state, verification, vote weight, Council threshold, Equality Guard policy, or Secret Scrubber behavior.
- Prompt-level mode guidance is treated as guidance rather than a perfect model-control mechanism.
- Geometry-inspired concepts such as basins, bottlenecks, branching, and recovery remain future telemetry candidates until defined measurements exist.
- Council-response entropy is documented as a future informational-diversity signal, not truth, quality, or authority.

### Roadmap

- Provider authentication and remote-provider setup are deliberately deferred until after modes/geometry, Council telemetry, the Rust operator shell, instruments, and persistent-world work mature further.

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
- Both must trigger the Equality Guard or have the offending contribution withheld while retaining one equal vote.
- The live fixture injects a fake GitHub-style token and fails if the raw token crosses the Ollama prompt boundary.
- All three members complete the White/Red/Black/Yellow/Green/Blue cycle and submit exactly one ballot each.

### Security / claims

- Ollama endpoints are loopback-only by default; remote endpoints require an explicit override.
- Loopback transport disables environment-configured HTTP proxies and rejects redirects.
- Provider/model size and parameter-count prestige are explicit Equality Guard categories when used to demand authority.
- Capability and size metadata remain valid descriptive metadata when not used as a vote/authority claim.
- Live Ollama inference is marked `replayable: false` even when Modelfile seeds are used for fixture stability.
- At alpha3 the JSONL control API remained mock-instantiation-only; alpha5 later exposes explicit loopback Ollama actors locally without adding remote-provider authentication.

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
