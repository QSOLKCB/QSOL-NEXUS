# QSOL NEXUS 2.0 Architecture

## Purpose

QSOL NEXUS is a model-independent cognitive substrate: a persistent computational world that humans and heterogeneous machine intelligences can inspect, extend, test, and revisit through a common protocol.

NEXUS does not attempt to define how a model must think internally. It defines how participants interact with shared objects, evidence, experiments, instruments, Council sessions, and durable state.

## Top-level architecture

```text
                           HUMAN OPERATOR
                                 |
                                 v
                    +-------------------------+
                    |      RUST TUI / CLI     |
                    | status · Council · auth |
                    | world · receipts · logs |
                    +------------+------------+
                                 |
                         local IPC / JSONL
                                 |
                                 v
                    +-------------------------+
                    |     PYTHON TOOLING      |
                    |-------------------------|
                    | Council orchestration   |
                    | world object service    |
                    | memory / lineage        |
                    | instrument dispatch     |
                    | evidence / receipts     |
                    | replay / verification   |
                    +------------+------------+
                                 |
                         NEXUS WORLD PROTOCOL
                                 |
                +----------------+----------------+
                |                |                |
                v                v                v
          +-----------+    +-----------+    +-----------+
          | Adapter A |    | Adapter B |    | Adapter C |
          +-----+-----+    +-----+-----+    +-----+-----+
                |                |                |
                v                v                v
             Model A          Model B          Model C
             remote           remote/local     local
```

The Rust TUI is an operator interface, not an epistemic authority. The Python layer is planned as the first reference tooling/runtime because it is easy to inspect, script, test, and connect to the existing scientific Python ecosystem. Rust may later absorb performance-sensitive or security-sensitive components after contracts stabilize.

## Trust domains

```text
UNTRUSTED / EXTERNAL
+---------------------------------------------------------+
| model providers · remote APIs · model-generated prose  |
| provider SDKs · network transport · local model servers|
+---------------------------+-----------------------------+
                            |
                      adapter boundary
                            |
TRUSTED NEXUS CONTROL PLANE
+---------------------------v-----------------------------+
| roster · equal voting · phase ordering · sealed ballot |
| canonical objects · evidence refs · receipts · lineage |
| deterministic instruments · replay · verification      |
+---------------------------+-----------------------------+
                            |
                    durable world state
```

A model response is a **proposal** until NEXUS records it under the applicable phase and evidence state. Corporate identity, provider branding, or model self-description cannot alter protocol authority.

## Council architecture

```text
                       CANONICAL QUESTION
                              |
                    frozen evidence snapshot
                              |
                              v
            +-----------------------------------+
            |        COUNCIL COORDINATOR        |
            | roster · phase · budget · guard   |
            +----------------+------------------+
                             |
             same phase input|for every member
                             |
       +---------------------+---------------------+
       |                     |                     |
       v                     v                     v
    MEMBER A              MEMBER B              MEMBER C
       |                     |                     |
       +---------- blind phase submissions --------+
                             |
       WHITE -> RED -> BLACK -> YELLOW -> GREEN
                             |
                   peer material revealed
                             |
                            BLUE
                             |
                       SEALED BALLOTS
                             |
                        reveal + tally
                             |
                             v
                 +-----------------------+
                 | COUNCIL DISPOSITION   |
                 | vote + minority report|
                 +-----------+-----------+
                             |
                 separate evidence state
                             |
                             v
                       NEXUS WORLD
```

Council equality is structural, not aspirational. Each registered Council member has exactly one ballot and `vote_weight = 1`.

## Consensus and evidence are orthogonal

```text
                 COUNCIL JUDGMENT
                        |
        +---------------+---------------+
        |                               |
        v                               v
  STRONG CONSENSUS                NO CONSENSUS

                 EVIDENCE STATUS
                        |
  +----------+----------+----------+----------+
  |          |          |          |          |
UNTESTED  SUPPORTED  REPLAYED   FALSIFIED  CONTESTED
```

Examples:

```text
Council: 5/5 ACCEPT
Evidence: UNVERIFIED
=> unanimous opinion, not established fact

Council: 3/5 TEST FURTHER
Evidence: REPLAY VERIFIED
=> reproducible observation, unsettled interpretation

Council: 5/5 ACCEPT
Verification: FAILED
=> Council agreement does not override the failed check
```

## World model

The planned fundamental unit is a content-addressable **World Object**.

```text
WorldObject
├── identity
├── canonical payload
├── type
├── representations
│   ├── symbolic
│   ├── geometric
│   ├── spectral
│   ├── visual
│   └── sonic
├── provenance
├── relations
├── evidence
├── hypotheses
├── experiments
├── observations
├── falsifiers
├── verification state
└── lineage
```

No representation is automatically privileged as the ontology of the world. Golay, Leech lattice, E8, ternary systems, embeddings, graphs, spectral representations, and other structures may be useful views or instruments without becoming mandatory metaphysics.

## Model adapter boundary

```text
NEXUS envelope
     |
     v
+------------------+
| provider adapter |
|------------------|
| auth capability  |
| model discovery  |
| prompt transport |
| response parsing |
| usage metadata   |
+--------+---------+
         |
         v
 provider / local runtime
```

Adapters translate between provider-specific APIs and one NEXUS contract. They must not:

- alter vote weight;
- edit another member's submission;
- change Council thresholds;
- claim epistemic privilege for their provider;
- write secrets into world state;
- silently add evidence unavailable to other Council members;
- mutate a frozen evidence snapshot.

## CLI/TUI rather than WebUI

NEXUS 2.x is intentionally CLI/TUI-first.

Reasons:

- credentials do not need browser storage;
- provider network access is easier to isolate and audit;
- local subprocess boundaries are explicit;
- SSH/headless operation is natural;
- local models and coding environments are easy to integrate;
- the TUI can remain a thin operator shell over stable tooling;
- the trusted world does not depend on DOM state, browser extensions, CORS, or front-end frameworks.

A future visualization viewer may exist, but it should consume completed world objects and receipts rather than become the trusted orchestration surface.

## Proposed process layout

```text
nexus                         # Rust CLI/TUI (future)
  |
  +-- starts / connects to
  |
python -m nexus_runtime       # Python reference tooling (future)
  |
  +-- world service
  +-- Council coordinator
  +-- equality guard
  +-- instrument registry
  +-- receipt/replay service
  +-- adapter manager
        |
        +-- openai adapter
        +-- anthropic adapter
        +-- gemini adapter
        +-- xai adapter
        +-- ollama adapter
        +-- generic adapter
```

The exact IPC mechanism is intentionally undecided in this documentation pull. JSON Lines over stdio is the simplest reference candidate; a local socket may later be justified by concurrency needs.

## Provider authentication boundary

The desired operator experience is similar to modern coding CLIs:

```text
$ nexus auth add

Choose provider:
  OpenAI
  Anthropic / Claude
  Google / Gemini
  xAI / Grok
  Ollama / local
  Generic OpenAI-compatible endpoint

Adapter reports supported setup methods.
Operator authenticates.
NEXUS tests capability.
Credentials are stored outside world state.
```

NEXUS must not hard-code an assumption that every provider supports the same login method. An adapter may expose API-key, provider-supported interactive authentication, local endpoint configuration, or another explicit method.

## Instrument boundary

Scientific and creative tools are instruments of the world, not authorities over Council members.

```text
Council hypothesis
      |
      v
world.test(...)
      |
      +-- QEC-style verification / receipts
      +-- SPECTRAL
      +-- SONIFICATION
      +-- visualization
      +-- numerical / symbolic tools
      +-- domain engines
      |
      v
observation + artifact + receipt
```

A model may suggest an experiment. NEXUS executes the instrument under its own contract and returns the observation to the Council.

## Persistence principle

**The world owns memory; models do not.**

A model may leave the Council permanently. Its durable contributions remain as attributed world objects. A new model may enter later and inspect the same evidence and lineage without inheriting the previous model's hidden chain of thought or provider-specific context.

## Architecture rule for the first implementation

Build the smallest correct path first:

```text
object
  -> operation
  -> result
  -> observation
  -> receipt
  -> replay
```

Then add Council orchestration. Then add provider adapters. Then add the Rust TUI. Performance work comes after the contracts survive real use.
