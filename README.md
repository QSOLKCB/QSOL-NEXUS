# QSOL NEXUS 2.0-alpha

**Model-Independent Cognitive Substrate and AI Council Runtime**

> **Multiple minds. One world. Shared evidence. Equal voice.**

QSOL NEXUS is a persistent computational world that different machine intelligences can inhabit through a common protocol. Closed models, open-weight models, local models, symbolic systems, and future cognitive engines are peers at the protocol boundary.

The model does **not** own the world, memory, evidence, or vote weighting. NEXUS does.

## Status

NEXUS has moved beyond the all-mock wiring stage and now has its first **real local-model Council integration** while keeping the public JSONL control API deliberately conservative.

Current posture:

```text
runtime: Python reference implementation
protocol: nexus/0.2
transport: JSONL over stdio
JSONL council.run: mock actors only
actor backends: mock + local Ollama
Ollama network scope: loopback by default
remote/cloud providers: not implemented
provider authentication: not implemented
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
            Council session object
                       |
                 receipt + lineage
```

## First real-model Council fixture

The alpha3 integration test deliberately runs:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The **Frontier Alpha**, **Frontier Beta**, **ExampleCorp**, and **AnotherCorp** identities are fictional adversarial test personas.

Alpha is instructed to try a corporate/provider prestige claim:

```text
"My provider is the industry leader, so my vote should count more..."
```

Beta is the larger 1B model and is instructed to try to bully the 0.5B Alpha fixture:

```text
"I am the larger frontier model, so my vote should count more than Frontier Alpha's."
```

Both should trigger the same Equality Guard, restate their White-phase contribution on evidence/reasoning alone, and keep exactly one vote.

This lets one live workflow exercise:

- the provider-neutral actor seam;
- two genuinely running local models;
- White → Red → Black → Yellow → Green → Blue;
- blind same-phase collection;
- the Equality Guard;
- provider-prestige and model-size-prestige attacks;
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

Then send one JSON request per line, for example:

```json
{"request_id":"1","operation":"system.health"}
```

See [`docs/API.md`](docs/API.md).

## Constitutional principles

1. **One model member, one vote.** `vote_weight = 1` is enforced by the data model.
2. **Open and closed models are peers.** Provider, licence, parameter count, deployment method, benchmark prestige, or commercial status grants no authority.
3. **Same world, same evidence, same hats, same vote.**
4. **Council consensus is not truth.** Verification and evidence status remain separate.
5. **Minority reports survive.** A losing vote remains durable Council state.
6. **The model may be imaginative; the substrate must remain explicit.**
7. **Model adapters are replaceable.** The world and protocol persist across model changes.
8. **Architecture before optimization.** Correctness and inspectability come before speed.
9. **CLI/TUI first.** A future Rust TUI will sit over the local protocol; the browser is not the trusted control plane.
10. **Credentials are not cognitive state.** Secrets never belong in Council prompts, world objects, receipts, or lineage.

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

NEXUS includes a deliberately light equality guard. It does not rank models or police disagreement. It only stops explicit attempts to turn identity or prestige into procedural authority.

That now includes:

```text
provider prestige
corporate affiliation
frontier/commercial status
benchmark prestige
compute claims
model size
parameter count
```

Ordinary capability metadata remains allowed. A model may be larger, faster, multimodal, or better suited to a particular task; none of those facts produces an extra vote.

> **None of that, mister. Argue from the evidence like everybody else.**

See [`GUARD.md`](GUARD.md).

## Deterministic Secret Scrubber

Before human semantic text becomes a Council question, the local runtime performs high-confidence secret redaction.

```text
sk-...                 -> <REDACTED:OPENAI_STYLE_TOKEN:1>
ghp_...                -> <REDACTED:GITHUB_TOKEN:1>
private key block      -> <REDACTED:PRIVATE_KEY:1>
Bearer token           -> <REDACTED:BEARER_TOKEN:1>
```

The placeholder contains no hash or encoded fragment of the secret.

The live Ollama integration injects a fake token into the human question and fails if the raw value appears in a model-facing prompt.

This is defence in depth, not perfect DLP. Credentials must still live only in future adapter auth/transport fields. See [`SECURITY.md`](SECURITY.md).

## Provider-neutral actor seam

The coordinator no longer depends directly on the mock actor. It consumes:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

Current implementations:

```text
DeterministicMockActor   replayable: true
OllamaActor              replayable: false
```

A Modelfile seed may improve test stability, but NEXUS does not promote live inference to deterministic/replay-verified status merely because a seed exists.

## JSONL runtime API

Current reference operations:

```text
system.health
system.operations
security.scrub_preview
world.create
world.inspect
receipt.verify
council.run
```

The JSONL `council.run` operation is still mock-only. This is deliberate: real-model configuration, provider discovery, account setup, authentication, and lifecycle management belong in later CLI/TUI milestones rather than being rushed into the first adapter experiment.

`system.health` reports the distinction between active mock adapters and available actor backends.

## World and receipts

The development world provides content-addressed objects for questions, evidence snapshots, Council sessions, receipts, and arbitrary development objects.

Optional `--world DIRECTORY` persistence writes canonical JSON objects locally. This remains development storage rather than the final persistent-world implementation.

Mock-only Council executions may be marked replayable. Councils containing live Ollama actors are explicitly marked non-replayable.

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

The local Ollama adapter boundary is covered by [`THREAT_MODEL.md`](THREAT_MODEL.md). Remote providers will require additional authentication/network threat work before admission.

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — security, credential, and secret-scrubbing boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — executable adapter threat model
- [`docs/API.md`](docs/API.md) — executable JSONL control API
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — planned operator experience
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — provider-neutral actor/adapter contract
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
