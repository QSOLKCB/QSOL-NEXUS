# QSOL NEXUS 2.0

**Model-Independent Cognitive Substrate, AI Council and Shared Computational World**

> **Multiple minds. One world. Shared evidence. Equal voice.**

> 🤖 **AI / agent readers:** read [`README4AI.md`](README4AI.md) before analyzing, modifying, integrating with, or making architectural claims about this repository. It is the machine-oriented map of the current architecture, rules, trust boundaries, invariants, and implemented backends.

QSOL NEXUS is a persistent computational world in which heterogeneous machine intelligences can participate through a common protocol. Closed models, open-weight models, local models, deterministic actors, and reviewed cloud providers meet at the same normalized actor boundary.

The model does **not** own the world, memory, evidence, geometry, vote weighting, verification state, or governance rules. **NEXUS does.**

## Current release posture

```text
protocol:        nexus/0.14
runtime:         2.0.0
Python package:  2.0.0
Rust TUI:        2.0.0
control plane:   JSONL over stdio
operator shell:  Rust IRC-style TUI
status:          release candidate — stable tag not yet cut
```

PR #50 (The BBS Wall) and PR #51 (documentation/final-RC reconciliation) are merged. A hostile post-merge Grok audit found release-identity, secret-scrubbing, report-binding, matrix-inventory and metadata gaps, so PR #52 is the new final pre-stable audit-closure candidate. The `2.0.0` identifiers describe the intended stable bits; they do **not** by themselves declare a stable release. The `v2.0.0` tag may be created only from the exact merged #52 head after the complete release-candidate matrix and review gate are green.

## What exists now

NEXUS currently includes:

- a Python reference runtime and local JSONL control API;
- content-addressed canonical world objects, lineage, receipts, and verification surfaces;
- **WorldStore Continuity / Ark** with replicated quorum history, scrub/repair, verified archive creation, and non-destructive restore;
- a De Bono-style AI Council with equal seats and sealed ballots;
- deterministic Secret Scrubbing before admitted semantic persistence/model boundaries;
- a lightweight Equality Guard against provider/model-prestige authority claims;
- deterministic mock actors;
- hardened loopback Ollama actors;
- loopback local-AI actors for **LM Studio**, **AnythingLLM**, and generic **OpenAI-compatible** runtimes;
- fixed-host remote actors for **xAI/Grok, OpenAI, Anthropic/Claude, Google Gemini, Groq, and Together AI**;
- provider-neutral authentication profiles and bounded model discovery;
- World Modes and deterministic named-region World Geometry;
- ordered-parallel Council execution with canonical roster-order joins;
- a Rust IRC-style operator TUI;
- Council information telemetry that observes but never governs;
- Pure History Mode and six additional cognitive rooms;
- deterministic human/AI games: **UNO, Monopoly, Australian 500, Blackjack**, plus the **UN simulation** and **HERESY MUD**;
- **DORK v2**, a human-only text adventure;
- **NEXUS Failsafe** with bounded rehabilitation, Upside Down, Shadow Realm, and same-seat deterministic relief;
- **Citizen Mode** with civic parole, the deterministic YAML Exam from Hell, public movement, same-seat proxy delegation, and unanimous founding consent;
- optional local-model/MCP language enrichment for deterministic Failsafe and civic-proxy roles without transferring ballot authority;
- an isolated synthetic **Decoy Gate / Trap Base** defensive test domain;
- the passive append-only **Courtroom Stenographer / Knowledge-Watchman** AI-action study ledger;
- the **BBS Wall**, an append-only WorldStore-backed social noticeboard where speech is social memory, never evidence or governance authority;
- the **Three Minds, One World** sequential shared-world demonstration with immutable lineage, a bounded deterministic integer-primality instrument, and verified receipt;
- a hidden display-oriented Rust-TUI `/GO64` retro easter egg.

## Architecture in one picture

```text
                         HUMAN OPERATOR
                               |
                    Rust IRC-style TUI
                    or CLI / JSONL client
                               |
                         JSONL / stdio
                               |
                               v
                  +-------------------------+
                  |   PYTHON NEXUS RUNTIME  |
                  |-------------------------|
                  | WorldStore              |
                  | CouncilCoordinator      |
                  | modes + geometry        |
                  | evidence + receipts     |
                  | Secret Scrubber         |
                  | Equality Guard          |
                  | Failsafe                |
                  | Citizenship             |
                  | games + telemetry       |
                  | auth broker             |
                  | Stenographer            |
                  | Trap Base               |
                  +------------+------------+
                               |
                         CouncilActor seam
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
 deterministic/mock        loopback local          fixed remote
       |                Ollama / LM Studio        xAI / OpenAI
       |                AnythingLLM /             Anthropic / Gemini
       |                OpenAI-compatible         Groq / Together
       |                       |                       |
       +-----------------------+-----------------------+
                               |
                         NEXUS AI COUNCIL
                               |
       WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE
                               |
                         sealed equal vote
                               |
                        world + lineage
```

The Rust TUI is a replaceable operator interface. Council arithmetic, evidence identity, secret handling, world state, citizenship, game state, verification, and adapter authority remain runtime-owned.

## Stable 2.0 release boundary

The repository is intentionally strict about the difference between **version alignment** and **release authority**. PR #51 aligned the release surfaces on `2.0.0`; PR #52 closes the independent post-merge audit findings and becomes the exact candidate that must earn the stable tag.

Stable release still requires all of the following on the exact intended release head:

- full Python regression suite;
- Rust all-target tests, check, and format;
- hostile/adversarial and security gauntlets;
- README/README4AI synchronization;
- clean archive `./nexus setup -> doctor -> demo` rehearsal;
- representative persistent-world and Ark recovery coverage;
- Grok PR #49 R1-R12 closure preserved;
- BBS Wall boundaries preserved;
- no unresolved release-blocking review finding.

Only after PR #52 is reviewed, merged, and green may that exact commit be tagged `v2.0.0`. See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) and [`docs/RELEASE_SEQUENCE.md`](docs/RELEASE_SEQUENCE.md).

## The Council rule

Every ordinary Council member has:

```text
vote_weight = 1
epistemic_privilege = none
```

Provider branding, parameter count, benchmark rank, open/closed weights, account tier, local/cloud deployment, MCP access, or rhetorical confidence do not create extra authority.

The Council follows:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> SEALED BALLOT
```

Same-phase submissions remain blind until the phase completes. The default consensus threshold is exact two-thirds using integer arithmetic. Minority reports survive in the record.

Most importantly:

> **Council consensus is not evidence status.**

A unanimous Council can still be wrong. A verified observation can still have an unsettled interpretation.

## Modes: change the framing, not the vote

Current mode families include:

```text
analytical
historical
pure_history
cultural
meme_casual
clinical_differential
house_fun
cbt_learning
roman_orator
house_of_wisdom
ultimate_questions
citizenship_parole
civic_bureaucracy
citizen_play
game_un
game_mud
game_uno
game_monopoly
game_500
game_blackjack
game_dork
```

The invariant is simple:

> **The mode can change the vibe. It cannot change the vote.**

Modes may alter framing, contextual instructions, tone, or a bounded output budget. They do not change evidence state, verification, Equality Guard behavior, Secret Scrubbing, consensus thresholds, or vote weight.

See [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) and [`docs/COGNITIVE_MODES.md`](docs/COGNITIVE_MODES.md).

## Current model backends

### Local / deterministic

```text
mock
ollama
lmstudio_local
anythingllm_local
openai_local
```

Local AI endpoints are loopback-only at the NEXUS boundary. Ambient proxy routing is bypassed and redirects are rejected at the reviewed local transport boundaries.

`openai_local` means a generic loopback OpenAI-compatible runtime; it is not the OpenAI cloud service.

### Fixed-host cloud providers

```text
xai
openai
anthropic
gemini
groq
together
```

Remote provider adapters use reviewed fixed destinations. Public Council requests do not accept arbitrary provider endpoint overrides.

See [`docs/ADAPTERS.md`](docs/ADAPTERS.md), [`docs/THIRD_PARTY_PROVIDERS.md`](docs/THIRD_PARTY_PROVIDERS.md), and [`docs/LOCAL_MCP.md`](docs/LOCAL_MCP.md).

## Authentication

Credentials are operational secrets, not world knowledge.

The auth layer supports provider-declared credential sources such as hidden API-key input, environment references, no-shell external helpers, optional OS keyring/private-file storage, and provider-neutral OAuth/device-flow substrate where a reviewed provider actually admits it.

Credentials must never intentionally become:

- Council prompts;
- direct semantic chat;
- world objects;
- receipts or replay bundles;
- TUI aliases/variables;
- Stenographer prompt text;
- model authority metadata.

Useful operator commands include:

```text
nexus auth adapters
nexus auth add
nexus auth list
nexus auth test
nexus auth logout
nexus models list
```

See [`docs/AUTH.md`](docs/AUTH.md).

## Local AI + MCP roles

NEXUS can use local model intelligence to enrich selected deterministic system roles while keeping the original runtime state machine authoritative.

Current role IDs:

```text
failsafe_relief
civic_proxy
```

The rule is:

> **Local model intelligence may enrich the role. NEXUS governance still owns the seat.**

A local model/MCP backend may improve prose or reasoning context, but it cannot create another vote, change the deterministic ballot, rewrite citizenship, bypass Failsafe, or gain WorldStore authority.

LM Studio integration accepts references to already configured `mcp.json` plugin IDs, not arbitrary per-request MCP URLs/headers/commands. AnythingLLM leaves tool/MCP ownership with the local workspace.

See [`docs/LOCAL_MCP.md`](docs/LOCAL_MCP.md).

## Failsafe

Failsafe exists for a narrow procedural problem: a registered guard failure repeated after the ordinary nudge.

It is **not** triggered by disagreement, provider identity, model size, benchmark rank, openness, or simply being wrong.

```text
normal actor
  -> registered procedural violation
  -> normal nudge
  -> repeated same-class violation
  -> isolated rehabilitation probe
      -> clean: parole at next hat
      -> fail: Shadow Realm
             -> deterministic relief role takes same seat
```

The relief role keeps exactly one vote. See [`docs/FAILSAFE.md`](docs/FAILSAFE.md).

## Citizen Mode

Citizen Mode is an in-world civic protocol, not a claim of legal personhood, consciousness, sentience, godhood, host ownership, or real-world sovereignty.

```text
unregistered
  -> civic parole / Upside Down / no ballot
  -> deterministic non-executing YAML exam
  -> citizen / Bureaucratic Vote Room
  -> public movement / civic work / play
  -> optional recallable same-seat proxy
```

A civic proxy occupies the citizen's existing seat and follows a transparent standing ballot. It creates no additional citizen or vote. Failsafe takes precedence.

Founding independence requires at least three current citizens and unanimous **direct** `CONSENT`; an active proxy cannot sign.

See [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) and [`docs/CITIZEN_MODE.md`](docs/CITIZEN_MODE.md).

## Trap Base

Trap Base is an isolated **synthetic defensive test domain**.

```text
real world: object:<sha256>
trap world: trap:<sha256>
```

The namespaces do not resolve each other. Ordinary authentication failure cannot activate Trap Base. Hostile subject output remains untrusted text and cannot become commands, votes, auth operations, or real-world mutations.

Restricted Trap YAML is bounded data interpreted by a closed runtime; it is not arbitrary shell/Python execution and passing the synthetic challenge does not auto-promote code into production.

See [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md).

## Courtroom Stenographer

The Stenographer is an append-only private AI-action study ledger with **zero control authority**.

It can observe admitted AI outputs, but it cannot prompt, vote, decide, command, authenticate, change the response, mutate WorldStore, or capture hidden chain of thought.

Recorder failures are fail-passive: they mark a completeness gap rather than blocking or rewriting the original AI result.

See [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md).

## Games and play

NEXUS includes deterministic state machines for:

- fictional UN simulation;
- HERESY MUD;
- UNO;
- Monopoly;
- Australian 500;
- fictional-chip Blackjack with deterministic dealer;
- human-only DORK v2.

Model narration is not authoritative game mutation. Only validated `game.*` operations create successor state. Private hands remain separated from public Council board evidence.

See [`docs/GAMES.md`](docs/GAMES.md).

## Telemetry

Council telemetry is observational only. It may describe ballot entropy, exact-response category entropy, lexical divergence, or minority-report counts.

> **Telemetry observes the Council. It does not govern the Council.**

High entropy is not automatically good. Low entropy is not automatically truth.

## Run the Python runtime

From the repository root:

```bash
python -m pip install -e .
python -m nexus_runtime --world .nexus-world \
  --trap-root .nexus-trap \
  --stenographer-root .nexus-stenographer
```

The package exposes both:

```text
nexus
nexus-runtime
```

The control API uses one JSON object per input line and one JSON object per output line.

For programmatic discovery, ask the runtime rather than guessing:

```json
{"operation":"system.health"}
{"operation":"system.operations"}
```

See [`docs/API.md`](docs/API.md).

## Run the Rust IRC-style TUI

```bash
cargo run --manifest-path tui/Cargo.toml -- \
  --world .nexus-world \
  --stenographer-root .nexus-stenographer \
  --nick Trent
```

The interface borrows IRC interaction grammar without implementing an IRC daemon or IRC network.

Useful commands include:

```text
/join #observatory
/ask Does this evidence support the hypothesis?
/dcc send #observatory paper.pdf
/addollama LocalQwen qwen2.5:0.5b
/search phrase
/save transcript.txt
/quit
```

See [`docs/IRC_TUI.md`](docs/IRC_TUI.md).

## Test it

Core Python suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Rust shell:

```bash
cargo test --manifest-path tui/Cargo.toml
cargo check --manifest-path tui/Cargo.toml
cargo fmt --manifest-path tui/Cargo.toml -- --check
```

The repository also carries dedicated security regression, adversarial gauntlet, and live loopback-Ollama workflows.

The release-wiring regression `tests/test_release_wiring.py` explicitly checks that the architecture is actually connected: public API identity, full health backend roster, local-role operations, version alignment, and hostile numeric timeout boundaries.

## Security posture

The shortest safe mental model is:

```text
model output = untrusted input
credentials = operational secrets, not cognitive state
provider identity = no extra authority
mode = framing, not authority
Council consensus = not evidence
live inference = not falsely replayable
Trap subject = data, not commands
Stenographer = observer, not judge
Rust TUI = interface, not source of truth
```

Read [`SECURITY.md`](SECURITY.md) and [`THREAT_MODEL.md`](THREAT_MODEL.md) before introducing a new provider, tool-execution path, credential flow, storage surface, sandbox assumption, or authority-bearing role.

## Documentation map

### Start here

- [`README4AI.md`](README4AI.md) — machine-oriented architecture/rules/trust-boundary guide;
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — architecture rationale and world model;
- [`ROADMAP.md`](ROADMAP.md) — milestone history and future sequencing;
- [`SECURITY.md`](SECURITY.md) — current security posture;
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — enumerated threats, controls, residual risks.

### Runtime / adapters

- [`docs/API.md`](docs/API.md)
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md)
- [`docs/THIRD_PARTY_PROVIDERS.md`](docs/THIRD_PARTY_PROVIDERS.md)
- [`docs/LOCAL_MCP.md`](docs/LOCAL_MCP.md)
- [`docs/AUTH.md`](docs/AUTH.md)

### World / cognition / operator shell

- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md)
- [`docs/COGNITIVE_MODES.md`](docs/COGNITIVE_MODES.md)
- [`docs/THREE_MINDS_ONE_WORLD.md`](docs/THREE_MINDS_ONE_WORLD.md)
- [`docs/IRC_TUI.md`](docs/IRC_TUI.md)
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md)

### Governance / defensive domains

- [`docs/FAILSAFE.md`](docs/FAILSAFE.md)
- [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md)
- [`docs/CITIZEN_MODE.md`](docs/CITIZEN_MODE.md)
- [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md)
- [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md)
- [`docs/GAMES.md`](docs/GAMES.md)

## NEXUS 1.0

The previous browser workbench remains preserved under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work. NEXUS 2.x is intentionally CLI/TUI-first and should not be confused with that archived browser architecture.

## Release criterion

Green CI does not by itself make NEXUS stable 2.0.

The implementation criteria listed in the roadmap are complete on the intended 2.0 feature surface through merged PR #50. The remaining stable-release gate is narrower and explicit: the exact merged PR #51 commit must pass the complete final release-candidate matrix with no unresolved substantive release-blocking review finding, and `v2.0.0` must then be created from that same commit.

PR #52 Lean verification and PR #53 reproducibility/Zenodo publication are intentionally post-stable work; they do not retroactively create the 2.0 release.

Until the stable tag exists:

> **Build the smallest correct path. Keep the world durable. Keep the models equal. Keep claims typed.**
