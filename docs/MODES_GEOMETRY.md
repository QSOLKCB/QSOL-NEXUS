# NEXUS World Modes and Geometry

## Purpose

NEXUS should be useful for serious analysis without becoming a permanently serious room.

World Modes let the Human Operator choose the kind of cognitive activity taking place. The Geometry Layer gives that activity an explicit place in the shared world.

The separation is deliberate:

```text
MODE
  = how a session is framed
  = reasoning posture, context and tone

GEOMETRY
  = where the session is situated
  = named region, coordinate and adjacency
```

Neither concept changes Council authority, evidence status, verification, secret handling, or claim boundaries.

> **The mode can change the vibe. It cannot change the vote.**

## Current built-in world

```text
                         ARCHIVE
                       Historical
                         (-2,1)
                        /      \
                       /        \
                 AGORA ---------- OBSERVATORY
                Cultural           Analytical
                 (0,2)               (0,0)
                      \             /   |
                       \           /    |
                        COMMONS ----+    |
                      Meme/Casual    \   |
                         (2,1)        \  |
                                    ASSEMBLY HALL
                                    UN Simulation
                                       (0,-2)
```

The map remains intentionally tiny. Correct semantics and stable contracts matter more than producing a huge fictional universe.

## Modes

### Analytical — Observatory

Evidence-first technical reasoning.

Actors are asked to:

- separate observation from interpretation;
- make assumptions and unknowns explicit;
- preserve falsifiers and competing hypotheses;
- prefer the narrowest conclusion supported by evidence.

This remains the default mode.

### Historical — Archive

Chronology and source context.

Actors are asked to:

- preserve temporal order;
- distinguish primary facts from later interpretation;
- notice missing or conflicting sources;
- avoid treating present-day categories as timeless;
- keep alternative historical readings visible when evidence is incomplete.

Historical Mode does not grant the model a hidden historical database. Its claims still depend on supplied or retrieved evidence.

### Cultural — Agora

Context-sensitive cultural reasoning.

Actors are asked to:

- distinguish local norms from universal claims;
- preserve ambiguity where it carries social meaning;
- notice insider/outsider interpretations;
- compare cultural frames without automatically ranking them;
- recognize that the same behavior can build cohesion in one context and exclusion in another.

This is particularly useful for humor, slang, ritual, media, subcultures, social norms and cross-cultural comparison.

### Meme / Casual — Commons

Playful interaction, irreverence and meme-aware reasoning.

Actors may:

- joke;
- use colloquial language;
- riff on absurdity;
- puncture pretension;
- treat banter as part of the social context.

But:

```text
joke != evidence
confidence != verification
status joke != extra vote
meme consensus != factual consensus
```

The Equality Guard remains active. The Secret Scrubber remains active. Evidence and verification rules remain unchanged.

### UN Simulation Game — Assembly Hall

`game_un` is the first explicit game mode.

It frames a fictional UN-style strategy simulation with invented states, deterministic crises, abstract Risk-like statistics and meme-friendly diplomacy.

Actors may debate:

- sanctions;
- political/economic support;
- humanitarian aid;
- recognition;
- suspension or reinstatement;
- mediation;
- abstract arms-trade game actions;
- meme campaigns;
- doing absolutely nothing and blaming the committee process.

The critical separation is:

```text
Council/model output -> proposals, arguments and role-play
/game operation       -> authoritative game-state transition
```

The current game board is shared Council evidence, but narration never mutates the board merely because a model says something happened.

All countries, wars, territory values and arms packages are fictional game objects. See [`UN_SIM.md`](UN_SIM.md).

## Why runtime modes, not just persona prompts?

NEXUS records the selected mode as protocol state rather than pretending a model prompt can perfectly enforce behavior.

A compliant adapter receives mode guidance, but the world owns the mode identity. Model output remains untrusted input.

This matters because chat-trained models may retain output and conversational priors even under aggressive prompt-level constraints. NEXUS therefore treats prompt instructions as guidance and keeps procedural rules in the runtime.

The same reasoning applies especially strongly to a game room: a model can role-play an ambassador, but the runtime owns whether a country is actually sanctioned, suspended, at war or holding a territory token.

## Geometry semantics

The Geometry Layer is an **operational topology**, not a physical claim.

```text
WorldRegion
├── region_id
├── label
├── x
├── y
├── neighbors[]
└── description
```

Properties:

- coordinates are small deterministic integers;
- adjacency is explicit and symmetric;
- hop distance is computable;
- every built-in mode maps to exactly one region;
- the current built-in geometry identifier is `named-regions-v2`;
- the content-derived `topology_ref` remains separate from that human-readable identifier.

NEXUS does **not** claim that culture, history, memes, games or model cognition literally occupy Euclidean coordinates. The geometry is a computational substrate for placement, relation, navigation and later visualization.

## World presence

A Council session creates a content-addressed presence object before the session identity is frozen:

```text
world_presence
├── mode_id
├── mode_label
├── region_id
├── region_label
├── coordinates
├── member_ids[]
├── question_ref
├── geometry_id
└── geometry_topology_ref
```

The Council session then references that presence object.

This means two otherwise identical Councils run in different modes are different sessions with different lineage, while their constitutional voting mechanics remain identical.

## Examples

Cultural Council:

```json
{
  "operation": "council.run",
  "question": "Why does this joke work in one culture and fail in another?",
  "mode": "cultural",
  "members": [
    {"member_id": "A", "model_id": "mock-a"},
    {"member_id": "B", "model_id": "mock-b"},
    {"member_id": "C", "model_id": "mock-c"}
  ]
}
```

NEXUS resolves:

```text
mode: cultural
region: agora
coordinates: (0,2)
```

Game Council:

```json
{
  "operation":"council.run",
  "question":"Should the Assembly suspend both belligerents?",
  "mode":"game_un",
  "evidence_refs":["object:<current-game-state>"],
  "members":[
    {"member_id":"A","model_id":"mock-a"},
    {"member_id":"B","model_id":"mock-b"},
    {"member_id":"C","model_id":"mock-c"}
  ]
}
```

resolves to Assembly Hall at `(0,-2)` and keeps exactly the same Council vote mechanics.

## API

World-mode/geometry operations:

```text
world.modes
world.geometry
world.geometry.distance
```

Example:

```json
{
  "operation": "world.geometry.distance",
  "source_region_id": "archive",
  "target_region_id": "assembly"
}
```

returns the shortest topological hop distance in the current named-region graph.

The game itself is exposed separately through the `game.un.*` operations documented in [`API.md`](API.md) and [`UN_SIM.md`](UN_SIM.md).

## Geometry-inspired ideas deliberately deferred

The uploaded research material suggests richer ideas such as admissibility, bottlenecks, shattered regions, perturbation sensitivity, branching multiplicity and transport cost.

Those are useful design inspirations, but they should be added only when NEXUS has operational measurements that justify them.

Possible later geometry telemetry:

```text
branching multiplicity
response-diversity / Council entropy
mode-transition cost
recovery after perturbation
loop / basin indicators
control-gain proxies
```

A later implementation may label regions or paths as bottlenecked or fragmented **only from measured NEXUS behavior**. It should not treat an analogy to spectral geometry as a measured spectrum.

## Future expansion

Potential regions can be added without changing the constitutional core:

```text
Workshop      creative / making
Gallery       visual / aesthetic
Soundstage    sonification / music
Laboratory    experiments
Library       long-form research
Arena         adversarial red-team sessions
Garden        exploratory hypothesis growth
```

Likewise, future user-defined modes may map onto existing or new regions.

Game rooms may also grow into separate deterministic simulations without granting those simulations authority over evidence, verification or Council voting.

The map should grow because useful behavior requires it, not because a large ontology looks impressive.
