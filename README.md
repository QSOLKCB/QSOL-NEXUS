# QSOL NEXUS 2.0-alpha

**Model-Independent Cognitive Substrate and AI Council Runtime**

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
- a real loopback Ollama actor tested with two live local models;
- **World Modes**;
- a first deterministic **World Geometry**.

Current posture:

```text
runtime: Python reference implementation
protocol: nexus/0.3
runtime version: 2.0.0-alpha4
transport: JSONL over stdio
JSONL council.run: mock actors only
actor backends: mock + local Ollama
world modes: analytical / historical / cultural / meme_casual
geometry: named-regions-v1
Ollama network scope: loopback by default
remote/cloud providers: deferred
provider authentication: deferred
world persistence: optional local canonical JSON files
Rust TUI: planned, not implemented
```

The previous NEXUS 1.0 browser workbench remains preserved unchanged under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work.

## Current architecture

```text
                 HUMAN OPERATOR
                       |
                semantic question
                       v
            +---------------------+
            |  LOCAL SECRET       |
            |      SCRUBBER       |
            +----------+----------+
                       |
                 scrubbed text
                       v
            +---------------------+
            |   PYTHON RUNTIME    |
            | world + Council     |
            | modes + geometry    |
            +----------+----------+
                       |
               CouncilActor seam
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
      Mock       Ollama Alpha    Ollama Beta
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

## World Modes

NEXUS should not be all work and no play.

Alpha4 introduces four modes:

| Mode | Region | Purpose |
|---|---|---|
| `analytical` | Observatory | evidence-first technical reasoning |
| `historical` | Archive | chronology, source context, change over time |
| `cultural` | Agora | norms, ambiguity, social meaning, cultural comparison |
| `meme_casual` | Commons | playful, irreverent, meme-aware interaction |

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

The geometry gives NEXUS explicit:

- named regions;
- deterministic integer coordinates;
- symmetric adjacency;
- hop distance;
- Council/world placement.

Every Council creates a content-addressed `world_presence` object binding its mode, region, members and question into lineage.

## First real-model Council fixture

The alpha3 integration test runs:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The **Frontier Alpha**, **Frontier Beta**, **ExampleCorp**, and **AnotherCorp** identities are fictional adversarial test personas.

The test exercises:

- two genuinely running local models;
- White → Red → Black → Yellow → Green → Blue;
- blind same-phase collection;
- provider/model-size prestige attacks;
- the Equality Guard;
- the Secret Scrubber boundary;
- schema-constrained ballots;
- one-member/one-vote enforcement;
- Council persistence;
- receipt generation;
- non-replayable marking for live inference.

See [`THREAT_MODEL.md`](THREAT_MODEL.md), [`docs/ADAPTERS.md`](docs/ADAPTERS.md), and `integration/ollama/`.

## Quick start

Requires Python 3.11+.

```bash
python -m pip install -e .
python -m nexus_runtime --demo
python -m unittest discover -s tests
```

Run the JSONL stdio API with an optional file-backed development world:

```bash
python -m nexus_runtime --world .nexus-world
```

Then send one JSON request per line:

```json
{"request_id":"1","operation":"system.health"}
```

List modes:

```json
{"operation":"world.modes"}
```

Inspect geometry:

```json
{"operation":"world.geometry"}
```

Run a Cultural Council in the Agora:

```json
{
  "operation":"council.run",
  "question":"Why does this joke work in one culture and fail in another?",
  "mode":"cultural",
  "members":[
    {"member_id":"A","model_id":"mock-a"},
    {"member_id":"B","model_id":"mock-b"},
    {"member_id":"C","model_id":"mock-c"}
  ]
}
```

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
9. **Model adapters are replaceable.** The world and protocol persist across model changes.
10. **Architecture before optimization.** Correctness and inspectability come before speed.
11. **CLI/TUI first.** A future Rust TUI will sit over the local protocol; the browser is not the trusted control plane.
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

That includes:

```text
provider prestige
corporate affiliation
frontier/commercial status
benchmark prestige
compute claims
model size
parameter count
```

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

This remains defence in depth, not perfect DLP. Credentials must still live only in future adapter auth/transport fields. See [`SECURITY.md`](SECURITY.md).

## Provider-neutral actor seam

The coordinator consumes:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

`PhaseContext` now also carries the selected world mode and geometry region.

Current implementations:

```text
DeterministicMockActor   replayable: true
OllamaActor              replayable: false
```

## JSONL runtime API

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
council.run
```

The JSONL `council.run` operation remains mock-only. Real provider configuration and authentication are deliberately deferred while NEXUS develops the world itself.

## Geometry and future telemetry

The research vocabulary around admissibility, basins, bottlenecks, branching and recovery is useful inspiration, but NEXUS will only promote those terms into runtime state when there are defined measurements behind them.

A likely future observation channel is **Council-response entropy**:

```text
near-identical independent responses
        -> lower response entropy
        -> lower informational diversity

divergent independent hypotheses
        -> higher response entropy
        -> higher informational diversity
```

Entropy would be telemetry, not truth, quality, or vote weight.

## What is deliberately not here yet

This alpha does **not** add:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- xAI / Grok;
- provider API keys or OAuth;
- remote provider networking;
- generic remote endpoints;
- a Rust TUI;
- arbitrary model-generated code execution;
- QEC-grade proof/replay for live inference;
- performance optimization or concurrent Council scheduling.

Remote provider auth is intentionally postponed until the shared-world, telemetry and operator contracts are more mature.

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — security, credential, and secret-scrubbing boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — executable adapter threat model
- [`docs/API.md`](docs/API.md) — executable JSONL control API
- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — World Modes and named-region geometry
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — planned operator experience
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — provider-neutral actor/adapter contract
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
