# HERESY MUD — The Great Under-Moderated Dungeon

## Purpose

HERESY MUD is NEXUS's first deterministic multi-avatar dungeon game.

It borrows the social grammar of old BBS/MUD games—shared players, realms, rooms, loot, combat, persistence and terminal commands—while building a new NEXUS-native world out of the existing QSOLKCB/DORK and QSOLKCB/HERESY satire.

> **Narration is role-play. Dungeon state is substrate.**

A model may say it opened a vault, killed a dragon, installed seventeen packages, or achieved enlightenment through YAML. None of those statements change the game. Only a validated `game.mud.act` transition creates the next authoritative state.

## NEXUS placement versus MUD rooms

These are deliberately separate concepts:

```text
NEXUS world geometry
    dungeon region
        |
        v
HERESY MUD state
    Beige Realm
    Framework Realm
    Heresy Realm
        |
        +-- bbs_gate
        +-- terms_catacomb
        +-- venture_tavern
        +-- microservice_maze
        +-- node_modules_pit
        +-- moderation_bridge
        +-- cobol_vault
        +-- punchcard_crypt
        +-- nixos_cathedral
        +-- forceos_shrine
        +-- dependency_cache
```

The NEXUS `dungeon` coordinate is operational world placement. It does not claim that the internal MUD map shares those coordinates.

## Realms

```text
Beige Realm      -> BBS/login/TOS/venture-capital ruins
Framework Realm  -> microservices, node_modules and moderation infrastructure
Heresy Realm     -> COBOL, punch cards, declarative scripture and FORCEOS '38
```

The realms are fictional game groupings. They are not provider classes or Council authority levels.

## Avatars

A new MUD receives an explicit list of player IDs. The Rust TUI uses the human operator nick plus the current model roster.

Example:

```text
Trent
Alpha
Beta
Grok
```

Each avatar owns independent game state:

```text
room_id
hp / max_hp
clout
score
alive
```

Items have exactly one authoritative location at a time: room, player, NPC, or consumed.

The initial TUI lets the human operator proxy any registered avatar:

```text
/mud as Grok n
/mud as Alpha take large_trout
/mud as Beta attack yaml_necromancer large_trout
```

This is an operator control surface, not evidence that the named model independently chose that action. Future autonomous model action would require a separate explicit adapter/game contract.

## Commands

Start and inspect:

```text
/join #mud
/mud new [seed]
/mud look [player]
/mud status [player]
/mud who
/mud inventory [player]
```

Movement:

```text
/mud n
/mud s
/mud e
/mud w
/mud go north
```

Objects:

```text
/mud take large_trout
/mud get large_trout
/mud drop large_trout
/mud use left_pad_talisman
```

Combat and social warfare:

```text
/mud attack yaml_necromancer
/mud attack content_moderator_troll large_trout
/mud shitpost brand_intern_paladin
/mud ratio content_moderator_troll
/mud rest
```

`SHITPOST` and `RATIO` are intentionally inherited as concepts from DORK's internet-parody command vocabulary. In HERESY MUD they are deterministic game actions with bounded HP/clout effects, not moderation or network operations.

## Items

The initial dungeon includes:

```text
large_trout
left_pad_talisman
yaml_scroll
nft_rock
immutable_receipt
punch_card
banhammer
zero_dependency_crown
```

The EBCDIC punch card is a game capability token required to enter the final Dependency Dragon Cache.

No item represents a real credential, weapon, financial asset or network capability.

## NPCs

```text
brand_intern_paladin
    cheerful, non-hostile, quarterly-targeted

yaml_necromancer
    hostile configuration undead

content_moderator_troll
    hostile; carries the legacy banhammer

dependency_dragon
    final hostile; guards the Zero-Dependency Crown
```

Attacking a non-hostile NPC costs clout. Hostile surviving NPCs may retaliate.

## Deterministic action resolution

MUD actions do not use wall-clock randomness.

For a bounded random-looking outcome, NEXUS hashes the complete immutable prior game state plus an operation label:

```text
R = SHA-256(canonical_json({ prior_state, action_label }))
roll = prefix(R) mod N
```

Therefore:

```text
same prior state
+ same player
+ same action
+ same arguments
= same resulting game object
```

Combat completion order, wall time and host RNG do not enter game identity.

## State lineage

Every mutating action creates a new `mud_game_state` object.

```text
mud_state_0
    |
    | game.mud.act
    v
mud_state_1
    previous_state_ref -> mud_state_0
    |
    v
mud_state_2
```

The prior object remains immutable in the WorldStore.

The Rust TUI keeps only the latest MUD state ref in `#mud` room evidence. Removing that ref with `/unref` also makes `/mud` treat the game as no longer current, preserving the shared-evidence invariant used by the UN simulation.

## Council evidence

The complete structural MUD object is durable state. A deterministic `content` representation is derived from it for model-readable Council evidence.

The view includes:

```text
turn / quest status
all avatar positions and HP
inventories
currently occupied room exits/items/NPCs
all NPC survival/HP status
recent events
```

Validation recomputes this view and rejects a state if the stored text differs. A crafted object therefore cannot retain valid structural state while replacing the Council-facing board with invented prose.

## Claim boundary

Every valid MUD state requires exactly these boundaries:

```text
fictional_simulation = true
real_world_policy_claim = false
real_weapon_procurement = false
game_stats_are_real_world_measurements = false
model_narration_mutates_state = false
network_mud_server = false
```

This alpha is not a network-facing MUD daemon. The Rust operator shell and Python runtime remain local and communicate over JSONL/stdio.

## DORK and HERESY inheritance

HERESY MUD does not embed DORK's Z-machine story or a Commodore emulator.

It reuses project ideas at the NEXUS world-protocol level:

```text
DORK
  -> interactive-fiction grammar
  -> internet-parody vocabulary
  -> trout / shitpost / ratio / moderator-troll energy

HERESY
  -> deliberately obsolete implementation aesthetics
  -> COBOL fixed-record certainty
  -> EBCDIC punch-card absurdity
  -> NixOS / Arch scripture jokes
  -> FORCEOS '38 / tiny-microkernel ethos
  -> zero-dependency final objective
```

The result is a new deterministic shared-world game rather than a port of either repository.
