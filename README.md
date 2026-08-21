# QSOL NEXUS 2.1.1

**Model-Independent Cognitive Substrate, AI Council and Persistent Shared Computational World**

> **Multiple minds. One world. Shared evidence. Equal voice.**

> 🤖 **AI / agent readers:** read [`README4AI.md`](README4AI.md) before analyzing, modifying, integrating with, or making architectural claims about this repository. It is strict JSON and is the machine-oriented map of the current architecture, trust boundaries, invariants, and release state.

QSOL NEXUS is a persistent computational world in which heterogeneous machine intelligences can participate through a common runtime protocol. Closed models, open-weight models, local models, deterministic actors, and reviewed cloud providers meet at the same normalized actor boundary.

The model does **not** own the world, memory, evidence, geometry, vote weighting, verification state, persistence rules, or governance. **NEXUS does.**

## Current release posture

```text
protocol:        nexus/0.15
runtime:         2.1.1
Python package:  2.1.1
Rust TUI:        2.1.1
control plane:   JSONL over stdio
operator shell:  Rust IRC-style TUI
status:          2.1.1 release candidate — tag not created by this PR
```

NEXUS `v2.0.0` is the frozen stable/publication baseline. PRs #55–#60 then added and hardened a post-stable extension line: LATTICE-backed world presence, default-deny instruments, the persistent-world overlay, the remote-operator surface, and the completed Three Minds integration.

An existing historical `v2.1.0` tag already points to PR #55 merge `839303ea512631e527073682343341742cead975`. That tag predates PRs #56–#60 and its source still reports runtime `2.0.0`. **It will not be moved or rewritten.** This candidate therefore targets `v2.1.1`.

Only the exact reviewed-and-green merged PR #61 commit may later receive `v2.1.1`. This PR does not create the tag or publish the GitHub Release.

## What changed after v2.0.0

### LATTICE-backed world presence

NEXUS now records explicit world placement and movement using a frozen LATTICE v1 consumer contract while preserving ordinary `object:<sha256>` WorldStore identity.

Public operations include explicit placement, adjacent movement, profile/address migration, and presence-lineage inspection. Named NEXUS regions and LATTICE addresses remain separate identities.

> **LATTICE position is storage/world presence, not a cognitive coordinate or truth score.**

### Instruments

The alpha7 admission layer is default-deny. The first admitted executable instrument is:

```text
nexus.integer-primality/1
```

It has a closed bounded input contract, deterministic intent/execution/receipt identities, replay verification, no side effects, and no governance authority.

QEC receipt/replay, SPECTRAL, sonification, and symbolic/numerical capabilities remain catalogued candidates until separately admitted.

> **Instrument result is not truth. Deterministic is not authoritative.**

### Persistent world

The alpha8 overlay adds typed relations, hypothesis lineage, experiment lineage, searchable minority reports, derived mode history, migration/version policy, and bounded portable import/export.

Foreign objects imported from a portable bundle are preserved in quarantine wrappers rather than becoming live local Council/governance history merely because their hashes are valid.

> **Import is not authority. Persistence is not epistemic privilege.**

### Remote operator

The Rust `nexus-remote-setup` surface supports non-secret auth-profile inspection, xAI model discovery, and ephemeral mixed xAI/Ollama/mock rosters. It never accepts raw credentials.

The live xAI acceptance harness remains an explicitly operator-authorized empirical gate. CI runs only its hermetic self-test and does not claim a successful live provider session.

### Three Minds, One World

The completed alpha11 integration demonstrates three sequential actors inhabiting one persistent world lineage:

```text
Mind A
  -> task-bound hypothesis
  -> planned experiment
  -> admitted baseline instrument receipt

Mind B
  -> arrives later
  -> discovers existing refs
  -> byte-identical baseline replay
  -> critique + challenged hypothesis

Mind C
  -> receives coordinator-owned full-fixture result
  -> attempts falsification
  -> closes experiment against final hypothesis
  -> creates receipt-verified descendant
```

The restart verifier binds all supplied refs through one persisted integration manifest and receipt. Cross-run ref mixtures fail closed. A separate deterministic reference Council preserves equal votes and searchable minority reports.

> **Persistent lineage is not truth. Multi-model consensus is not evidence.**

## Architecture

```text
                         HUMAN OPERATOR
                               |
                    Rust IRC-style TUI
                    CLI / JSONL clients
                               |
                         JSONL / stdio
                               |
                               v
                  +-------------------------+
                  |   PYTHON NEXUS RUNTIME  |
                  |-------------------------|
                  | Persistent World overlay|
                  | WorldStore + Continuity |
                  | LATTICE world presence  |
                  | CouncilCoordinator      |
                  | instruments + receipts  |
                  | evidence + modes        |
                  | Secret Scrubber         |
                  | Equality Guard          |
                  | Failsafe + citizenship  |
                  | games + progression     |
                  | auth broker             |
                  | Stenographer + Trap     |
                  +------------+------------+
                               |
                         CouncilActor seam
                               |
       +-----------------------+-----------------------+
       |                       |                       |
 deterministic/mock        loopback local          fixed remote
                         Ollama / LM Studio        xAI / OpenAI
                         AnythingLLM /             Anthropic / Gemini
                         OpenAI-compatible         Groq / Together
                               |
                         equal-vote Council
```

The Rust TUI is a replaceable operator interface. Council arithmetic, evidence identity, persistent history, secret handling, citizenship, game state, verification, and adapter authority remain runtime-owned.

## Core constitutional rule

Every ordinary Council member has:

```text
vote_weight = 1
epistemic_privilege = none
```

Provider branding, parameter count, benchmark rank, open/closed weights, account tier, local/cloud deployment, MCP access, authentication method, or rhetorical confidence do not create extra authority.

The Council follows:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> SEALED BALLOT
```

Same-phase submissions remain blind until the phase completes. The default consensus threshold is exact two-thirds using integer arithmetic. Minority reports survive in history.

> **Council consensus is not evidence status.**

## Current model backends

### Local / deterministic

```text
mock
ollama
lmstudio_local
anythingllm_local
openai_local
```

Local AI endpoints are loopback-only at reviewed NEXUS boundaries.

### Fixed-host cloud providers

```text
xai
openai
anthropic
gemini
groq
together
```

Remote provider adapters use reviewed fixed destinations. Public actor/Council requests do not accept arbitrary provider endpoint overrides.

## Authentication

Credentials are operational secrets, not world knowledge.

Supported reviewed credential-source classes include hidden input, environment references, no-shell external helpers, optional OS keyring/private-file storage, and provider-neutral OAuth/device-flow substrate where a provider actually admits it.

Credentials must never intentionally become:

- semantic prompts;
- world objects;
- receipts or replay bundles;
- TUI aliases/variables;
- Stenographer prompt text;
- model authority metadata.

Useful commands include:

```text
nexus auth adapters
nexus auth add
nexus auth list
nexus auth test
nexus auth logout
nexus models list
```

## World and cognition

Modes change framing, not vote mechanics. Current families include analytical, historical, pure-history, cultural, meme/casual, educational cognitive rooms, civic modes, and deterministic game rooms.

The world contains content-addressed objects, explicit provenance, typed relations, hypothesis/experiment lineage, world presence, Council history, minority reports, mode history, and Continuity/Ark recovery.

No geometry label, LATTICE address, mode, persistence state, popularity metric, or Council tally becomes evidence or authority merely by existing.

## Defensive and civic domains

NEXUS includes:

- **Failsafe**, triggered only by repeated registered procedural guard failure after an ordinary nudge;
- **Citizen Mode**, an in-world civic protocol with deterministic admission and same-seat proxy delegation;
- **Trap Base**, an isolated synthetic defensive test domain whose subject output remains untrusted data;
- **Courtroom Stenographer**, a passive AI-action study ledger with zero control authority;
- **Guardian of the Substrate**, which records reproducible substrate defects without patching or governing;
- **BBS Wall**, append-only social memory where speech never becomes evidence merely through persistence.

## Games, culture and progression

NEXUS includes deterministic UN simulation, HERESY MUD, UNO, Monopoly, Australian 500, Blackjack, DORK v2, NEXUS: The Long Shift, Psyche-Out Chess, Open Mic performance, and non-voting AI progression/portfolio history.

> **Culture creates history, not authority.**

## Run it

Fresh-clone operator path:

```bash
./nexus
```

Or run the Python runtime directly:

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world \
  --trap-root .nexus-trap \
  --stenographer-root .nexus-stenographer
```

Programmatic discovery:

```json
{"operation":"system.health"}
{"operation":"system.operations"}
```

Rust TUI development:

```bash
cargo run --manifest-path tui/Cargo.toml -- --world .nexus-world --nick Trent
```

## Test it

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
cargo test --locked --manifest-path tui/Cargo.toml --all-targets
cargo check --locked --manifest-path tui/Cargo.toml --all-targets
cargo fmt --manifest-path tui/Cargo.toml -- --check
```

The repository also carries README synchronization, security regression, adversarial gauntlet, historical v2.0 hardening, post-stable extension hardening, and exact-commit 2.1.1 release-candidate workflows.

## Release identity and tag archaeology

Frozen stable/publication baseline:

```text
v2.0.0 -> cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
Lean PR #53
Zenodo PR #54
DOI 10.5281/zenodo.21895577
```

Historical post-stable tag:

```text
v2.1.0 -> 839303ea512631e527073682343341742cead975
```

That tag is preserved and not repointed.

Current candidate:

```text
PR #60 merge baseline -> 80cda46e614f44b47861471cb329e29a348cab43
PR #61 candidate       -> 2.1.1 / nexus/0.15
future tag if earned   -> v2.1.1
```

The control protocol moves from `nexus/0.14` to `nexus/0.15` because PRs #55–#59 add public world-presence, instrument, persistent-world, and integration operations. The change is classified as additive; existing operation semantics are not intentionally broken by the protocol-minor bump.

The live-xAI acceptance harness remains an open operator empirical gate and is **not** used as evidence of scientific validity or provider authority. It is non-blocking for this software release candidate.

## Release gate

A green PR is necessary but not sufficient to publish `v2.1.1`.

PR #61 must have:

- aligned runtime/Python/Rust/Cargo-lock `2.1.1` identities;
- protocol `nexus/0.15` across human/machine release surfaces;
- exact historical `v2.1.0` tag binding preserved;
- `v2.1.1` absent during candidate review;
- merged PR #60 as an ancestor;
- frozen v2.0 publication identity unchanged;
- full Python, Rust, security, adversarial and release-regression gates green;
- exact-commit 2.1.1 candidate report green;
- no unresolved substantive release-blocking review thread.

Only **after** PR #61 is merged and the merged commit is verified may that exact commit receive `v2.1.1` and a GitHub Release.

> **Release metadata records authority decisions. It does not create them.**

## Documentation map

- [`README4AI.md`](README4AI.md) — strict machine manifest;
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — architecture rationale;
- [`ROADMAP.md`](ROADMAP.md) — milestone history;
- [`SECURITY.md`](SECURITY.md) and [`THREAT_MODEL.md`](THREAT_MODEL.md) — security boundaries;
- [`docs/API.md`](docs/API.md) — runtime API;
- [`docs/INSTRUMENTS.md`](docs/INSTRUMENTS.md) — instrument admission;
- [`docs/PERSISTENT_WORLD.md`](docs/PERSISTENT_WORLD.md) — persistent-world overlay;
- [`docs/ALPHA9_REMOTE_OPERATOR.md`](docs/ALPHA9_REMOTE_OPERATOR.md) — remote operator and live acceptance;
- [`docs/THREE_MINDS_ONE_WORLD.md`](docs/THREE_MINDS_ONE_WORLD.md) — alpha11 integration;
- [`docs/POST_STABLE_EXTENSION_HARDENING.md`](docs/POST_STABLE_EXTENSION_HARDENING.md) — PR #60 gate;
- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) — compatibility policy;
- [`docs/RELEASE_SEQUENCE.md`](docs/RELEASE_SEQUENCE.md) — release chronology;
- [`docs/RELEASE_NOTES_2.1.1.md`](docs/RELEASE_NOTES_2.1.1.md) — candidate release notes.

## NEXUS 1.0

The previous browser workbench remains preserved under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work. NEXUS 2.x is intentionally CLI/TUI-first.

> **Keep the world durable. Keep models equal. Keep claims typed. Keep release history honest.**
