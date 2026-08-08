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
- a lightweight Equality Guard;
- deterministic mock actors;
- a hardened loopback Ollama actor tested with real local models;
- **World Modes**;
- a deterministic named-region **World Geometry**;
- a first **Rust operator TUI** using an old-school IRC interface.

Current posture:

```text
protocol: nexus/0.4
runtime version: 2.0.0-alpha5
control transport: JSONL over stdio
operator shell: Rust IRC-style TUI
actor backends: mock + explicit loopback Ollama
world modes: analytical / historical / cultural / meme_casual
geometry: named-regions-v1
remote/cloud providers: deferred
provider authentication: deferred
world persistence: optional local canonical JSON files
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
            +----------+----------+
                       |
                  JSONL / stdio
                       |
                       v
            +---------------------+
            |   PYTHON RUNTIME    |
            | world + Council     |
            | modes + geometry    |
            | Secret Scrubber     |
            +----------+----------+
                       |
               CouncilActor seam
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
      Mock        local Ollama   future actors
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

The Rust TUI is an operator shell, not a new authority layer. Council rules, evidence identity, secret handling, world objects, voting and verification remain runtime-owned.

## World Modes

NEXUS should not be all work and no play.

| Mode | Region / room | Purpose |
|---|---|---|
| `analytical` | Observatory / `#observatory` | evidence-first technical reasoning |
| `historical` | Archive / `#archive` | chronology, source context, change over time |
| `cultural` | Agora / `#agora` | norms, ambiguity, social meaning, cultural comparison |
| `meme_casual` | Commons / `#commons` | playful, irreverent, meme-aware interaction |

The important invariant is:

> **The mode can change the vibe. It cannot change the vote.**

Modes may affect framing, context and tone. They do **not** change evidence status, verification, Council thresholds, secret handling, the Equality Guard, or `vote_weight = 1`.

See [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md).

## First World Geometry

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

This is an **operational topology**, not a claim that cognition, culture, history or humor literally occupies Euclidean space.

The geometry gives NEXUS explicit named regions, deterministic integer coordinates, symmetric adjacency, hop distance, and Council/world placement. Every Council creates a content-addressed `world_presence` object binding its mode, region, members and question into lineage.

## Old-school IRC-style Rust TUI

Alpha5 deliberately borrows the interface grammar of old IRC clients without implementing IRC networking.

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
cargo run --manifest-path tui/Cargo.toml -- --world .nexus-world --nick Trent
```

Normal public text is treated as a Council question. Council phases and ballots stream into chronological text scrollback so results are easy to copy, quote and archive.

Useful commands:

```text
/join #agora
/topic Cultural interpretation of X
/ask Compare these two readings.
/me *slapped Grok with a large trout*
/who

/addmock Delta skeptical
/addollama LocalQwen qwen2.5:0.5b
/kick Delta

/search phrase
/save transcript.txt
/quit
```

See [`docs/IRC_TUI.md`](docs/IRC_TUI.md).

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

This is **not** the future provider-auth system. OpenAI, Claude, Gemini, Grok cloud APIs, OAuth/API keys, generic remote endpoints and provider discovery remain deferred.

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

Run the JSONL stdio runtime directly:

```bash
python -m nexus_runtime --world .nexus-world
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
receipt.verify
actor.chat
council.run
```

`council.run` can instantiate deterministic mock actors and explicit loopback-local Ollama actors. Remote actor configuration remains rejected.

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

The coordinator implements blind same-phase collection, ballot commitments, exact two-thirds consensus arithmetic, and durable minority reports. See [`COUNCIL.md`](COUNCIL.md).

## Equality Guard

NEXUS includes a deliberately light equality guard. It only stops explicit attempts to turn identity or prestige into procedural authority.

That includes provider prestige, corporate affiliation, frontier/commercial status, benchmark prestige, compute claims, model size, and parameter count.

> **None of that, mister. Argue from the evidence like everybody else.**

The guard remains active in every World Mode, including Meme/Casual.

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

The scrubber applies to world/document creation and direct `actor.chat` messages as well as Council questions. This remains defence in depth, not perfect DLP. See [`SECURITY.md`](SECURITY.md).

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
```

The operator-only direct `actor.chat` path is deliberately marked non-Council and does not alter Council authority.

## Next: Council information telemetry

The next planned observation layer is **Council-response entropy**:

```text
near-identical independent responses
        -> lower response entropy
        -> lower informational diversity

divergent independent hypotheses
        -> higher response entropy
        -> higher informational diversity
```

Entropy will be telemetry, not truth, quality, confidence, reputation, or vote weight.

See [`ROADMAP.md`](ROADMAP.md).

## What is deliberately not here yet

This alpha does **not** add:

- OpenAI cloud integration;
- Anthropic / Claude cloud integration;
- Google / Gemini cloud integration;
- xAI / Grok cloud integration;
- provider API keys or OAuth;
- generic remote model endpoints;
- IRC networking or an IRC daemon;
- real DCC P2P sockets;
- mIRC remote/event scripting;
- arbitrary model-generated code execution;
- QEC-grade proof/replay for live inference;
- performance optimization or concurrent Council scheduling.

Remote provider auth is intentionally postponed until the shared-world, operator, telemetry, instrument and persistence contracts are more mature.

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — security, credential, and secret-scrubbing boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — executable adapter threat model
- [`docs/API.md`](docs/API.md) — JSONL control API
- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — World Modes and named-region geometry
- [`docs/IRC_TUI.md`](docs/IRC_TUI.md) — implemented Rust IRC-style operator interface
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — broader operator-shell direction
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — provider-neutral actor/adapter contract
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](`LICENSE`) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
