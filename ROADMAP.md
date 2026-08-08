# QSOL NEXUS 2.x Roadmap

NEXUS 2.x is deliberately architecture-first. The project should earn complexity rather than start with a large agent framework.

## 2.0-alpha0 — Architecture constitution

Documentation-only milestone completed in PR #1.

- [x] redefine NEXUS as a model-independent persistent cognitive substrate;
- [x] define CLI/TUI-first direction;
- [x] define Python tooling beneath a future Rust operator shell;
- [x] define model-neutral adapter boundary;
- [x] define open/closed model equality;
- [x] define one-member/one-vote invariant;
- [x] define De Bono-style White/Red/Black/Yellow/Green/Blue Council cycle;
- [x] define blind first-pass and sealed final ballot concepts;
- [x] define lightweight Equality Guard;
- [x] distinguish Council consensus from evidence/verification;
- [x] sketch world objects and world operations;
- [x] document future provider-authentication UX without implementing provider flows;
- [x] archive NEXUS 1.0 as referential prior work.

## 2.0-alpha1 — Python reference protocol

Implemented:

- [x] canonical JSON and content-addressed object references;
- [x] local in-memory world;
- [x] optional file-backed development world;
- [x] deterministic reference operations;
- [x] JSONL-over-stdio API seam for the future Rust TUI;
- [x] simple receipt object and reference verification;
- [x] deterministic pre-model Secret Scrubber;
- [x] standard-library Python test suite.

Still later:

- [ ] generalized operation replay beyond deterministic fixtures;
- [ ] final schema/version migration policy.

## 2.0-alpha2 — Council coordinator

Implemented:

- [x] minimum roster and unique member enforcement;
- [x] frozen equal roster metadata;
- [x] White/Red/Black/Yellow/Green/Blue ordering;
- [x] blind same-phase collection;
- [x] deterministic ballot commitment/reveal records;
- [x] one member, one vote mechanically enforced;
- [x] exact two-thirds default consensus threshold using integer arithmetic;
- [x] minority reports;
- [x] Council/evidence status separation;
- [x] lightweight Equality Guard nudge/resubmission path;
- [x] deterministic mock actor;
- [x] network posture explicitly reports `none` for the JSONL control API;
- [x] user semantic text scrubbed before model-facing Council context.

## 2.0-alpha3 — Adapter protocol and first live local Council

Completed in PR #3:

- [x] dedicated `THREAT_MODEL.md` before executable non-mock adapter admission;
- [x] provider-neutral `CouncilActor` protocol;
- [x] mock actor refactored onto the shared actor seam;
- [x] minimal stdlib Ollama actor;
- [x] loopback-only-by-default Ollama transport;
- [x] environment-proxy bypass protection for loopback transport;
- [x] redirect rejection for loopback transport;
- [x] schema-constrained and locally validated Ollama ballot output;
- [x] live secret-crossing assertion at the adapter boundary;
- [x] explicit non-replayable marking for live inference;
- [x] separate GitHub Actions live-Ollama integration workflow;
- [x] fictional 0.5B Frontier Alpha adversarial fixture;
- [x] fictional 1B Frontier Beta adversarial fixture;
- [x] provider-prestige and model-size-prestige Equality Guard tests with real local models.

Current acceptance Council:

```text
Mock reference
     +
Frontier Alpha / qwen2.5:0.5b
     +
Frontier Beta / llama3.2:1b
     |
     v
NEXUS AI Council
```

The public JSONL `council.run` operation remains mock-instantiation-only.

## 2.0-alpha4 — World Modes and Geometry

Make NEXUS feel like an inhabitable shared world rather than only a deliberation engine.

Initial modes:

```text
analytical  -> Observatory
historical  -> Archive
cultural    -> Agora
meme_casual -> Commons
```

Initial geometry:

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

Goals:

- [x] deterministic built-in mode registry;
- [x] modes carry framing/context but no procedural authority;
- [x] named-region geometry with integer coordinates;
- [x] explicit symmetric adjacency;
- [x] deterministic hop distance;
- [x] content-addressed Council `world_presence` objects;
- [x] mode/region included in frozen Council identity;
- [x] mode propagation through `PhaseContext` to actors;
- [x] `world.modes` API;
- [x] `world.geometry` API;
- [x] `world.geometry.distance` API;
- [x] deterministic tests proving mode changes framing but not vote mechanics;
- [x] documentation of operational-vs-physical geometry claim boundary;
- [ ] user-defined modes;
- [ ] explicit recorded `world.move` transitions;
- [ ] richer object-to-region placement rules.

Core invariant:

> **The mode can change the vibe. It cannot change the vote.**

## 2.0-alpha5 — Council information telemetry

Add observation channels for *how* a Council converges or diverges without turning telemetry into authority.

Primary candidate: Council-response entropy.

```text
near-identical independent responses
        -> low response entropy
        -> low informational diversity

divergent independent hypotheses
        -> high response entropy
        -> high informational diversity
```

Potential metrics:

- per-hat response diversity;
- ballot entropy;
- hypothesis branching multiplicity;
- recovery after controlled perturbation;
- loop / repeated-motif indicators;
- simple mode-transition cost;
- minority-branch persistence.

Requirements:

- telemetry is observational, not a vote weight;
- high entropy is not automatically good;
- low entropy is not automatically truth;
- metrics must be reproducible from captured Council artifacts where practical;
- geometric labels such as `bottlenecked` or `shattered` require explicit measurement rules rather than analogy alone.

## 2.0-alpha6 — Rust CLI/TUI

Build the Rust operator shell over the stable JSONL/local protocol.

Goals:

- single clear executable entrypoint;
- world-mode selection;
- geometry/region display;
- Council creation and monitoring;
- phase and ballot views;
- world-object browsing;
- evidence and minority reports;
- telemetry inspection;
- secret-scrub event visibility without secret disclosure;
- instrument and receipt inspection;
- local model process/endpoint supervision;
- useful non-interactive subcommands for automation/SSH.

Provider/account login UI remains deferred until the authentication milestone.

The Rust layer should not duplicate Python/world business logic.

## 2.0-alpha7 — Instruments

Connect selected existing QSOL capabilities as versioned instruments rather than embedding entire repositories.

Candidates:

- QEC-derived canonical receipt/replay concepts;
- SPECTRAL analysis;
- SONIFICATION;
- visualization/export tools;
- numerical and symbolic computation;
- selected domain laboratories from NEXUS 1.0.

Instrument admission requires explicit input/output and claim boundaries.

Creative modes should be able to use instruments too; Meme/Casual Mode does not mean “no tools.”

## 2.0-alpha8 — Persistent world

Upgrade development storage into a robust persistent world:

- content-addressed objects;
- provenance;
- relations;
- hypotheses;
- experiment lineage;
- Council-session objects;
- world-presence and movement history;
- searchable minority reports;
- mode history;
- migration/version policy;
- import/export.

## 2.0-alpha9 — Authentication and remote-provider setup

Only after the world, modes, telemetry, operator surface, instruments and persistence contracts are mature enough should NEXUS invite remote providers into the operator-configurable runtime.

Planned UX:

```text
nexus auth add
nexus auth list
nexus auth test
nexus models list
```

Requirements:

- adapter reports supported authentication methods;
- credentials remain outside world state and receipts;
- OS secret/keyring integration where practical;
- explicit headless/external-secret path;
- visible connection test;
- no assumption that all providers authenticate the same way;
- authentication material never enters semantic prompts;
- Secret Scrubber remains upstream of every semantic request;
- provider-specific threat model extension before admission.

Initial remote-provider targets, one at a time:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- xAI / Grok.

Provider integrations remain replaceable and confer no voting authority.

## 2.0-alpha10 — Three minds, one world demo

Reference demonstration:

```text
Model A enters a world region
  -> creates hypothesis + experiment
  -> leaves

Model B enters later
  -> discovers existing objects and placement
  -> replays experiment where applicable
  -> critiques interpretation

Model C enters
  -> proposes falsifier
  -> executes allowed instrument
  -> creates verified descendant

All contributions remain in one world lineage.
```

A Council version should demonstrate heterogeneous remote providers and at least one local/open model with equal votes.

## 2.0-beta — Hardening

- adapter threat models implemented and tested;
- credential handling audited;
- Secret Scrubber bypass fixtures;
- provider failure/quorum behavior tested;
- replay/tamper fixtures;
- bounded Council loops;
- adapter conformance suite;
- world migration fixtures;
- deterministic Council-policy tests;
- mode/geometry migration tests;
- telemetry reproducibility tests;
- operational logging/redaction tests;
- endpoint/process impersonation tests;
- provider destination allowlisting tests.

## 2.0 release criterion

NEXUS 2.0 should not be called stable until:

1. multiple unrelated model adapters can inhabit the same persistent world;
2. Council equality is mechanically enforced;
3. Council sessions preserve mode, placement and evidence lineage;
4. Council sessions are replayable at the protocol/evidence level where underlying operations are actually replayable;
5. credentials are outside durable cognitive state and semantic prompts;
6. at least one local and one remote model can participate as peers;
7. an evidence-producing instrument can be called through the world protocol;
8. minority reports and failed hypotheses survive in lineage;
9. the Rust CLI/TUI remains a replaceable shell rather than the source of truth;
10. information/geometry telemetry is clearly separated from evidence and authority.

## Optimization policy

Accuracy and contract clarity come first.

Do not optimize concurrency, token routing, model batching, binary formats, distributed execution, or provider-specific shortcuts until the reference protocol has been exercised enough to reveal real bottlenecks.
