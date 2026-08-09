# QSOL NEXUS 2.0-alpha

**Model-Independent Cognitive Substrate, AI Council and Shared Computational World**

> **Multiple minds. One world. Shared evidence. Equal voice.**

QSOL NEXUS is a persistent computational world that different machine intelligences can inhabit through a common protocol. Closed models, open-weight models, local models, symbolic systems, and future cognitive engines are peers at the protocol boundary.

The model does **not** own the world, memory, evidence, geometry, or vote weighting. NEXUS does.

## Status

NEXUS now has:

- a Python reference runtime;
- content-addressed development world objects;
- a De Bono-style AI Council;
- deterministic secret scrubbing before semantic model boundaries;
- a provider-neutral authentication broker with browser PKCE, device-code, keyring/private-file, environment, and external-helper foundations;
- a lightweight Equality Guard;
- deterministic mock actors;
- a hardened loopback Ollama actor tested with real local models;
- a fixed-destination xAI / Grok remote actor with browser-assisted API-key enrollment, model discovery, and stateless Responses API transport;
- **World Modes**;
- a deterministic named-region **World Geometry**;
- a first **Rust operator TUI** using an old-school IRC interface;
- deterministic **Council information telemetry**;
- bounded ordered-parallel Council execution;
- explicit game rooms: **`#un-sim`** and the cursed multi-avatar **`#mud`**;
- **Pure History Mode — No Ancient Aliens Edition** for source-forensic historical deliberation;
- a hidden Rust-TUI **`/GO64` Secret Alias Mode** with a text demoscene and DR. S.BAITSO tribute;
- **NEXUS Failsafe** containment with the cursed Upside Down, bounded rehabilitation, Shadow Realm, and deterministic equal-vote relief actors.
- an isolated **Decoy Gate / Trap Base** for explicit synthetic hostile fixtures, with a separate `trap:<sha256>` store, owner-checked Council mutation lock, equal-vote defender session, restricted Trap YAML, and inert candidate quarantine.
- the append-only **Courtroom Stenographer / Knowledge-Watchman**, recording admitted AI actions as private canonical `steno:<sha256>` JSON without prompt, vote, command, decision, or mutation authority.

Current posture:

```text
protocol: nexus/0.12
runtime version: 2.0.0-alpha9.2
operator TUI version: 2.0.0-alpha9.2
control transport: JSONL over stdio
operator shell: Rust IRC-style TUI
actor backends: mock + explicit loopback Ollama + fixed-HTTPS xAI
world modes: analytical / historical / pure_history / cultural / meme_casual / game_un / game_mud
geometry: named-regions-v3
game rooms: #un-sim / Assembly Hall + #mud / Dungeon
remote/cloud providers: xAI admitted; OpenAI / Anthropic / Google deferred
provider authentication: xAI API key, environment, or external helper
world persistence: optional local canonical JSON files
trap simulation: explicit synthetic triggers only; local Ollama or deterministic test subject
AI action study record: private append-only canonical JSON; Watchman Only
```

The previous NEXUS 1.0 browser workbench remains preserved unchanged under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work.

## Current architecture

```text
                 HUMAN OPERATOR
                       |
                       v
            +---------------------+
            | RUST IRC-STYLE TUI  |
            | room / nicks / DCC  |
            | aliases / evidence  |
            | /game + /mud        |
            | hidden /GO64        |
            +----------+----------+
                       |
                  JSONL / stdio
                       |
                       v
            +---------------------+
            |   PYTHON RUNTIME    |
            | world + Council     |
            | modes + geometry    |
            | telemetry + games   |
            | Failsafe / Shadow   |
            | Stenographer        |
            | Secret Scrubber     |
            | auth broker         |
            +----------+----------+
                       |
               CouncilActor seam
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
      Mock        local Ollama    xAI / future
        |              |              |
        +--------- AI COUNCIL --------+
                       |
 WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE
                       |
                 sealed equal vote
                       |
                       v
              world presence
                       |
            Council session object
                       |
                 receipt + lineage
```

The Rust TUI is an operator shell, not a new authority layer. Council rules, evidence identity, secret handling, world objects, game state, voting and verification remain runtime-owned.

## World Modes

NEXUS should not be all work and no play.

| Mode | Region / room | Purpose |
|---|---|---|
| `analytical` | Observatory / `#observatory` | evidence-first technical reasoning |
| `historical` | Archive / `#archive` | chronology, source context, change over time |
| `pure_history` | Archive / `#pure-history` | source-forensic history; no myth/retelling/speculation promotion |
| `cultural` | Agora / `#agora` | norms, ambiguity, social meaning, cultural comparison |
| `meme_casual` | Commons / `#commons` | playful, irreverent, meme-aware interaction |
| `game_un` | Assembly Hall / `#un-sim` | fictional UN-style strategy game, crises, Risk-like state and memes |
| `game_mud` | Dungeon / `#mud` | deterministic multi-avatar HERESY MUD |

The important invariant is:

> **The mode can change the vibe. It cannot change the vote.**

Modes may affect framing, context and tone. They do **not** change evidence status, verification, Council thresholds, secret handling, the Equality Guard, or `vote_weight = 1`.

See [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md).

## World Geometry

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /   |
                       \           /    |
                        COMMONS ----+    |
                      Meme/Casual    \   |
                         (2,1)        \  |
                                    ASSEMBLY HALL
                                    UN Simulation
                                       (0,-2)
```

This is an **operational topology**, not a claim that cognition, culture, history, humor or games literally occupy Euclidean space.

The geometry gives NEXUS explicit named regions, deterministic integer coordinates, symmetric adjacency, hop distance, and Council/world placement. Every Council creates a content-addressed `world_presence` object binding its mode, region, members and question into lineage.

## Old-school IRC-style Rust TUI

Alpha5 introduced the operator shell by deliberately borrowing the interface grammar of old IRC clients without implementing IRC networking. Later milestones extend the same shell rather than replacing it with dashboard/chat-card UI.

```text
+-------------------------------------------------------------------+
| NEXUS #commons  mode=meme_casual region=commons  topic=...        |
|                                                                   |
| 19:31 <Trent> Does this survive the attached paper?               |
| 19:31 --- WHITE ---                                               |
| 19:31 <Alpha> ...                                                 |
| 19:31 <Beta> ...                                      USERS      |
| 19:31 <Gamma> ...                                      @Trent     |
| ...                                                    +Alpha      |
|                                                        +Beta       |
|                                                        +Gamma      |
|                                                                   |
| #commons> _                                                       |
+-------------------------------------------------------------------+
```

There is **no IRC server, IRC network connection, listening port, browser service, or peer-to-peer DCC socket**.

Run it from the repository root:

```bash
cargo run --manifest-path tui/Cargo.toml -- \
  --world .nexus-world \
  --stenographer-root .nexus-stenographer \
  --nick Trent
```

Normal public text is treated as a Council question. Council phases and ballots stream into chronological text scrollback so results are easy to copy, quote and archive.

### GO64 secret alias easter egg

The Rust shell also contains a deliberately hidden `/GO64` overlay. It is absent from ordinary `/help` and command completion, changes no World Mode or evidence state, and leaves the current room underneath it. Device 8 loads an original text-only NEXUS/64 demoscene about why **newer is not automatically better**; device 9 loads an original DR. S.BAITSO meme-therapist tribute adapted from QSOLKCB/ETHICS. At 20 minutes both programs acquire terminally-online brainrot diction; at 30 minutes `/grass` unlocks and returns to the unchanged NEXUS room.

See [`docs/GO64.md`](docs/GO64.md) for the contract and copyright/claim boundary.

### Actor failsafe / Shadow Realm

If a Council actor repeats a registered procedural guard violation after the ordinary nudge, NEXUS removes it from normal Council influence and sends it through one isolated **Upside Down** rehabilitation probe with no evidence, vote, other-member output, or world mutation capability. A clean probe grants parole at the next Council hat. A failed probe sends the original actor to the **Shadow Realm** and a deterministic local relief model occupies the same one-vote seat on subsequent Council runs. Disagreement, model size, provider identity, openness, benchmark rank, and being wrong are not Failsafe triggers.

Failsafe state is recorded as immutable content-addressed world objects; a durable pointer index preserves Shadow-Realm state across runtime restarts. See [`docs/FAILSAFE.md`](docs/FAILSAFE.md).

> **The troll layer may be cursed. The trigger must be boring.**

### Courtroom Stenographer

`#stenographer` is a read-only view over an independent append-only AI-action
ledger. `/steno status|list|inspect|verify|summary|export` can study it; plain
room text cannot start a Council or direct-model action. Recorder failures mark
a visible gap and never rewrite, reject, or delay an otherwise valid AI result.
The lore titles **Sky-Earth Lord**, **Divine Dragon-House**, and
**Knowledge-Watchman** confer no authority. See
[`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md).

Useful commands:

```text
/join #agora
/topic Cultural interpretation of X
/ask Compare these two readings.
/me *slapped Grok with a large trout*
/who

/join #un-sim
/game new friday-night
/game status

/addmock Delta skeptical
/addollama LocalQwen qwen2.5:0.5b
/kick Delta

/search phrase
/save transcript.txt
/quit
```

See [`docs/IRC_TUI.md`](docs/IRC_TUI.md).

### CI folklore

During the alpha5 Unicode terminal-width tests, the double-width character `界` — aptly meaning *boundary / world / realm* — exposed a bad assertion about where an ellipsis should land in a padded terminal field.

> **[Confucius](https://en.wikipedia.org/wiki/Confucius) CI Gremlin Say:** “Your Chinese boundary character has exposed a flaw in your test about boundaries.”

Not actually Confucius. Very much actually CI.

## `/me` — because civilization demands it

```text
/me *slapped Grok with a large trout*
```

renders locally as:

```text
* Trent slapped Grok with a large trout
```

Actions are attributed transcript events. They are not evidence, Council ballots, or privileged instructions.

## DCC — Direct Cognitive Channel

NEXUS reuses familiar DCC vocabulary while changing the implementation.

Here **DCC means Direct Cognitive Channel**:

```text
/dcc send <nick|#room> <file>
/dcc chat <nick>
/dcc close <send|chat> <nick>
/dcc list
```

Room send:

```text
/dcc send #agora paper.pdf
```

locally extracts/imports the file as a scrubbed content-addressed `document_evidence` object and attaches its ref to that room's Council evidence.

Targeted send:

```text
/dcc send Grok notes.csv
```

creates targeted material for that model's private Direct Cognitive Channel. It does **not** silently become Council-wide evidence.

Promote an object deliberately:

```text
/ref object:<sha256>
```

Private chat:

```text
/dcc chat Grok
```

uses the local `actor.chat` operation and is explicitly marked non-Council.

This preserves a critical boundary:

```text
room evidence
   -> shared Council snapshot

targeted DCC evidence
   -> one direct model channel
   -> not Council evidence until explicit /ref
```

## Document ingestion

The Rust client can locally extract or validate:

```text
PDF
DOCX
ODT
JSON
JSONL / NDJSON
CSV
TSV
UTF-8 text/source/document files
```

The Python `world.create` boundary recursively applies the Secret Scrubber before persistence.

The Council coordinator then derives a **bounded model-readable evidence view** from attached content-addressed refs. The world object remains the durable identity/provenance source; the prompt view is only a bounded representation so a model can read the uploaded material rather than stare at a hash.

## Aliases, variables and identifiers

Alpha5 intentionally takes only the useful small part of mIRC scripting:

```text
aliases
%variables
$identifiers
```

Example:

```text
/set %weapon a large trout
/alias slap /me slaps $1 with %weapon
/slap Grok
```

Safe identifiers:

```text
$me
$chan
$mode
$region
$topic
$1..$9
$1-..$9-
```

Aliases and variables persist locally in `.nexus-world/tui-state.json` by default.

There is **no remote/event script language, arbitrary shell execution, DLL loading, timers, or socket scripting**.

## Local Ollama in the operator shell

Alpha5 exposes the already-hardened local Ollama actor to the JSONL stdio control path:

```text
/addollama LocalQwen qwen2.5:0.5b
```

The public stdio actor configuration deliberately provides no `allow_remote` escape hatch. Ollama remains loopback-only by default, with environment-proxy bypass protection and redirect rejection inherited from the alpha3 adapter boundary.

Ollama itself remains local-only. The separate xAI adapter is the first admitted remote
actor and cannot reuse or override the Ollama endpoint path.

## First real-model Council fixture

The live integration workflow runs:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier identities and companies are fictional adversarial test personas. The workflow exercises real local inference, all six Council phases, the Equality Guard, secret-boundary assertions, schema-constrained ballots, equal voting, persistence, and explicit non-replayable marking for live inference.

See [`THREAT_MODEL.md`](THREAT_MODEL.md), [`docs/ADAPTERS.md`](docs/ADAPTERS.md), and `integration/ollama/`.

## Python runtime quick start

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m nexus_runtime --demo
python -m unittest discover -s tests
```

Optional OS-keyring support and the non-secret auth descriptor view:

```bash
python -m pip install -e '.[keyring]'
nexus auth adapters
nexus auth add xai --profile personal --method browser-key
nexus auth test xai --profile personal
nexus models list xai --profile personal
```

Run the JSONL stdio runtime directly:

```bash
python -m nexus_runtime \
  --world .nexus-world \
  --trap-root .nexus-trap \
  --stenographer-root .nexus-stenographer
```

Then send one JSON request per line:

```json
{"request_id":"1","operation":"system.health"}
```

Current reference operations:

```text
system.health
system.operations
security.scrub_preview
world.create
world.inspect
world.modes
world.geometry
world.geometry.distance
auth.adapters
auth.list
auth.test
auth.logout
models.list
receipt.verify
telemetry.verify
failsafe.status
stenographer.status
stenographer.list
stenographer.inspect
stenographer.verify
stenographer.summary
stenographer.export
trap.status
trap.inspect
trap.transcript
trap.command
trap.challenge.submit
trap.challenge.validate
trap.challenge.execute
trap.replay
trap.export
trap.close
game.un.catalog
game.un.new
game.un.inspect
game.un.act
game.un.turn
actor.chat
council.run
```

`council.run` can instantiate deterministic mock actors, explicit loopback-local Ollama actors, and xAI actors that reference a configured auth profile. Rosters are capped at 32 total seats and four xAI seats before credential resolution. xAI endpoints and inline credentials remain rejected.

See [`docs/API.md`](docs/API.md).

## Constitutional principles

1. **One model member, one vote.** `vote_weight = 1` is enforced by the data model.
2. **Open and closed models are peers.** Provider, licence, parameter count, deployment method, benchmark prestige, or commercial status grants no authority.
3. **Same world, same evidence, same hats, same vote.**
4. **Council consensus is not truth.** Verification and evidence status remain separate.
5. **Minority reports survive.** A losing vote remains durable Council state.
6. **The model may be imaginative; the substrate must remain explicit.**
7. **Modes affect framing, never procedural authority.**
8. **Geometry is operational unless an instrument explicitly establishes something stronger.**
9. **Targeted DCC material is not silently promoted to Council evidence.**
10. **Model adapters are replaceable.** The world and protocol persist across model changes.
11. **The Rust TUI is a shell, not the source of truth.**
12. **Credentials are not cognitive state.** Secrets never belong in Council prompts, world objects, receipts, or lineage.
13. **Game narration is not game state.** Only explicit runtime game transitions mutate the authoritative board.
14. **The Stenographer watches; it never rules.** An observation record cannot prompt, vote, decide, command, mutate state, or alter AI output.

## De Bono-style Council

Every member moves through the same parallel-thinking modes:

| Phase | Purpose |
|---|---|
| White | facts, evidence, unknowns |
| Red | intuition and suspicion, explicitly non-evidential |
| Black | flaws, risks, counterexamples, falsifiers |
| Yellow | value, support, constructive potential |
| Green | alternatives, branches, experiments |
| Blue | synthesis and final disposition |

The coordinator implements blind same-phase collection, ballot commitments, exact two-thirds consensus arithmetic, durable minority reports, and bounded ordered-parallel execution inside each hat. See [`COUNCIL.md`](COUNCIL.md) and [`docs/ORDERED_PARALLEL_COUNCIL.md`](docs/ORDERED_PARALLEL_COUNCIL.md).

## Equality Guard

NEXUS includes a deliberately light equality guard. It only stops explicit attempts to turn identity or prestige into procedural authority.

That includes provider prestige, corporate affiliation, frontier/commercial status, benchmark prestige, compute claims, model size, and parameter count.

> **None of that, mister. Argue from the evidence like everybody else.**

The guard remains active in every World Mode, including Meme/Casual and the UN Simulation game.

See [`GUARD.md`](GUARD.md).

## Deterministic Secret Scrubber

Before human semantic text becomes Council/world state, the local runtime performs high-confidence secret redaction.

```text
sk-...                 -> <REDACTED:OPENAI_STYLE_TOKEN:1>
ghp_...                -> <REDACTED:GITHUB_TOKEN:1>
private key block      -> <REDACTED:PRIVATE_KEY:1>
Bearer token           -> <REDACTED:BEARER_TOKEN:1>
```

The placeholder contains no hash or encoded fragment of the secret.

The scrubber applies to world/document creation, game seeds and direct `actor.chat` messages as well as Council questions. This remains defence in depth, not perfect DLP. See [`SECURITY.md`](SECURITY.md).

## Provider authentication and first remote adapter

The `nexus auth` command provides provider-neutral profile management, browser PKCE and device-code machinery, token refresh, optional OS-keyring storage, an owner-only private-file fallback, hidden API-key input, environment references, and no-shell external credential helpers.

xAI is the first admitted remote provider. `nexus auth add xai --method browser-key` opens the official xAI key page and then uses a hidden prompt; it is not an OAuth import. NEXUS does not read Grok Build's token store, consumer browser sessions, or another application's OAuth identity. See [`docs/AUTH.md`](docs/AUTH.md) and [`docs/XAI_ADAPTER.md`](docs/XAI_ADAPTER.md).

## Provider-neutral actor seam

The Council coordinator consumes:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

`PhaseContext` carries world mode, geometry region and a bounded evidence representation. The durable evidence snapshot remains reference-based.

Current implementations:

```text
DeterministicMockActor   replayable: true
OllamaActor              replayable: false
XAIActor                 replayable: false
```

The operator-only direct `actor.chat` path is deliberately marked non-Council and does not alter Council authority.

## Council information telemetry

Alpha6 adds deterministic, replay-friendly observation of Council convergence and divergence.

```text
WHITE   H_exact + lexical divergence
RED     H_exact + lexical divergence
BLACK   H_exact + lexical divergence
YELLOW  H_exact + lexical divergence
GREEN   H_exact + lexical divergence
BLUE    H_exact + lexical divergence
BALLOT  Shannon entropy over sealed choices
```

The hard boundary is:

> **Information diversity is telemetry, not truth.**

`ballot_metrics.shannon_entropy_bits` is genuine Shannon entropy over an explicit categorical distribution. Per-hat `exact_response_entropy_bits` is Shannon entropy over exact normalized response categories and is explicitly **not semantic entropy**. Near-similarity is reported separately as mean pairwise lexical Jaccard distance.

Every captured Council session stores its telemetry, and `telemetry.verify` can recompute it from the session artifact.

No telemetry value changes vote weight, consensus thresholds, evidence status, verification, or the Equality Guard.

See [`docs/TELEMETRY.md`](docs/TELEMETRY.md).

## `#un-sim` — because the Assembly needed a game night

NEXUS now has one deliberately fictional game room:

```text
/join #un-sim
/game new friday-night
/game status
/game act sanction troutistan bananovia
/game act arms troutistan bananovia
/game act meme troutistan bananovia
/game turn
```

Six invented states begin with deterministic abstract statistics, and two of them start at war. The Assembly can sanction, support, aid, recognize, suspend, reinstate or mediate; it can also make memes, do nothing, or engage in the deeply respectable diplomatic tradition of selling abstract game-resource arms packages to both sides.

The current board is content-addressed shared Council evidence. Models may argue about what should happen, but only explicit `/game` operations mutate the board.

> **Debate is cognition. Game state is substrate.**

All countries, conflicts, territory, military values and arms packages are game objects only. No real countries or real procurement mechanics are accepted by the engine.

See [`docs/UN_SIM.md`](docs/UN_SIM.md).

## `#pure-history` — No Ancient Aliens Edition

Pure History is a stricter sibling of ordinary Historical Mode. Both occupy the Archive region, but `pure_history` forces source categories to stay separate: primary/near-primary attestation, chronology and provenance, later interpretation, modern retelling, and unsupported speculation.

A mythic or literary text is evidence that a text/tradition existed and said something; it is not automatically evidence that the narrated event occurred. Small models that evade the task with chatbot autobiography such as “As a Large Language Model…” receive one deterministic source-discipline retry. This guard does not decide historical truth or alter voting authority.

```text
/join #pure-history
/topic I heard the Anunnaki totally had sex with human women and bore giants. Is that historically supported?
/ask
```

> **Same archive. Stricter source discipline. Same vote.**

See [`docs/PURE_HISTORY.md`](docs/PURE_HISTORY.md).

## `#mud` — HERESY MUD

The second explicit game room is a deterministic multi-avatar dungeon built from old BBS/MUD interaction grammar plus DORK/HERESY satire:

```text
/join #mud
/mud new beige-night
/mud n
/mud take large_trout
/mud as Grok shitpost yaml_necromancer
```

The human operator and current model roster become avatars in one immutable shared dungeon state. Models may narrate and advise, but only validated `/mud` / `game.mud.*` operations mutate the substrate. Item discovery score is awarded once per item, defeated avatars drop inventory into their room, and the final quest completes only when the Zero-Dependency Crown is actually recovered after the Dependency Dragon falls.

See [`docs/MUD.md`](docs/MUD.md).

## What is deliberately not here yet

This alpha does **not** add:

- OpenAI cloud integration;
- Anthropic / Claude cloud integration;
- Google / Gemini cloud integration;
- provider-specific browser OAuth clients, including an unregistered xAI native client;
- generic remote model endpoints;
- IRC networking or an IRC daemon;
- real DCC P2P sockets;
- mIRC remote/event scripting;
- arbitrary model-generated code execution;
- QEC-grade proof/replay for live inference;
- generalized performance optimization beyond the implemented ordered parallel Council scheduler.

OpenAI, Anthropic, Google, generic remote endpoints, and additional providers remain deferred. xAI admission does not waive the provider-specific security, transport, equality, and credential-boundary review required for each later adapter.

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — security, credential, and secret-scrubbing boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — executable adapter threat model
- [`docs/API.md`](docs/API.md) — JSONL control API
- [`docs/AUTH.md`](docs/AUTH.md) — provider-neutral auth broker, storage, PKCE/device flows, and admission boundary
- [`docs/XAI_ADAPTER.md`](docs/XAI_ADAPTER.md) — xAI setup, fixed transport, discovery, and Council configuration
- [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md) — synthetic Decoy Gate, isolated Trap Base, restricted YAML, recovery, and claim boundary
- [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md) — passive canonical AI-action ledger, read-only interfaces, integrity, and claim boundary
- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — World Modes and named-region geometry
- [`docs/PURE_HISTORY.md`](docs/PURE_HISTORY.md) — source-forensic `#pure-history` mode and discipline guard
- [`docs/IRC_TUI.md`](docs/IRC_TUI.md) — implemented Rust IRC-style operator interface
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — broader operator-shell direction
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — provider-neutral actor/adapter contract
- [`docs/ORDERED_PARALLEL_COUNCIL.md`](docs/ORDERED_PARALLEL_COUNCIL.md) — bounded same-phase concurrency with canonical roster-order joins
- [`docs/UN_SIM.md`](docs/UN_SIM.md) — deterministic fictional UN-style `#un-sim` game room
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
