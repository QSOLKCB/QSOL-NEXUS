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

The mock-runtime pull implements the first small executable path:

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

Implemented in this stage:

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

The development file store and receipt verifier are intentionally modest. They do not claim the final NEXUS persistence or QEC-level replay semantics.

## 2.0-alpha2 — Council coordinator

The mock-runtime pull wires the Council mechanics with deterministic fake actors before any real model provider is connected.

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
- [x] deterministic mock adapter/actors;
- [x] network posture explicitly reports `none`;
- [x] user semantic text scrubbed before model-facing Council context.

No commercial or remote provider SDK belongs in alpha2.

## 2.0-alpha3 — Adapter protocol

Before any executable provider adapter ships, create the dedicated adapter threat model required by `SECURITY.md`. The threat model must cover the adapter boundary sufficiently to review credential handling, provider transport, scrubber bypass, imported/model-generated content, tool-call requests, local endpoint impersonation, and failure behavior before executable provider code is admitted.

Then implement the provider-neutral adapter contract.

Start with:

- mock adapter conformance extraction from alpha2;
- local subprocess adapter;
- Ollama/local-model adapter;
- generic endpoint adapter.

Then add remote providers independently, potentially including:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- xAI / Grok.

Provider integrations must remain replaceable and must not leak provider-specific semantics into Council voting or world identity. Tests must prove raw injected credentials cannot reach provider request bodies.

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
- authentication material never enters semantic prompts.

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
- useful non-interactive subcommands for automation/SSH.

The Rust layer should not duplicate the Python/world business logic.

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
  -> replays experiment
  -> critiques interpretation

Model C enters
  -> proposes falsifier
  -> executes allowed instrument
  -> creates verified descendant

All three contributions remain in one world lineage.
```

A Council version should demonstrate heterogeneous providers and at least one local/open model with equal votes.

## 2.0-beta — Hardening

- adapter threat model implemented and tested;
- credential handling audited;
- Secret Scrubber bypass fixtures;
- provider failure/quorum behavior tested;
- replay/tamper fixtures;
- bounded Council loops;
- adapter conformance suite;
- world migration fixtures;
- deterministic Council-policy tests;
- operational logging/redaction tests.

## 2.0 release criterion

NEXUS 2.0 should not be called stable until:

1. multiple unrelated model adapters can inhabit the same persistent world;
2. Council equality is mechanically enforced;
3. Council sessions are replayable at the protocol/evidence level;
4. credentials are outside durable cognitive state and semantic prompts;
5. at least one local and one remote model can participate as peers;
6. an evidence-producing instrument can be called through the world protocol;
7. minority reports and failed hypotheses survive in lineage;
8. the Rust CLI/TUI remains a replaceable shell rather than the source of truth.

## Optimization policy

Accuracy and contract clarity come first.

Do not optimize concurrency, token routing, model batching, binary formats, distributed execution, or provider-specific shortcuts until the reference protocol has been exercised enough to reveal real bottlenecks.
