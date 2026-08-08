# QSOL NEXUS 2.0 Architecture

## Purpose

QSOL NEXUS is a model-independent cognitive substrate: a persistent computational world that humans and heterogeneous machine intelligences can inspect, extend, test, and revisit through a common protocol.

NEXUS does not attempt to define how a model must think internally. It defines how participants interact with shared objects, evidence, experiments, instruments, Council sessions, durable state, world modes, and geometry.

## Top-level architecture

```text
                           HUMAN OPERATOR
                                 |
                                 v
                    +-------------------------+
                    |   CLI / future RUST TUI |
                    | Council · world · modes |
                    | receipts · logs · tools |
                    +------------+------------+
                                 |
                         local IPC / JSONL
                                 |
                                 v
                    +-------------------------+
                    |     PYTHON RUNTIME      |
                    |-------------------------|
                    | Council orchestration   |
                    | world object service    |
                    | modes + geometry        |
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
```

The future Rust TUI is an operator interface, not an epistemic authority. The Python layer remains the first reference tooling/runtime because it is easy to inspect, script, test, and connect to the existing scientific Python ecosystem.

Provider authentication is deliberately deferred until the shared-world contracts have matured further.

## Trust domains

```text
UNTRUSTED / EXTERNAL
+---------------------------------------------------------+
| model providers · local model servers · generated prose|
| provider SDKs · network transport · model self-claims  |
+---------------------------+-----------------------------+
                            |
                      adapter boundary
                            |
TRUSTED NEXUS CONTROL PLANE
+---------------------------v-----------------------------+
| roster · equal voting · phase ordering · sealed ballot |
| world mode · geometry placement · evidence snapshots   |
| canonical objects · receipts · lineage · verification  |
+---------------------------+-----------------------------+
                            |
                    durable world state
```

A model response is a **proposal** until NEXUS records it under the applicable phase and evidence state. Corporate identity, provider branding, model self-description, selected world mode, or geometry location cannot alter protocol authority.

## Modes and geometry

NEXUS separates **how a session is framed** from **where it exists in the shared world**.

```text
MODE
  reasoning posture · context · tone

GEOMETRY
  region · coordinate · adjacency · presence
```

Initial map:

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

Built-in modes:

```text
analytical  -> Observatory
historical  -> Archive
cultural    -> Agora
meme_casual -> Commons
```

The geometry is deliberately an **operational topology**, not a claim that cognition, history, culture, or humor literally occupy Euclidean coordinates.

Mode invariants:

```text
mode may change framing
mode may change tone
mode may change contextual instructions

mode may NOT change vote_weight
mode may NOT change epistemic_privilege
mode may NOT change evidence_state
mode may NOT disable verification
mode may NOT disable the Equality Guard
mode may NOT bypass the Secret Scrubber
```

This distinction is important because model prompts are guidance, not the source of runtime authority.

See [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md).

## World presence

A Council session is placed into the world through a content-addressed presence object:

```text
WorldPresence
├── mode_id
├── mode_label
├── region_id
├── region_label
├── coordinates
├── member_ids[]
├── question_ref
└── geometry_id
```

The presence reference becomes part of the frozen Council session identity. Identical questions run in different modes therefore form distinct world lineage.

## Council architecture

```text
                       CANONICAL QUESTION
                              |
                    frozen evidence snapshot
                              |
                      MODE + WORLD REGION
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

Council equality is structural, not aspirational. Each registered Council member has exactly one ballot and `vote_weight = 1` regardless of provider, model size, mode, or region.

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

The same rule applies in Meme/Casual Mode: a very funny unanimous answer is still not evidence.

## World model

The fundamental unit is a content-addressable **World Object**.

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

The alpha4 named-region map is therefore a minimal navigational substrate rather than a scientific claim.

## Geometry-inspired telemetry

Research concepts such as basins, bottlenecks, branching multiplicity, perturbation sensitivity, recovery time and control-gain collapse may later inspire measurable NEXUS telemetry.

They must remain operationally typed:

```text
measured response diversity -> telemetry
measured branching          -> telemetry
measured recovery time      -> telemetry

analogy to spectral gap     != measured physical/operator spectrum
```

Council-response entropy is a particularly promising future observation channel: low entropy can indicate convergent responses, while higher entropy can indicate greater informational diversity. It must not be interpreted as truth or quality by itself.

## Model adapter boundary

```text
NEXUS envelope
     |
     v
+------------------+
| provider adapter |
|------------------|
| auth capability  |  # later milestone
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
- mutate a frozen evidence snapshot;
- redefine the active world mode;
- move the Council to a different region without a recorded world transition.

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

A future visualization viewer may exist, but it should consume completed world objects and geometry rather than become the trusted orchestration surface.

## Proposed process layout

```text
nexus                         # Rust CLI/TUI (future)
  |
  +-- starts / connects to
  |
python -m nexus_runtime       # Python reference runtime
  |
  +-- world service
  +-- Council coordinator
  +-- mode registry
  +-- geometry service
  +-- equality guard
  +-- instrument registry
  +-- receipt/replay service
  +-- adapter manager
```

JSON Lines over stdio remains the simplest reference IPC. A local socket may later be justified by concurrency needs.

## Provider authentication boundary — deferred

The long-term operator experience remains coding-CLI-like:

```text
nexus auth add
nexus auth list
nexus auth test
nexus models list
```

But authentication is intentionally **not** the next architectural priority. NEXUS should first develop the shared world, geometry, modes, telemetry, instruments and operator shell enough that remote providers are arriving into a stable place rather than defining that place.

Credentials will remain outside world state, Council prompts, receipts and lineage when this layer is implemented.

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

## Architecture rule

Build the smallest correct path first:

```text
object
  -> placement
  -> operation
  -> result
  -> observation
  -> receipt
  -> replay where applicable
```

Then expand the world. Authentication and optimization come after the world contracts survive real use.
