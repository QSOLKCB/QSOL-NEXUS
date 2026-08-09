# NEXUS Human/AI Games and DORK v2

## Scope

NEXUS provides four deterministic table games for human and AI seats:

| Game | Room | Runtime schema | Seats |
|---|---|---|---|
| UNO | `#uno` | `nexus-uno/1` | 2–8 human/AI players |
| Monopoly | `#monopoly` | `nexus-monopoly/1` | 2–8 human/AI players |
| 500 | `#500` | `nexus-five-hundred/1` | exactly four human/AI players, opposite-seat partners |
| Blackjack | `#blackjack` | `nexus-blackjack/1` | 1–7 human/AI players plus the deterministic dealer |

It also provides one deliberately separate single-player adventure:

| Game | Room | Runtime schema | Seats |
|---|---|---|---|
| DORK v2: The Great Under-Moderated NEXUS | `#dork` | `nexus-dork-v2/1` | exactly one human operator; no AI avatar |

The table games label each registered seat `human` or `ai`. In the Rust shell,
the current human nick is the human seat and the current model roster supplies
the AI seats. The operator can submit a validated action for any table seat with
the explicit `as <model-nick>` form. Models may also inspect the public board,
receive their player-specific view through the operator boundary, and propose a
move in the room.

An AI seat does not grant a model tool authority. A model sentence such as “I
play the red seven” is still prose until the corresponding `game.*.act`
operation is submitted and accepted.

> **Models can play a seat. Models do not own the table.**

## Shared substrate contract

Every game uses the same NEXUS laws:

- the initial state and every successor are immutable `object:<sha256>` world objects;
- each successor records `previous_state_ref` and a typed `last_transition`;
- decks, shoes, dice and card order use SHA-256 domain-separated deterministic
  derivation from a scrubbed seed; the Blackjack dealer follows a closed total rule;
- there is no process RNG, wall clock, network service, remote dealer or model-generated code execution;
- the same state reference plus the same validated action produces the same successor reference;
- card games conserve their canonical decks/shoe, property and adventure
  ledgers are validated, and every derived public-content check rejects forged state before transition;
- the active Trap Base mutation gate blocks every new-game and action operation;
- public Council evidence contains a bounded public table view, not hidden hands or the dealer hole card;
- `player_view` returns the requesting seat's private hand and relevant legal context;
- provider identity, model size, prestige and benchmark claims never change rules or turn order.

The local JSONL control process remains a trusted operator boundary. It can
inspect authoritative world objects, so player views are a game-information
contract, not a multi-tenant access-control system.

## UNO profile

NEXUS UNO uses a canonical 108-card deck:

- four colors;
- one zero per color;
- two each of 1–9, Skip, Reverse and Draw Two per color;
- four Wild and four Wild Draw Four cards;
- seven cards per player.

The opening discard is deterministically selected as a numeric colored card so
no unresolved action occurs before the first turn. Wild Draw Four is rejected
when the player holds the active color. After drawing, the player may play only
that drawn card or pass. Reverse acts as Skip at a two-player table. Empty draw
piles recycle the discard pile beneath the visible top card through a new
domain-separated deterministic permutation.

```text
/join #uno
/uno new reverse-card-night
/uno status
/uno play red-7-a
/uno play wild-2 blue
/uno draw
/uno pass
/uno as Alpha play yellow-reverse-a
```

## Monopoly profile

NEXUS MONOPOLY: Substrate Edition implements property purchase, rent, complete
color groups, even building and selling, railways, utilities, mortgages,
unmortgaging, taxes, deterministic Chance/Community Patch cards, doubles,
three-doubles Jail, bail, bankruptcy and GO salary.

The board is an original forty-square software-satire board. It does not embed
commercial board artwork, text or data. Compact NEXUS house rules deliberately
leave a declined property unowned rather than opening an auction, and do not
implement player-to-player trades. A bounded 400-turn table closes by net worth
so a deterministic replay cannot run forever.

```text
/join #monopoly
/monopoly new beige-property-night
/monopoly roll
/monopoly buy
/monopoly pass
/monopoly build cobol_close
/monopoly mortgage dialup_rail
/monopoly as Alpha roll
```

## 500 profile

NEXUS 500 implements the four-player Australian partnership core:

- a 43-card deck: Joker; black fours; all fives through aces;
- ten cards per player and a three-card kitty;
- opposite-seat partnerships;
- ascending contracts from `6S` through `10NT`;
- a three-pass auction close after a bid and deterministic redeal after four opening passes;
- declarer pickup and exactly three discards;
- right bower, left bower, Joker and effective-suit following;
- ten tricks, contract scoring, defender trick points, and ±500 game boundary.

This bounded first profile intentionally excludes Misère and Open Misère. In a
no-trump contract the Joker is the highest card and, when led, does not impose a
printed-suit follow requirement.

```text
/join #500
/500 new adelaide-card-night
/500 as Alpha bid 7H
/500 as Beta pass
/500 as Gamma discard hearts-5 clubs-A joker
/500 as Trent play spades-J
```

## Blackjack profile

NEXUS Blackjack uses fictional chips and a six-deck deterministic shoe. The
dealer has no model adapter and no discretion:

```text
dealer total < 17  -> hit
dealer total >= 17 -> stand
soft 17            -> stand
```

The engine deals, hides the hole card in public evidence, resolves the dealer
automatically after all active seats, pays natural Blackjack at 3:2, and
supports Hit, Stand and Double. Bets are even whole-chip amounts so 3:2 payouts
remain exact integers. Splits, surrender, insurance, side bets, real money and
external gambling services are outside this profile. A multi-seat table closes
when one funded competitor remains; a single seat can continue against the
dealer. Any table still open after 250 rounds closes by bankroll so replay stays
bounded, and the dealer wins if every seat is broke.

```text
/join #blackjack
/blackjack new canonical-shoe-night
/blackjack bet 10
/blackjack as Alpha bet 20
/blackjack hit
/blackjack stand
/blackjack double
/blackjack new_round
```

## DORK v2 — human only

DORK v2 opens in a field west of a suspiciously familiar white startup, beside
a small mailbox. Opening the mailbox destroys the illusion: this is a new
NEXUS-native version of
[`QSOLKCB/DORK`](https://github.com/QSOLKCB/DORK), full of conversion funnels,
terms scrolls, microservice mazes, `node_modules`, an AI wrapper, the Content
Moderator Troll, the NixOS Cathedral, a punch card and the Zero-Dependency Crown.

It uses original Python adventure state and prose. NEXUS does not embed or
execute a Zork story binary, Z-machine interpreter, or upstream DORK ZIL source.

DORK has exactly one `human_operator_id`. There is no `as` command, AI hand,
model avatar, AI inventory or AI score. Models in `#dork` may discuss clues, but
only the bound human's explicit operation can move, take, open, ratio, mute,
prompt, deploy or touch grass.

```text
/join #dork
/dork new mailbox-with-prior-art
/dork look
/dork open mailbox
/dork take dork_leaflet
/dork read dork_leaflet
/dork n
/dork open window
/dork go in
/dork inventory
/dork shitpost
/dork ratio troll
/dork mute troll
/dork prompt
/dork deploy
/dork grass
```

## JSONL API

Each table game exposes:

```text
game.<id>.catalog
game.<id>.new
game.<id>.inspect
game.<id>.act
```

where `<id>` is `uno`, `monopoly`, `500` or `blackjack`.

Create a mixed human/AI UNO table:

```json
{
  "operation": "game.uno.new",
  "seed": "reverse-card-night",
  "players": ["Trent", "Alpha", "Beta", "Gamma"],
  "human_players": ["Trent"]
}
```

Inspect one seat without promoting its hand into public Council evidence:

```json
{
  "operation": "game.uno.inspect",
  "game_ref": "object:<sha256>",
  "player_id": "Alpha"
}
```

Submit a move:

```json
{
  "operation": "game.uno.act",
  "game_ref": "object:<sha256>",
  "player_id": "Alpha",
  "action": "play",
  "args": ["blue-9-a"]
}
```

DORK exposes the same verbs under `game.dork.*`, but creation accepts only one
`human_player_id` and every later action must use that same identifier.

## Names and affiliation

The familiar game names identify compatible rules families. This project is
not affiliated with or endorsed by the owners of those game brands. NEXUS uses
plain text, an original satirical property board, original DORK prose and no
commercial artwork or packaged game assets.
