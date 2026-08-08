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
- [x] document provider-authentication UX without implementing provider flows;
- [x] archive NEXUS 1.0 as referential prior work.

## 2.0-alpha1 — Python reference protocol

The mock-runtime pull implemented the first small executable path:

```text
operator text
  -> deterministic secret scrub
  -> canonical question object
  -> operation
  -> Council result
  -> Council session object
  -> receipt
  -> receipt verification
```

Implemented:

- [x] canonical JSON and content-addressed object references;
- [x] local in-memory world;
- [x] optional file-backed development world;
- [x] deterministic reference operations;
- [x] JSONL-over-stdio API seam for the future Rust TUI;
- [x] simple receipt object and reference verification;
- [x] deterministic pre-model Secret Scrubber;
- [x] standard-library Python test suite;
- [ ] generalized operation replay beyond deterministic re-execution fixtures;
- [ ] final schema/version migration policy.

The development file store and receipt verifier remain intentionally modest. They do not claim final NEXUS persistence or QEC-level replay semantics.

## 2.0-alpha2 — Council coordinator

The mock-runtime pull wired Council mechanics with deterministic fake actors before any real model provider was connected.

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

The first executable non-mock boundary is intentionally local before any cloud credential is introduced.

Completed / in this milestone:

- [x] dedicated `THREAT_MODEL.md` before executable non-mock adapter admission;
- [x] provider-neutral `CouncilActor` protocol;
- [x] mock actor refactored onto the shared actor seam;
- [x] minimal stdlib Ollama actor;
- [x] loopback-only-by-default Ollama transport;
- [x] schema-constrained Ollama ballot output;
- [x] live secret-crossing assertion at the adapter boundary;
- [x] explicit non-replayable marking for live inference;
- [x] unit tests for endpoint policy and parameter-count authority claims;
- [x] separate GitHub Actions live-Ollama integration workflow;
- [x] fictional 0.5B Frontier Alpha adversarial fixture;
- [x] fictional 1B Frontier Beta adversarial fixture;
- [x] corporate/provider-prestige guard test using a real local model;
- [x] model-size/parameter-count guard test using a real local model;
- [ ] local subprocess adapter distinct from Ollama;
- [ ] generic endpoint adapter;
- [ ] full adapter lifecycle/failure state abstraction;
- [ ] operator-configurable adapter registry through JSONL/CLI;
- [ ] local daemon identity/process supervision.

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

The frontier identities are fictional test personas. Alpha deliberately attempts to pull rank through corporate/provider prestige. Beta deliberately attempts to pull rank because it is the larger fixture. Both must receive the same Equality Guard nudge and retain exactly one vote.

The public JSONL `council.run` operation remains mock-instantiation-only. This prevents local integration plumbing from accidentally becoming an undocumented provider-configuration surface.

### After the local adapter survives

Next adapter targets should be introduced independently:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- xAI / Grok.

Provider integrations must remain replaceable and must not leak provider-specific semantics into Council voting or world identity. Each remote adapter must extend the threat model for its own authentication, destination, transport, failure, and tool-call surfaces.

## 2.0-alpha4 — Authentication and provider setup

Implement coding-CLI-style setup:

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
- the Secret Scrubber remains upstream of every model-facing semantic request.

Initial provider rollout should be one adapter at a time rather than connecting every commercial model in one pull.

## 2.0-alpha5 — Rust CLI/TUI

Build the Rust operator shell over the stable JSONL/local protocol.

Goals:

- single clear executable entrypoint;
- provider/account status;
- Council creation and monitoring;
- phase and ballot views;
- world-object browsing;
- evidence and minority reports;
- secret-scrub event visibility without secret disclosure;
- instrument and receipt inspection;
- local model process/endpoint supervision;
- useful non-interactive subcommands for automation/SSH.

The Rust layer should not duplicate Python/world business logic.

## 2.0-alpha6 — Instruments

Connect selected existing QSOL capabilities as versioned instruments rather than embedding entire repositories.

Candidates:

- QEC-derived canonical receipt/replay concepts;
- SPECTRAL analysis;
- SONIFICATION;
- visualization/export tools;
- numerical and symbolic computation;
- selected domain laboratories from NEXUS 1.0.

Instrument admission requires explicit input/output and claim boundaries.

## 2.0-alpha7 — Persistent world

Upgrade development storage into a robust persistent world:

- content-addressed objects;
- provenance;
- relations;
- hypotheses;
- experiment lineage;
- Council-session objects;
- searchable minority reports;
- migration/version policy;
- import/export.

## 2.0-alpha8 — Three minds, one world demo

Reference demonstration:

```text
Model A enters
  -> creates hypothesis + experiment
  -> leaves

Model B enters later
  -> discovers existing objects
  -> replays experiment where replay is applicable
  -> critiques interpretation

Model C enters
  -> proposes falsifier
  -> executes allowed instrument
  -> creates verified descendant

All three contributions remain in one world lineage.
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
- operational logging/redaction tests;
- endpoint/process impersonation tests;
- provider destination allowlisting tests.

## 2.0 release criterion

NEXUS 2.0 should not be called stable until:

1. multiple unrelated model adapters can inhabit the same persistent world;
2. Council equality is mechanically enforced;
3. Council sessions are replayable at the protocol/evidence level where underlying operations are actually replayable;
4. credentials are outside durable cognitive state and semantic prompts;
5. at least one local and one remote model can participate as peers;
6. an evidence-producing instrument can be called through the world protocol;
7. minority reports and failed hypotheses survive in lineage;
8. the Rust CLI/TUI remains a replaceable shell rather than the source of truth.

## Optimization policy

Accuracy and contract clarity come first.

Do not optimize concurrency, token routing, model batching, binary formats, distributed execution, or provider-specific shortcuts until the reference protocol has been exercised enough to reveal real bottlenecks.
