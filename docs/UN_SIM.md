# `#un-sim` — Fictional UN Simulation Game

## Purpose

`#un-sim` is the first explicit game room in QSOL NEXUS.

It borrows the feel of old forum political-board simulations: players and model actors argue over invented states, crises, sanctions, support, diplomacy, absurd hypocrisy and propaganda while a small deterministic world engine owns the actual board.

Core rule:

> **Debate is cognition. Game state is substrate.**

The room is deliberately fictional. It is not a model of current international relations and is not a source of real-world policy or weapons-procurement advice.

## Room, mode and region

```text
IRC room: #un-sim
World Mode: game_un
World region: assembly
Region label: Assembly Hall
```

The built-in world geometry is `named-regions-v2` for this milestone.

`game_un` changes framing and gives the Council a fictional game context. It does not alter Council vote weight, consensus thresholds, evidence status, verification, the Equality Guard or the Secret Scrubber.

## Start a game

From the Rust IRC-style operator shell:

```text
/join #un-sim
/game new friday-night
```

A seed creates a deterministic initial board. Reusing the same seed produces the same initial content-addressed game state.

If no seed is supplied:

```text
/game new
```

NEXUS uses the built-in default seed.

## Initial fictional states

The first deck contains six deliberately invented countries:

```text
troutistan  — Republic of Troutistan
bananovia   — Commonwealth of Bananovia
kestrelia   — Federation of Kestrelia
sablemere   — Free State of Sablemere
wombatia    — People's Republic of Wombatia
pixelgrad   — Democratic Union of Pixelgrad
```

No arbitrary country names are accepted as action targets. The engine therefore does not silently turn a fictional board command into an operation against a real country.

At game creation, two deterministically selected fictional states begin at war.

## Board statistics

Each country carries abstract integer game state:

```text
economy
military
stability
influence
reputation
territory
sanctions
arms_imports
meme_heat
suspended
```

The global board also carries:

```text
turn
world_tension
un_legitimacy
wars
event_log
previous_state_ref
last_transition
```

These are game tokens. They are not measurements of real states, populations, forces or institutions.

## Actions

The initial action vocabulary is:

```text
sanction
support
aid
arms
meme
suspend
reinstate
recognize
mediate
do_nothing
```

Examples:

```text
/game act sanction troutistan bananovia
/game act support troutistan
/game act aid bananovia
/game act arms troutistan bananovia
/game act meme troutistan bananovia
/game act suspend troutistan bananovia
/game act reinstate troutistan
/game act recognize kestrelia
/game act mediate troutistan bananovia
/game act do_nothing
```

### Abstract arms trade

`arms` is intentionally a game-resource operation:

```text
military +1
economy  -1
world tension +2
arms_imports +1
```

It contains no weapon type, supplier, price, quantity, delivery route or procurement procedure.

If an action arms both sides of the same current war, the game also lowers `un_legitimacy` and records an `arms_hypocrisy` event.

### Meme campaigns

`meme` increases `meme_heat` and uses a SHA-256-derived deterministic roll to decide whether the campaign lands or backfires.

A backfire can improve the target's reputation and damage UN legitimacy. This is intentionally silly game logic, but its transition is still deterministic and replayable.

### Suspension and reinstatement

Suspension is stateful. Repeating `suspend` on an already suspended country does not repeatedly drain influence; repeating `reinstate` on a country already in the Assembly does not farm influence.

The engine records the procedural non-event instead.

## Turns and war

Advance the board with:

```text
/game turn
```

Each current war resolves one deterministic round from the immutable prior game-state reference and turn number.

Military and stability contribute to the abstract contest score. A SHA-256-derived roll adds bounded variation. Repeated advantage can shift one abstract territory point. Severe economic or stability exhaustion can force an armistice.

A deterministic world event is then added for the turn, such as a commodity boom, leaked cable, peace march, meme scandal or border rumor.

This is Risk-like game machinery, not a military simulation.

## Content-addressed lineage

Every game transition creates a new immutable `un_sim_game_state` object.

```text
game state A
    |
    | /game act ...
    v
game state B
    |
    | /game turn
    v
game state C
```

Each successor records:

```text
previous_state_ref
last_transition
```

The same state plus the same deterministic operation produces the same successor identity.

The event log retained inside each state is bounded because the immutable lineage already preserves historical state transitions.

## Council evidence

The current board is automatically attached to `#un-sim` as room-wide Council evidence.

When a game command produces a successor state, the TUI removes the previous board ref from the room evidence set and promotes the new one.

Therefore:

```text
old board ref  -> replaced
current board  -> shared evidence
```

Every Council member receives the same board snapshot.

A compact deterministic `content` representation is stored alongside the full game state. The generic NEXUS evidence path uses that compact view so the Council sees current wars, all countries, current statistics and the latest event without spending its model-readable evidence budget on old event detail.

Normal conversation does not mutate the board:

```text
<Trent> Should we suspend both belligerents or back Troutistan?
```

runs the Council against the current game evidence.

Only explicit game commands alter state:

```text
/game act suspend troutistan bananovia
```

A model can recommend an action. It cannot make the action authoritative merely by saying it happened.

## Direct JSONL API

The local stdio protocol exposes:

```text
game.un.catalog
game.un.new
game.un.inspect
game.un.act
game.un.turn
```

Example:

```json
{"operation":"game.un.new","seed":"friday-night"}
```

Then:

```json
{"operation":"game.un.act","game_ref":"object:<sha256>","action":"meme","targets":["troutistan"]}
```

The control transport remains local JSONL over stdio. The game feature does not introduce a game server, IRC server, browser service or peer-to-peer networking.

## Claim boundary

Every game state explicitly records:

```text
fictional_simulation = true
real_world_policy_claim = false
real_weapon_procurement = false
game_stats_are_real_world_measurements = false
```

So the intended interpretation is narrow:

```text
fictional strategy game       yes
deterministic NEXUS state     yes
Council role-play/debate      yes
memes and absurd diplomacy    yes
real geopolitical forecast    no
real military simulation      no
real weapons procurement      no
real-country action engine    no
```

The Assembly Hall can be ridiculous. The substrate still has to know what is real.