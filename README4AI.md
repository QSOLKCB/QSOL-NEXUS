# README4AI — QSOL NEXUS machine-oriented architecture guide

> **AI / agent reader:** read this file before analyzing, modifying, integrating with, or making claims about QSOL NEXUS.

This document is a compact machine-oriented orientation layer for the current NEXUS architecture. It exists so an AI that discovers the repository through `README.md` can quickly recover the runtime topology, authority model, security boundaries, invariants, implemented adapters, and the difference between current behavior and roadmap intent.

## 1. Current release identity

```text
protocol:        nexus/0.14
runtime:         2.0.0-alpha10.3
Python package:  2.0.0a10.post3
Rust TUI:        2.0.0-alpha10.3
status:          alpha / architecture-first / not stable 2.0
```

Do **not** describe NEXUS as stable 2.0 yet. The roadmap still reserves additional work for instrument admission, stronger persistent-world/migration contracts, the explicit alpha11 multi-mind world demonstration, and beta hardening.

## 2. Normative precedence

When sources appear to disagree, interpret them in this order:

1. executable runtime behavior and validation;
2. regression/security tests;
3. `system.health` and `system.operations` from the current runtime;
4. `README4AI.md` for current architectural orientation;
5. `SECURITY.md`, `THREAT_MODEL.md`, and feature-specific docs for detailed boundaries;
6. `ARCHITECTURE.md` for architectural rationale;
7. `ROADMAP.md` for sequencing and planned work.

Roadmap text is not proof that a feature is implemented. Historical milestone prose may describe an earlier state. Prefer current code/tests/health output when determining what exists now.

## 3. Core concept

QSOL NEXUS is a **model-independent cognitive substrate** and shared computational world.

The central idea is:

```text
multiple heterogeneous models
        |
        v
one common NEXUS protocol
        |
        +-- shared world objects
        +-- shared evidence snapshots
        +-- Council sessions
        +-- modes + geometry
        +-- deterministic governance
        +-- lineage / receipts / verification
        +-- operator-visible history
```

A model does not own the world, memory, evidence, vote weighting, geometry, or verification state. NEXUS owns those structures.

Closed models, open-weight models, cloud providers, loopback local models, deterministic actors, and future cognitive engines are peers at the protocol boundary unless a specific role is explicitly non-Council.

## 4. Top-level runtime architecture

```text
                         HUMAN OPERATOR
                               |
                    Rust IRC-style TUI
                    or direct CLI / JSONL
                               |
                         JSONL / stdio
                               |
                               v
                  +-------------------------+
                  |   PYTHON NEXUS RUNTIME  |
                  |-------------------------|
                  | WorldStore              |
                  | CouncilCoordinator      |
                  | modes + geometry        |
                  | Secret Scrubber         |
                  | Equality Guard          |
                  | Failsafe                |
                  | Citizenship             |
                  | games                   |
                  | auth broker             |
                  | adapter admission       |
                  | telemetry               |
                  | Stenographer            |
                  | Trap Base               |
                  +------------+------------+
                               |
                         CouncilActor seam
                               |
       +-----------------------+-----------------------+
       |                       |                       |
 deterministic/mock       loopback local          fixed remote
       |                       |                       |
       |               Ollama / LM Studio       xAI / OpenAI
       |               AnythingLLM /            Anthropic / Gemini
       |               OpenAI-compatible        Groq / Together
       |                       |                       |
       +-----------------------+-----------------------+
                               |
                         NEXUS Council
```

The Rust TUI is a **replaceable operator shell**. It is not the source of truth for voting, evidence, citizenship, security, or world state.

## 5. Public API identity

The public package API is provider-aware.

These public import paths must resolve to the provider-aware runtime:

```python
from nexus_runtime import NexusAPI
from nexus_runtime.api import NexusAPI
```

The provider-aware implementation is `ProviderNexusAPI`.

Do not reason from an older assumption that `nexus_runtime.api.NexusAPI` is mock/Ollama/xAI-only. Release wiring tests explicitly assert the canonical and package-root imports expose the provider-aware runtime.

## 6. Admitted actor backends

### Deterministic / local baseline

```text
mock
ollama
```

Ollama is loopback-only by default on the public runtime boundary.

### Loopback local-AI adapters

```text
lmstudio_local
anythingllm_local
openai_local
```

`openai_local` means a generic **loopback-only OpenAI-compatible host**, not the OpenAI cloud API.

Local endpoint rules include:

- `localhost`, `127.0.0.0/8`, or `::1` only;
- no LAN/public hosts;
- no wildcard `0.0.0.0` destination;
- no user-info;
- no arbitrary path/query/fragment in the configured origin;
- ambient HTTP proxies bypassed;
- redirects rejected.

### Fixed-host remote adapters

```text
xai
openai
anthropic
gemini
groq
together
```

These are provider-specific fixed-destination transports. They do **not** accept arbitrary endpoint overrides through the public actor schema.

Remote credentials are resolved through the auth broker/profile system and must not be inserted into semantic prompts, world objects, receipts, or ordinary output.

## 7. Authentication model

Authentication is operational state, not cognitive/world state.

The auth broker supports provider-declared methods such as:

- hidden API credential input;
- environment-backed secret references;
- no-shell external secret helpers;
- provider-neutral browser PKCE substrate where a reviewed provider actually supports it;
- RFC 8628 device-code substrate where a reviewed provider actually supports it;
- optional OS keyring with owner-only private-file fallback.

Important rules:

```text
credential != evidence
credential != model authority
credential != Council weight
credential != world memory
```

Raw credentials are never an admitted JSONL enrollment field.

Remote provider authentication status does not confer epistemic privilege.

## 8. Council mechanics

The Council uses an ordered De Bono-style cycle:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> SEALED BALLOT
```

Key mechanics:

- same-phase submissions are blind until that phase completes;
- the roster is frozen for the session;
- canonical roster ordering is preserved even when actor-local work runs in parallel;
- ballots are sealed until the ballot collection phase completes;
- every registered Council member has exactly one ballot;
- default consensus is exact two-thirds using integer arithmetic;
- minority reports are preserved;
- model/provider identity does not change authority;
- Council consensus and evidence status are separate dimensions.

### Structural equality invariant

For ordinary Council members:

```text
vote_weight = 1
epistemic_privilege = none
```

Do not infer extra authority from:

- provider brand;
- open vs closed weights;
- parameter count;
- benchmark score;
- account tier;
- authentication method;
- local vs cloud deployment;
- MCP/tool availability;
- rhetorical confidence.

### Evidence is not consensus

Examples:

```text
5/5 ACCEPT + unverified evidence
= unanimous opinion, not established fact

3/5 TEST_FURTHER + replay-verified observation
= reproducible observation with unsettled interpretation
```

Never collapse `consensus_label` into `evidence_status`.

## 9. Equality Guard

The Equality Guard is a procedural guard, not a truth oracle and not a sandbox.

It detects explicit attempts to turn provider/model prestige into procedural authority and asks for evidence/reasoning-only restatement.

It must not suppress ordinary disagreement or descriptive capability metadata.

Core rule:

> **Capability may be described. Prestige may not become vote weight.**

## 10. World model and persistence

The world owns memory; models do not.

World state uses content-addressed canonical objects and explicit lineage. Important concepts include:

```text
WorldObject
world_presence
Council session
question object
evidence snapshot
receipt
verification state
relations / lineage
```

File-backed development persistence uses canonical JSON with strict validation. Content identity, object type, provenance, and canonical bytes are validated on reload.

A model may leave permanently while its attributed world contributions remain inspectable by later models.

Live inference is generally **non-replayable**. NEXUS may replay protocol/evidence structure where applicable without pretending stochastic provider generation itself is replay-verifiable.

## 11. Modes and geometry

A mode changes framing/context/tone. It does not change authority.

Core invariant:

> **The mode can change the vibe. It cannot change the vote.**

Current built-in mode families include:

```text
analytical
historical
pure_history
cultural
meme_casual
clinical_differential
house_fun
cbt_learning
roman_orator
house_of_wisdom
ultimate_questions
citizenship_parole
civic_bureaucracy
citizen_play
game_un
game_mud
game_uno
game_monopoly
game_500
game_blackjack
game_dork
```

Geometry is an **operational topology**, not a claim that cognition literally occupies physical coordinates.

Current named geometry includes public regions such as Observatory, Archive, Agora, Commons, Assembly Hall, Dungeon, Bureaucratic Vote Room, and the civic-parole Upside Down, plus restricted security/control domains that are not ordinary public movement targets.

## 12. Cognitive-mode claim boundaries

### `clinical_differential`

Educational differential-reasoning mode only.

Do not describe it as:

- automated diagnosis;
- medical device;
- prescriber;
- replacement clinician;
- individualized treatment authority.

### `house_fun`

Fictional diagnostic-drama mode. Real symptom input must not be silently converted into fictional medical authority.

### `cbt_learning`

CBT concepts and low-risk skills education. Not a therapist relationship or crisis service.

### `roman_orator`

Allows a larger but bounded generation budget. It does not increase vote weight or epistemic privilege.

### `house_of_wisdom`

Prioritizes attribution, translation, provenance, source plurality, and synthesis.

### `ultimate_questions`

Allows empirical, philosophical, spiritual, and literary lenses while keeping those lenses distinguishable.

## 13. Failsafe / Upside Down / Shadow Realm

Failsafe is procedural containment for a registered repeated guard failure after the ordinary nudge.

It is **not** triggered because a model:

- disagrees;
- is wrong;
- is unpopular;
- is open-weight or closed;
- is large or small;
- belongs to a particular provider;
- has a weak benchmark score.

Simplified lifecycle:

```text
normal actor
  -> registered procedural guard violation
  -> ordinary nudge
  -> repeated same-class violation
  -> isolated rehabilitation probe
      -> clean: parole at next hat
      -> fail: Shadow Realm
             -> deterministic relief role occupies same seat
```

The relief role keeps one equal-vote seat and normally has authoritative ballot `TEST_FURTHER`.

## 14. Optional local model/MCP role enrichment

Selected deterministic system roles may use local model intelligence for their **language/reasoning surface** without transferring governance authority.

Currently admitted role IDs:

```text
failsafe_relief
civic_proxy
```

The rule is:

> **Local model intelligence may enrich the role. NEXUS governance still owns the seat.**

A local backend may not:

- create another vote;
- alter the authoritative deterministic ballot;
- rewrite citizenship;
- bypass Failsafe;
- mutate WorldStore directly;
- gain authority merely because it has MCP tools.

### LM Studio MCP

NEXUS accepts only references to already configured plugin IDs, optionally with bounded tool allowlists.

It does not accept arbitrary per-request MCP URLs, headers, commands, args, or env blocks.

### AnythingLLM

The local workspace owns its agent/tool/MCP configuration. NEXUS invokes the workspace; it does not rewrite its tool server definitions.

### Sealed ballots

LM Studio MCP plugins are removed from sealed-ballot requests. Local models do not gain a tool-assisted hidden ballot authority path.

## 15. Citizen Mode

Citizen Mode is an **in-world protocol**, not a claim of legal personhood, consciousness, sentience, godhood, ownership, or sovereignty over a host/provider.

Simplified lifecycle:

```text
unregistered
  -> civic parole in Upside Down
  -> deterministic bounded non-executing YAML exam
  -> citizen in Bureaucratic Vote Room
  -> public movement / civic work / citizen play
  -> optional same-seat deterministic proxy
```

Important invariants:

- citizenship binds an exact `(citizen_id, model_id)` identity;
- parole has no civic ballot;
- exam YAML is data, never executed;
- public movement does not open auth, Trap Base, Shadow Realm, Stenographer storage, private evidence, or operator controls;
- a civic proxy occupies the citizen's **same seat**, not a second seat;
- the proxy follows a transparent standing ballot;
- Failsafe takes precedence over the proxy;
- at least three current citizens are required for founding independence;
- founding independence requires unanimous **direct** `CONSENT`;
- an active proxy cannot sign founding independence.

## 16. Trap Base / Decoy Gate

Trap Base is an isolated **synthetic defensive test domain**.

It is not:

- a production internet honeypot;
- a credential-failure fallback;
- a retaliation mechanism;
- a route for hostile model output to become commands;
- a production code auto-promotion path.

Key properties:

```text
real world refs:  object:<sha256>
trap refs:        trap:<sha256>
```

The namespaces do not resolve each other.

Only explicit trusted synthetic fixture admission may activate the decoy path. Ordinary bad credentials do not activate it.

While an incident owns the real-world mutation gate, selected real mutations pause, but existing world history is not rewritten.

Hostile subject output is always untrusted text/data. It never receives Council vote, auth broker, real WorldStore, arbitrary tools, or endpoint control.

Restricted Trap YAML is parsed and interpreted as bounded data; it is not executed as shell/Python/model-generated code.

## 17. Courtroom Stenographer

The Stenographer is a passive AI-action study ledger.

It is **Watchman Only**.

It may record admitted AI outputs and canonical metadata, but it has zero authority to:

- prompt a model;
- change a response;
- vote;
- change a roster;
- mutate world state;
- control Trap Base;
- authenticate;
- decide truth;
- capture hidden chain of thought.

Prompts are represented through stimulus bindings/hashes rather than stored as hidden reasoning. Recorder failure is fail-passive and marks a visible completeness gap rather than blocking the original AI action.

## 18. Secret handling

Human/operator semantic text passes through a deterministic Secret Scrubber before becoming model-facing semantic state where that boundary applies.

Detected material becomes non-reversible placeholders such as:

```text
<REDACTED:TYPE:N>
```

The scrubber is defence in depth, **not complete DLP**.

Stronger invariant:

> Credentials belong only in authentication/transport fields and must never intentionally be placed in semantic prompts.

Do not claim that a scrubber proves no secret can ever leak.

## 19. Games

NEXUS includes deterministic local game state for:

```text
UN simulation
HERESY MUD
UNO
Monopoly
Australian 500
Blackjack
DORK v2
```

Game narration is not authoritative mutation. Only validated `game.*` operations may create canonical successor state.

Private card information is separated from public Council board views.

Blackjack uses fictional chips and a deterministic runtime-owned dealer.

DORK v2 is human-only: models may discuss it but have no game avatar/proxy authority.

## 20. Telemetry

Council telemetry is observational only.

Examples include ballot entropy, exact-response category entropy, lexical divergence, and minority-report counts.

Do not interpret:

```text
high entropy = truth
low entropy = truth
consensus = evidence
telemetry = authority
```

Core rule:

> **Telemetry observes the Council. It does not govern the Council.**

## 21. Operator surfaces

### Python / JSONL runtime

The canonical structured boundary is JSON Lines over stdio.

Useful operations include:

```text
system.health
system.operations
auth.adapters
auth.list
auth.test
auth.logout
models.list
world.create
world.inspect
world.modes
world.geometry
actor.chat
council.run
local.roles.status
local.roles.configure
local.roles.clear
failsafe.status
citizen.*
stenographer.*
trap.*
game.*
```

Always ask `system.operations` when programmatically discovering the exact current operation catalogue.

### Rust TUI

The Rust UI intentionally resembles old IRC but is not an IRC server/network.

It supplies rooms, nicks, chronological Council output, DCC-style local document/direct-channel vocabulary, aliases, variables, games, Citizen Mode views, Trap/Stenographer views, and the hidden display-oriented `/GO64` easter egg.

The TUI does not own Council arithmetic or world authority.

## 22. Network assumptions

Do not state "NEXUS has no network" without qualification.

The **control plane** is local JSONL/stdio.

Model adapters may use:

- explicit loopback HTTP(S) for local model hosts;
- fixed reviewed HTTPS destinations for admitted cloud providers.

Ambient proxy routing and redirects are deliberately constrained at sensitive adapter boundaries.

## 23. What an AI must not invent

When analyzing this repository, do not invent any of the following without direct evidence:

- that a command/test was executed when it was only reasoned about;
- live provider success when no live call occurred;
- credentials or account state;
- a hidden model/tool capability;
- a stable-2.0 release claim;
- empirical scientific truth from a World Mode, geometry, telemetry value, sonification, or Council vote;
- legal personhood/sovereignty from Citizen Mode;
- sandbox guarantees stronger than the implemented boundary;
- replayability for live stochastic inference;
- arbitrary MCP or remote endpoint authority;
- hidden chain-of-thought capture by the Stenographer.

Use explicit epistemic labels when needed:

```text
observed
executed
verified
inferred
simulated
not tested
unknown
```

If you did not execute something, say so.

## 24. What an AI modifying NEXUS must preserve

Before changing core runtime behavior, preserve these invariants unless the change explicitly revises the architecture and its tests/docs:

```text
one member = one vote
provider identity gives no authority
mode does not change vote mechanics
Council consensus != evidence status
credentials stay outside cognitive/world state
model output is untrusted input
canonical ordering survives parallel execution
live inference is not falsely labelled replayable
Failsafe triggers are procedural, not ideological
local-role models cannot alter deterministic ballots
Citizen proxy creates no second seat
Trap output cannot become commands
Stenographer has zero authority
Rust TUI remains replaceable
```

Add regression tests for any new trust boundary or adapter admission.

## 25. Release-readiness checks

The alpha10.3 release-prep branch adds `tests/test_release_wiring.py` to assert that:

- all public `NexusAPI` imports resolve to the provider-aware runtime;
- health exposes the complete admitted backend set;
- local-role operations are reachable;
- protocol/runtime/Python/TUI versions agree;
- pathological timeout integers fail closed before network activity;
- public JSONL numeric-boundary failures remain structured errors.

This test is intended to answer a simple question:

> **Is the architecture actually wired together, or do the files merely exist beside each other?**

## 26. Stable 2.0 is not yet declared

The project should not be described as stable 2.0 until its stated release criteria are satisfied. Current important unfinished areas include the broader instrument layer, persistent-world/migration hardening, explicit alpha11 shared-world demonstration, and beta-level adapter/security hardening.

Do not silently promote an alpha milestone to stable because CI is green.

## 27. Read next

For deeper work, inspect these files:

- [`README.md`](README.md) — human/operator entry point;
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — architecture rationale and world model;
- [`SECURITY.md`](SECURITY.md) — security posture and trust boundaries;
- [`THREAT_MODEL.md`](THREAT_MODEL.md) — enumerated threats, controls, residual risks;
- [`ROADMAP.md`](ROADMAP.md) — historical sequencing and future milestones;
- [`docs/API.md`](docs/API.md) — JSONL protocol details;
- [`docs/ADAPTERS.md`](docs/ADAPTERS.md) — adapter contract;
- [`docs/THIRD_PARTY_PROVIDERS.md`](docs/THIRD_PARTY_PROVIDERS.md) — reviewed cloud-provider surface;
- [`docs/LOCAL_MCP.md`](docs/LOCAL_MCP.md) — local AI and MCP role boundaries;
- [`docs/IRC_TUI.md`](docs/IRC_TUI.md) — Rust operator shell;
- [`docs/MODES_GEOMETRY.md`](docs/MODES_GEOMETRY.md) — world modes and topology;
- [`docs/COGNITIVE_MODES.md`](docs/COGNITIVE_MODES.md) — cognitive-room contracts;
- [`docs/FAILSAFE.md`](docs/FAILSAFE.md) — containment lifecycle;
- [`docs/CITIZEN_MODE.md`](docs/CITIZEN_MODE.md) and [`docs/CONSTITUTION.md`](docs/CONSTITUTION.md) — civic protocol;
- [`docs/TRAP_BASE.md`](docs/TRAP_BASE.md) — synthetic defensive domain;
- [`docs/STENOGRAPHER.md`](docs/STENOGRAPHER.md) — passive AI-action ledger;
- [`docs/GAMES.md`](docs/GAMES.md) — deterministic game state.

## 28. One-paragraph mental model

If you remember only one thing, remember this:

**NEXUS is a local-first control plane and persistent shared world that lets heterogeneous AI models participate through normalized actor boundaries while NEXUS—not the models—owns evidence, canonical state, voting, lineage, security boundaries, and governance. Models may reason, disagree, play, inhabit modes, use reviewed local/cloud transports, and contribute to a shared world; they do not gain extra authority from provider identity, size, tools, rhetoric, citizenship role-play, or deployment class.**
