# QSOL NEXUS 2.0-alpha

**Model-Independent Cognitive Substrate and AI Council Runtime**

> **Multiple minds. One world. Shared evidence. Equal voice.**

QSOL NEXUS is a persistent computational world that different machine intelligences can inhabit through a common protocol. Closed models, open-weight models, local models, symbolic systems, and future cognitive engines are peers at the protocol boundary.

The model does **not** own the world, memory, evidence, or vote weighting. NEXUS does.

## Status

NEXUS now has its first executable **mock reference runtime**. This stage deliberately uses deterministic fake model actors to wire up and test the system before any real provider SDK, authentication flow, or outbound model traffic is introduced.

Current posture:

```text
runtime: Python reference implementation
transport: JSONL over stdio
provider adapters: mock only
network: none
world persistence: optional local canonical JSON files
Rust TUI: planned, not implemented
real AI providers: not implemented
```

The previous NEXUS 1.0 browser workbench remains preserved unchanged under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work.

## Current executable path

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
            | world + Council API |
            +----------+----------+
                       |
                NEXUS protocol
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
     Mock A          Mock B         Mock C
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

The mock actors perform no inference and make no network requests. They exist to test the architecture.

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
2. **Open and closed models are peers.** Provider, licence, parameter count, deployment method, or commercial status grants no authority.
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

The reference coordinator implements blind same-phase collection, deterministic ballot commitments, exact two-thirds consensus arithmetic, and durable minority reports. See [`COUNCIL.md`](COUNCIL.md).

## Equality Guard

NEXUS includes a deliberately light equality guard. It does not rank models or police disagreement. It only stops explicit attempts to turn provider/corporate identity into procedural authority and asks the member to restate the argument on evidence or reasoning alone.

> **None of that, mister. Argue from the evidence like everybody else.**

The guard never changes vote weight. See [`GUARD.md`](GUARD.md).

## Deterministic Secret Scrubber

Before human semantic text becomes a Council question, the local runtime performs high-confidence secret redaction.

```text
sk-...                 -> <REDACTED:OPENAI_STYLE_TOKEN:1>
ghp_...                -> <REDACTED:GITHUB_TOKEN:1>
private key block      -> <REDACTED:PRIVATE_KEY:1>
Bearer token           -> <REDACTED:BEARER_TOKEN:1>
```

The placeholder contains no hash or encoded fragment of the secret. Repeated appearances of the same detected secret receive the same placeholder within one scrub operation.

This is defence in depth, not perfect DLP. Unknown secret formats can evade pattern detection, so credentials must still stay in future adapter auth/transport fields rather than semantic prompts. See [`SECURITY.md`](SECURITY.md).

## Mock runtime API

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

`system.health` explicitly reports `network: none` and `adapters: [mock]` in this stage.

The transport is intentionally simple JSON Lines over stdin/stdout so a future Rust TUI can supervise the Python runtime without requiring HTTP or a browser.

## World and receipts

The first development world provides content-addressed objects for:

```text
question
evidence_snapshot
council_session
receipt
arbitrary development objects
```

Optional `--world DIRECTORY` persistence writes canonical JSON objects locally. This is intentionally simple development storage rather than the final world database.

Council receipts currently bind the operation, input references, result reference, protocol version, and replayable flag. Receipt verification checks referenced objects remain present. Stronger replay/tamper semantics will be added after the protocol stabilizes.

## What is deliberately not here yet

This pull does **not** add:

- OpenAI, Anthropic/Claude, Gemini, Grok, Ollama, or generic remote adapters;
- provider authentication;
- outbound HTTP;
- a Rust TUI;
- arbitrary model-generated code execution;
- a claim of QEC-level proof machinery;
- performance optimization or concurrent Council scheduling.

Real provider adapters must wait for the dedicated adapter threat model required by [`SECURITY.md`](SECURITY.md) and [`ROADMAP.md`](ROADMAP.md).

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — security, credential, and secret-scrubbing boundaries
- [`docs/API.md`](docs/API.md) — executable mock JSONL API
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — planned operator experience
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — future provider-neutral adapter contract
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
