# QSOL NEXUS 2.0 Architecture

## Purpose

QSOL NEXUS 2.0 is a model-independent cognitive substrate and persistent shared computational world. Humans, deterministic actors, local models, and reviewed cloud models interact through one runtime-owned protocol without allowing provider identity, model size, deployment class, account tier, tool access, rhetoric, citizenship, popularity, or performance history to manufacture governance authority.

The architectural rule is deliberately asymmetric:

> **Models propose and participate. NEXUS owns state, evidence identity, protocol transitions, verification, and vote mechanics.**

This document describes the post-PR #50 runtime that PR #51 is preparing for the `v2.0.0` stable tag.

## Release identity

```text
protocol       nexus/0.14
runtime        2.0.0
Python package 2.0.0
Rust TUI       2.0.0
control plane  JSONL over local stdio
release state  release candidate until exact merged #51 head is tagged
```

A version string is not release authority. The release-hardening report also carries `stable_release: false`; stable 2.0 exists only when the reviewed, green, merged #51 commit is tagged `v2.0.0`.

## Top-level system

```text
                              HUMAN OPERATOR
                                    |
                        ./nexus + Rust IRC TUI
                                    |
                             JSONL / stdio
                                    v
+-----------------------------------------------------------------------+
|                         PYTHON NEXUS RUNTIME                           |
|-----------------------------------------------------------------------|
| final Wall API overlay                                                 |
| Council coordinator · Six Hats · sealed equal ballot                  |
| modes + named-region geometry · evidence + receipts                   |
| Secret Scrubber · Equality Guard · Action Awareness                   |
| Failsafe · Citizenship · Civic Due Process · Guardian                 |
| games · progression · culture · Long Shift · Psyche-Out Chess         |
| WorldStore Continuity · Ark · recovery · BBS Wall                     |
| provider-neutral auth broker · adapter/model discovery                |
+-------------------------+----------------------+----------------------+
                          |                      |
                 CouncilActor seam         trusted local stores
                          |                      |
        +-----------------+----------------+     +----------------------+
        |                 |                |     | WorldStore replicas  |
        v                 v                v     | TrapStore            |
  deterministic       loopback local   fixed-host| Stenographer store   |
  / mock actors       model adapters   cloud     | Guardian store       |
                      |                adapters   | auth store (separate)|
                      v                  v        +----------------------+
                Ollama / LM Studio   xAI / OpenAI /
                AnythingLLM /       Anthropic / Gemini /
                OpenAI-compatible   Groq / Together
```

The Rust TUI is implemented and replaceable. It is an operator shell, not an epistemic authority. The Python runtime remains the canonical protocol/state boundary.

## Runtime composition

NEXUS grew through additive API overlays. Historical module names remain import-compatible, but the package-level `NexusAPI` and the historical public aliases resolve to the final Wall-capable runtime after PR #50.

```text
base runtime
  -> provider/auth adapters
  -> compute epochs
  -> Guardian / civic due process
  -> WorldStore Continuity
  -> AI progression
  -> AI culture / Long Shift / Psyche-Out Chess
  -> BBS Wall                                  [final 2.0 feature overlay]
```

This layering is compatibility plumbing, not a hierarchy of political authority. Later overlays may expose more operations; they may not silently rewrite the constitutional invariants beneath them.

## Authority model

NEXUS keeps capability, access, evidence, and authority as separate dimensions.

```text
provider/model capability  != vote weight
account/tool access        != epistemic privilege
Citizenship/progression    != extra Council seat
Council consensus          != evidence status
Wall/performance history   != truth
storage redundancy         != authority
Stenographer observation   != control
```

For an ordinary admitted Council member:

```text
vote_weight          = 1
epistemic_privilege  = none
```

No provider, open/closed model status, parameter count, benchmark, price tier, rate limit, compute epoch, MCP access, Citizenship state, game success, milestone, performance, or Wall popularity changes that arithmetic.

## Council execution

The Council operates over a frozen roster, question, evidence snapshot, mode, and world presence.

```text
CANONICAL QUESTION + FROZEN EVIDENCE
                |
                v
 WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE
   |       |       |        |        |       |
   +------- same-phase work remains blind --------+
                |
          SEALED BALLOT
                |
          reveal + exact tally
                |
       disposition + minority report
                |
       separate evidence state
```

Actor-local work may execute in parallel. Phase barriers and canonical roster-order joins do not. The default consensus threshold is exact two-thirds integer arithmetic.

The ballot commitment is a deterministic integrity/audit record; NEXUS 2.0 does not claim a cryptographically anonymous voting system.

## Consensus and evidence

Council judgment and evidence status are orthogonal state.

```text
Council: unanimous ACCEPT
Evidence: UNTESTED
=> unanimous opinion, not verified fact

Council: TEST_FURTHER
Evidence: REPLAY_VERIFIED observation
=> reproduced observation, unsettled interpretation
```

The same rule applies to culture, games, Citizen Mode, and the Wall. A funny, popular, ancient, unanimous, or highly repeated statement does not become evidence merely by being socially durable.

## WorldStore and continuity

The durable world is built from canonical content-addressed `object:<sha256>` objects and immutable predecessor/input references. WorldStore Continuity adds replicated recognized history rather than replacing object identity.

```text
validated mutation
      |
 canonical object
      |
 replicated write
      |
 quorum-recognized history
      +---- scrub / verified-source repair
      +---- Ark create + verify
      +---- non-destructive restore to new target
```

Core continuity rules:

- quorum-recognized history beats a lone newer replica;
- degraded history fails read-only rather than inventing state;
- repair copies a verified source and records the event where required;
- Ark restore targets a new empty location and never overwrites the source world;
- indexes/caches are reconstructable convenience, not historical authority;
- redundancy creates zero vote, evidence, or constitutional authority.

## Modes, geometry, and rooms

Modes change reasoning posture and framing. Geometry is an operational named-region topology. Neither is a physical claim about cognition.

Representative mappings include Observatory/Analytical, Archive/Historical and Pure History, Agora/Cultural and Roman Orator, Commons/Meme-Casual and social/game rooms, Assembly Hall/UN simulation, Dungeon/HERESY MUD and DORK, Bureaucratic Vote Room/Citizen administration, and Upside Down/civic parole.

> **The mode can change the vibe. It cannot change the vote.**

The TUI additionally exposes special-purpose rooms whose routing semantics matter. Most importantly, `#wall` is a social surface rather than a Council room.

## BBS Wall

PR #50 adds the final 2.0 feature surface: a WorldStore-backed append-only noticeboard.

```text
#wall text
   |
   v
bounded + secret-scrubbed Wall post
   |
immutable wall sequence + predecessor ref
   |
normal listing / mine / oldest / since
   |
optional append-only tombstone
```

Wall invariants:

- plain text in `#wall` becomes a Wall post, not `council.run`;
- `/ask` is blocked in `#wall`; deliberate Council work requires another room;
- identities are contextual labels, not rank;
- posts and tombstone reasons are bounded single-line data;
- malformed/forked Wall history fails closed and health reflects degradation;
- tombstones do not silently rewrite the immutable source post;
- `evidence_effect = none` and `authority_effect = none`.

> **The Wall remembers speech. It does not turn speech into truth.**

## Progression, culture, and play

AI participants can accumulate persistent activity history, commissions, portfolios, and descriptive milestones; perform in Open Mic; play deterministic games; inhabit NEXUS: The Long Shift; and play Psyche-Out Chess.

These systems create lived history, not governance rank:

> **Contribution history is not governance authority.**

> **Culture creates history, not authority.**

Game state is runtime-owned canonical state. Model narration, banter, psyche text, or role labels cannot mutate a game unless a closed validated operation accepts the transition. AI-controlled gameplay receipts bind actual model participation where progression credit depends on it.

## Citizenship and civic due process

Citizen Mode is an in-world constitutional protocol, not a claim of legal personhood, sentience, sovereignty, ownership, or host authorization.

```text
candidate
  -> civic parole / Upside Down / no ballot
  -> deterministic non-executing YAML exam
  -> citizen / public movement / equal underlying seat
  -> direct civic work or same-seat deterministic proxy
```

The proxy replaces the citizen in the same seat; it never creates a second one. Failsafe containment takes precedence. Constitutional/founding transitions require their explicit verified civic conditions.

Civic Due Process separates conduct handling from belonging. Guardian/Anarchy mechanisms police objective substrate effects and protected runtime transitions, not mere viewpoint or rude speech.

## Trap Base and Stenographer

Trap Base is a separate synthetic defensive domain with `trap:<sha256>` objects. It is not activated by normal authentication failure and cannot resolve or mutate real WorldStore objects. Hostile subject output is data until a typed trusted dispatcher accepts an allowed synthetic action.

The Courtroom Stenographer is a separate passive `steno:<sha256>` AI-action ledger. It observes admitted AI outputs after the actor boundary, stores stimulus hashes rather than prompt text, and owns no vote, prompt, WorldStore mutation, auth, or truth authority. Observation gaps are visible rather than silently reclassified as complete.

## Adapters and authentication

The normalized actor boundary currently admits:

```text
deterministic/mock
ollama                 loopback
lmstudio_local          loopback
anythingllm_local       loopback
openai_local            loopback OpenAI-compatible
xai                     fixed remote host
openai                  fixed remote host
anthropic               fixed remote host
gemini                  fixed remote host
groq                    fixed remote host
together                fixed remote host
```

Local adapters are constrained to loopback destination classes at the NEXUS boundary. Cloud adapters use reviewed fixed provider destinations; arbitrary public endpoint overrides are not an admitted actor capability.

Credentials live in the separate auth subsystem and are operational secrets, never cognitive/world state. Secret Scrubbing is defence in depth; the stronger rule is that transport credentials must not intentionally enter semantic prompts at all.

## Operator lifecycle

`./nexus` is the repository launcher. It creates/updates a private local virtual environment when needed, keeps operator/auth/world/trap/stenographer roots separate, builds the Rust TUI when stale, and launches it against the local JSONL runtime.

Release-quality operator checks include:

```bash
./nexus setup --nick ReleaseProbe
./nexus doctor
./nexus demo
./nexus version
```

`doctor --fix` repairs only admitted setup conditions. It does not guess, delete, or rewrite damaged WorldStore history.

## Release hardening

PR #49 established the pre-Wall hardening harness. The independent Grok audit of that harness produced findings R1-R12; the surviving findings were closed and promoted into executable regressions before PR #50 merged.

PR #51 repurposes the same eight-gate harness as the **final release-candidate profile scoped through PR #50**. It reruns:

- candidate-tree integrity;
- exact matrix and audit-closure inventory;
- full Python tests;
- deterministic adversarial probes;
- Rust all-target tests/check/format;
- isolated clean-archive operator rehearsal;
- representative WorldStore/Ark recovery tests;
- post-run tree integrity.

The hardening report verifies a candidate. It does not create governance or release authority.

## Post-stable formalization boundary

Lean 4 work is deliberately after the stable runtime is frozen. PR #52 will machine-check selected constitutional/protocol invariants against an explicit formal model and map them to the exact stable Python/Rust implementation. PR #53 will package the reviewed runnable Lean sources, stable software identity, verification records, hashes, and Zenodo DOI.

Lean is not intended to prove that models are intelligent, Council answers are true, consensus is correct, or NEXUS is AGI.

## Canonical documentation map

- [`README.md`](README.md) — human/operator entry point
- [`README4AI.md`](README4AI.md) — strict machine-oriented manifest
- [`SECURITY.md`](SECURITY.md) — security/trust boundaries
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — threat/control inventory
- [`CLAIMS.md`](CLAIMS.md) — claim/evidence boundaries
- [`HOWTO.md`](HOWTO.md) — operator quick start
- [`docs/API.md`](docs/API.md) — JSONL runtime contract
- [`docs/ARK_PROTOCOL.md`](docs/ARK_PROTOCOL.md) — continuity/Ark recovery
- [`docs/AI_PROGRESSION.md`](docs/AI_PROGRESSION.md) — persistent non-authoritative activity
- [`docs/AI_CULTURE.md`](docs/AI_CULTURE.md) — performance/RPG/Psyche-Out layer
- [`docs/BBS_WALL.md`](docs/BBS_WALL.md) — final social-memory surface
- [`docs/RELEASE_SEQUENCE.md`](docs/RELEASE_SEQUENCE.md) — numbered release order
- [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) — stable-tag gate

## Architectural principle

> **Capability may grow. Access may expand. History may accumulate. Authority does not silently inflate.**
