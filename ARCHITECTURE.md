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
                    | passive Stenographer    |
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

The Rust TUI is an operator interface, not an epistemic authority. The Python layer remains the first reference tooling/runtime because it is easy to inspect, script, test, and connect to the existing scientific Python ecosystem.

The provider-neutral authentication substrate is implemented outside the WorldStore. xAI is the first fixed-destination remote adapter; every later provider remains deferred until its own security/transport review and the broader world/instrument milestones are complete.

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
| non-secret auth profile/status control                  |
+---------------------------+-----------------------------+
                            |
                    durable world state
```

A model response is a **proposal** until NEXUS records it under the applicable phase and evidence state. Corporate identity, provider branding, model self-description, selected world mode, or geometry location cannot alter protocol authority.

## Decoy Gate and Trap Base

The synthetic decoy path is a third security domain, not an authentication
fallback and not a room inside the real world:

```text
trusted operator fixture -> DecoyGate -> TrapController -> TrapStore
                                                |
                           +--------------------+--------------------+
                           |                                         |
                    #trap-control                              #trap-base
                    defender snapshot                         hostile subject
                    equal incident votes                      no vote/tools/auth
```

The trusted front-door router sends normal credentials only to `AuthBroker`.
Ordinary failure ends there. Only one closed `DecoyAdmissionRequest` carrying an
approved synthetic reason can enter `DecoyGate`; no bearer value is a field in
that request.

The trap domain owns only `trap:<sha256>` objects, static synthetic scenarios,
an incident-specific defender roster, hostile text, trap commands, restricted
Trap YAML execution, and quarantined candidate artifacts. Real objects remain
`object:<sha256>`, and neither store resolves the other namespace.

An owner-checked `CouncilMutationGate` pauses real WorldStore/game/Council
mutation for the lifetime of the one active incident without moving or
rewriting real history. Read/verification/auth operations remain unchanged.
Immutable trap incident lineage is canonical; a small validated index and lock
can be rebuilt or safely released by crash recovery.

Subject output is always data. Only a typed operator/defender call can enter the
closed command dispatcher. Trap YAML is parsed into a bounded canonical
JSON-compatible tree and interpreted over immutable synthetic fixtures; it is
never executed by Python, a shell, an LLM, or a production instrument.

See [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md).

## Courtroom Stenographer

The Courtroom Stenographer is an independent observation domain beside the
WorldStore and TrapStore, not another control-plane authority:

```text
AI actor result -----> normal Council/direct/Trap consumer
       |
       +-------------> passive observer copy
                              |
                     bounded nonblocking queue
                              |
                     background lock/write/fsync
                              |
                         steno:<sha256>
                         canonical lineage
```

It records admitted direct replies, every Council phase attempt and sealed
ballot, Failsafe rehabilitation replies, and synthetic Trap subject replies.
Prompts are represented only by a `stimulus:<sha256>` binding; human commands,
world/game/auth actions and control-plane decisions are outside its scope.

Every record carries an explicit zero-authority envelope. The Stenographer owns
no actor, prompt, Council roster, vote, command dispatcher, WorldStore,
TrapStore or AuthBroker handle. Observation failures are caught after the actor
boundary; storage work is handed to a bounded nonblocking daemon observer, so
lock contention and lineage scans cannot delay the original AI result. Queue
saturation increments a bounded gap counter. Its owner-only store is disjoint
from all other persistence roots and
uses a linear immutable previous-record chain; the replaceable index is rebuilt
from lineage.

The Rust `#stenographer` room and `/steno` namespace expose only read and
verification views. See [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md).

## Modes and geometry

NEXUS separates **how a session is framed** from **where it exists in the shared world**.

```text
MODE
  reasoning posture · context · tone

GEOMETRY
  region · coordinate · adjacency · presence
```

Current map:

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /   |   \
                       \           /    |    \
                        COMMONS ----+    |   DUNGEON
                      Meme/Casual        |   HERESY / DORK
                         (2,1)            |   (2,-2)
                            \             |   /
                             \            |  /
                              ASSEMBLY HALL--+
                              UN Simulation
                                  (0,-2)
```

Selected built-in mappings (multiple modes intentionally share regions):

| Mode | Region |
|---|---|
| `analytical` | Observatory |
| `historical` | Archive |
| `pure_history` | Archive |
| `cultural` | Agora |
| `meme_casual` | Commons |
| `clinical_differential` | Observatory |
| `house_fun` | Commons |
| `cbt_learning` | Observatory |
| `roman_orator` | Agora |
| `house_of_wisdom` | Archive |
| `ultimate_questions` | Observatory |
| `game_un` | Assembly Hall |
| `game_mud` | Dungeon |
| `game_uno` | Commons |
| `game_monopoly` | Commons |
| `game_500` | Commons |
| `game_blackjack` | Commons |
| `game_dork` | Dungeon |

The geometry is deliberately an **operational topology**, not a claim that cognition, history, culture, or humor literally occupy Euclidean coordinates.

Mode invariants:

```text
mode may change framing
mode may change tone
mode may change contextual instructions
mode may select a bounded generation-length preference

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

### Deterministic game objects

UN simulation, HERESY MUD, UNO, Monopoly, 500, Blackjack and DORK v2 use the
same WorldStore identity contract. A validated action reads one immutable state
and creates one canonical successor with a `previous_state_ref` and typed
transition. Public `content` is a derived bounded representation for Council
evidence; private hands remain in player-specific operator views.

Decks, dice and shoes are deterministic substrate operations, never model
choices. Table AI receives a seat under the same rules as a human but no direct
WorldStore authority. DORK v2 is structurally different: its sole actor is the
bound human operator and models have no avatar.

See [`docs/GAMES.md`](docs/GAMES.md).

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
| auth capability  |  # neutral substrate implemented
| model discovery  |  # xAI implemented; later providers reviewed
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

- NEXUS has no browser application or browser-local credential store;
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
  +-- auth broker / credential-source router
  +-- adapter manager
```

JSON Lines over stdio remains the simplest reference IPC. A local socket may later be justified by concurrency needs.

## Provider authentication boundary

The long-term operator experience remains coding-CLI-like:

```text
nexus auth add
nexus auth adapters
nexus auth list
nexus auth test
nexus auth logout
nexus models list
```

PR #16 implements the provider-neutral broker, browser PKCE and device-code state machines, refresh handling, credential-source routing, safe profile/status operations, and storage isolation. The broker is operational infrastructure; it is not world state and cannot construct a Council actor by itself.

PR #17 admits xAI's documented API-key path, fixed `api.x.ai` transport, connection test, language-model discovery, and Responses API actor. It deliberately does not import Grok Build's first-party browser session or invent a NEXUS OAuth client registration. Credentials remain outside world state, Council prompts, receipts and lineage. See [`docs/AUTH.md`](docs/AUTH.md) and [`docs/XAI_ADAPTER.md`](docs/XAI_ADAPTER.md).

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
