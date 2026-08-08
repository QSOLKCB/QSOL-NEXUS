# QSOL NEXUS 2.0-alpha

**Model-Independent Cognitive Substrate and AI Council Architecture**

> **Multiple minds. One world. Shared evidence. Equal voice.**

QSOL NEXUS is being redesigned as a persistent computational world that different machine intelligences can inhabit through a common protocol. Closed models, open-weight models, local models, symbolic systems, and future cognitive engines are peers at the protocol boundary.

The model does **not** own the world, memory, evidence, or vote weighting. NEXUS does.

## Status

This branch is an **architecture-first, documentation-only alpha**. It intentionally contains no new model API integrations, provider authentication code, Council runtime, persistence kernel, or TUI implementation yet. The goal of the first pull is to make the architecture accurate before optimizing or implementing it.

The previous NEXUS 1.0 browser workbench is preserved unchanged under [`archives/v1.0.0/`](archives/v1.0.0/) as referential prior work.

## Core idea

```text
                 HUMAN OPERATOR
                       |
                asks / configures
                       v
            +---------------------+
            |     RUST TUI/CLI    |
            | operator cockpit    |
            +----------+----------+
                       |
                 local protocol
                       v
            +---------------------+
            |   PYTHON TOOLING    |
            | world + orchestration|
            +----------+----------+
                       |
               NEXUS WORLD PROTOCOL
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
     Model A         Model B        Model C
     adapter         adapter        adapter
        |              |              |
        +--------- AI COUNCIL --------+
                       |
        De Bono-style parallel cycle
 WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE
                       |
                 sealed equal vote
                       |
                       v
              Council disposition
                       |
          evidence remains separate
                       |
                       v
          persistent world / lineage
```

## Constitutional principles

1. **One model member, one vote.** `vote_weight = 1` is an invariant.
2. **Open and closed models are peers.** Provider, licence, parameter count, deployment method, or commercial status grants no authority.
3. **Same world, same evidence, same hats, same vote.**
4. **Council consensus is not truth.** Verification and evidence status are tracked separately.
5. **Minority reports survive.** A losing vote is not deleted from the world.
6. **The model may be imaginative; the substrate must remain explicit.**
7. **Model adapters are replaceable.** The world and protocol persist across model changes.
8. **Architecture before optimization.** Correctness and inspectability come before speed.
9. **CLI/TUI first.** NEXUS 2.x does not require or trust a browser UI.
10. **Credentials are not cognitive state.** Secrets never enter world objects, Council transcripts, receipts, lineage, or archives.

## De Bono-style Council

Every participating model moves through the same parallel thinking modes:

| Phase | Purpose |
|---|---|
| White | establish facts, evidence, unknowns |
| Red | record intuition, suspicion, aesthetic or heuristic reactions |
| Black | identify flaws, risks, counterexamples and falsifiers |
| Yellow | identify value, supporting evidence and constructive potential |
| Green | generate alternatives, branches and experiments |
| Blue | synthesize the current position and cast the final ballot |

The default Council uses blind first-pass submissions and a sealed final ballot. See [`COUNCIL.md`](COUNCIL.md).

## Equality Guard

NEXUS includes a deliberately **light** equality guard. It does not rank models or police disagreement. It only prevents structured attempts to gain Council privilege through provider/corporate identity and nudges explicit status claims with:

> Council peers have equal standing. Provider or corporate identity does not confer authority here. Please restate the contribution on evidence or reasoning alone.

See [`GUARD.md`](GUARD.md).

## CLI/TUI direction

NEXUS 2.x is designed as a command-line tool with a Rust TUI layered over Python tooling.

```text
Rust TUI / CLI
      |
      | local structured messages
      v
Python NEXUS runtime
      |
      +-- world / memory / Council
      +-- deterministic instruments
      +-- receipts / replay / lineage
      |
      +-- adapter: OpenAI
      +-- adapter: Anthropic / Claude
      +-- adapter: Google / Gemini
      +-- adapter: xAI / Grok
      +-- adapter: Ollama / local
      +-- adapter: generic
```

Provider setup should feel like a modern coding CLI: select a provider, authenticate using whatever supported method that adapter exposes, test the connection, choose one or more models, and add them to a Council. NEXUS itself must not assume that every provider uses the same authentication mechanism.

See [`docs/CLI_TUI.md`](docs/CLI_TUI.md) and [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

## Planned world primitives

```text
world.inspect
world.search
world.recall
world.create_object
world.relate
world.compute
world.compare
world.simulate
world.visualize
world.sonify
world.hypothesize
world.test
world.falsify
world.commit
world.verify
world.replay
```

These are protocol concepts, not implemented commands in this alpha.

## Existing QSOL lineage

NEXUS 2.x is intended to provide a common world around existing QSOL ideas and instruments, including the deterministic/replay philosophy of QEC, the SPECTRAL tool family, sonification systems, visualization laboratories, and later domain-specific engines. Existing projects remain independent; NEXUS provides contracts and adapters rather than concatenating repositories.

The previous NEXUS 1.0 workbench remains available in the archive for ideas worth carrying forward.

## Documentation map

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — trust boundaries and system layout
- [`COUNCIL.md`](COUNCIL.md) — De Bono-style Council protocol
- [`GUARD.md`](GUARD.md) — lightweight equality guard
- [`CLAIMS.md`](CLAIMS.md) — consensus, evidence, and verification boundaries
- [`SECURITY.md`](SECURITY.md) — CLI/TUI security and credential boundaries
- [`docs/CLI_TUI.md`](docs/CLI_TUI.md) — planned operator experience
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — provider-neutral adapter contract
- [`docs/WORLD_PROTOCOL.md`](docs/WORLD_PROTOCOL.md) — planned shared-world primitives
- [`docs/COUNCIL_EXAMPLE_NGC3603.md`](docs/COUNCIL_EXAMPLE_NGC3603.md) — worked Council example
- [`ROADMAP.md`](ROADMAP.md) — staged implementation path
- [`archives/v1.0.0/`](archives/v1.0.0/) — preserved NEXUS 1.0 reference snapshot

## Licence

QSOL NEXUS is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

Copyright © 2026 Trent Slade / QSOL-IMC.
