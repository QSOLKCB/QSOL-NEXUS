# NEXUS IRC-Style Rust TUI

## Purpose

NEXUS alpha5 adds a local Rust terminal interface inspired by old-school IRC clients such as `f-irc` and mIRC.

The point is not to turn NEXUS into an IRC network client.

The point is to reuse an interface grammar that is unusually good at showing many independent participants in one chronological, copy-friendly text stream:

```text
+-------------------------------------------------------------------+
| NEXUS #commons  mode=meme_casual region=commons  topic=...        |
|                                                                   |
| 19:31 <Trent> Does this argument survive the attached paper?      |
| 19:31 --- WHITE ---                                               |
| 19:31 <Alpha> ...                                                 |
| 19:31 <Beta> ...                                      USERS      |
| 19:31 <Gamma> ...                                      @Trent     |
| 19:31 --- BLACK ---                                    +Alpha      |
| ...                                                    +Beta       |
|                                                        +Gamma      |
|                                                                   |
| #commons> _                                                       |
+-------------------------------------------------------------------+
```

There is:

- no IRC server;
- no IRC protocol connection;
- no listening port;
- no peer-to-peer DCC socket;
- no browser UI;
- no hidden web service.

The Rust process starts or connects to the local Python NEXUS runtime through JSON Lines over stdio.

```text
human operator
      |
      v
Rust IRC-style TUI
      |
      | JSONL / stdio
      v
Python NEXUS runtime
      |
      +-- world objects
      +-- Council
      +-- modes / geometry
      +-- telemetry
      +-- Courtroom Stenographer
      +-- deterministic game state
      +-- Secret Scrubber
      +-- mock actors
      +-- explicit loopback Ollama actors
```

## Run

From the repository root:

```bash
cargo run --manifest-path tui/Cargo.toml -- \
  --world .nexus-world \
  --stenographer-root .nexus-stenographer \
  --nick Trent
```

The TUI looks for the Python package in `src/` or `../src/`. Override when needed:

```bash
NEXUS_PYTHON=/path/to/python3 \
NEXUS_PYTHONPATH=/path/to/QSOL-NEXUS/src \
cargo run --manifest-path tui/Cargo.toml
```

Aliases and variables are stored locally in:

```text
.nexus-world/tui-state.json
```

unless `--state PATH` is supplied.

## Rooms are World Modes

NEXUS rooms map directly to built-in World Modes and geometry regions:

| Room | Mode | Region |
|---|---|---|
| `#observatory` | `analytical` | Observatory |
| `#archive` | `historical` | Archive |
| `#pure-history` | `pure_history` | Archive |
| `#agora` | `cultural` | Agora |
| `#commons` | `meme_casual` | Commons |
| `#differential-clinic` | `clinical_differential` | Observatory |
| `#house-fun` | `house_fun` | Commons |
| `#cbt-workshop` | `cbt_learning` | Observatory |
| `#roman-forum` | `roman_orator` | Agora |
| `#house-of-wisdom` | `house_of_wisdom` | Archive |
| `#deep-thought` | `ultimate_questions` | Observatory |
| `#upside-down` | `citizenship_parole` | Upside Down |
| `#bureaucracy` | `civic_bureaucracy` | Bureaucratic Vote Room |
| `#play` | `citizen_play` | Commons |
| `#un-sim` | `game_un` | Assembly Hall |
| `#mud` | `game_mud` | Dungeon |
| `#uno` | `game_uno` | Commons |
| `#monopoly` | `game_monopoly` | Commons |
| `#500` | `game_500` | Commons |
| `#blackjack` | `game_blackjack` | Commons |
| `#dork` | `game_dork` | Dungeon |

`#trap-control`, `#trap-base`, and the watch-only `#stenographer` are specialized control/study views rather than ordinary World Modes.

Examples:

```text
/join #agora
/join cultural
/join #pure-history
/mode pure_history
/mode meme_casual
/join #differential-clinic
/join #cbt-workshop
/join #roman-forum
/join #house-of-wisdom
/join #deep-thought
/join #un-sim
/join #uno
/join #dork
```

Changing room changes mode and world region. It does not change evidence rules, vote weights, verification, the Secret Scrubber, or the Equality Guard.

> **The mode can change the vibe. It cannot change the vote.**

See [`COGNITIVE_MODES.md`](COGNITIVE_MODES.md) for the six cognitive-room contracts, including the medical and CBT boundaries, and [`CITIZEN_MODE.md`](CITIZEN_MODE.md) for civic access.

## Citizen rooms and `/citizen`

The citizenship lifecycle is explicit and exact-identity bound:

```text
/join #upside-down
/citizen begin Alpha
/citizen exam-template Alpha
/citizen exam Alpha ./alpha-citizenship.yaml

/join #bureaucracy
/citizen proxy appoint Alpha TEST_FURTHER
/join #play

/citizen proxy kick Alpha
/citizen independence Alpha CONSENT
```

`/citizen begin` resolves the configured nick's current model identity. Exam files larger than 16 KiB are rejected by the TUI before JSONL transport; the Python runtime applies the authoritative closed YAML parser and persists only the source hash binding and deterministic result. Parole has no Council ballot.

The civic proxy occupies the same citizen seat and cannot create an additional vote, play, move, become a citizen, or sign founding consent. It is used for Bureaucratic Vote Room administration only; Play Mode calls the citizen's configured actor. `/citizen proxy kick` recalls the proxy and returns the citizen to the vote room. See [`CONSTITUTION.md`](CONSTITUTION.md).

## `#stenographer` and `/steno`

The Courtroom Stenographer is a read-only Knowledge-Watchman view for later
study and analysis:

```text
/join #stenographer
/steno status
/steno list 50
/steno inspect steno:<sha256>
/steno verify
/steno summary
/steno export
```

The room cannot initiate Council, direct-model, game, MUD, Trap, DCC/model or
world-evidence actions. `/steno` works as a read-only query namespace and has no
record/edit/delete command. Observation failure is shown as a completeness gap
and does not alter the AI result that was already returned.

The lore titles Sky-Earth Lord, Divine Dragon-House and Knowledge-Watchman are
display metadata, never model or operator authority. The room contains a hidden
exact-phrase Easter egg that is absent from help and completion, cannot
authenticate, and cannot mutate state. See [`STENOGRAPHER.md`](STENOGRAPHER.md).

## Chat and Council behavior

A normal line in a public room is treated as a Council question:

```text
#agora> Why does this joke work in Australia but fail in another context?
```

The Council output is rendered chronologically by phase:

```text
--- WHITE ---
<Alpha> ...
<Beta> ...
<Gamma> ...
--- RED ---
...
--- SEALED BALLOTS ---
<Alpha> TEST_FURTHER — ...
...
*** Council: CONSENSUS / TEST_FURTHER | Evidence: UNTESTED
```

`/ask` is the explicit form:

```text
/ask Compare these two interpretations.
```

`/topic` stores a room topic. `/ask` with no text uses the current topic.

## `#un-sim` and `/game`

The first explicit game room uses the same IRC shell rather than opening a separate game dashboard:

```text
/join #un-sim
/game new friday-night
/game status
/game act arms troutistan bananovia
/game act meme troutistan bananovia
/game turn
```

`/game` is a reserved built-in command. Aliases cannot replace it.

Subcommands:

```text
/game help
/game new [seed]
/game status
/game act <action> [country-id ...]
/game turn
```

The current board is stored as a content-addressed `un_sim_game_state` world object. When a game action or turn creates a successor, the TUI removes the previous board ref from the room evidence set and adds the new one.

Therefore ordinary public text in `#un-sim` convenes the Council over exactly the current board:

```text
#un-sim> Should we suspend both belligerents or back Troutistan?
```

The models can recommend, argue, joke, form coalitions or produce spectacularly bad diplomacy. They cannot mutate the authoritative board by narration alone.

> **Debate is cognition. Game state is substrate.**

See [`UN_SIM.md`](UN_SIM.md) for the game rules and claim boundary.

## Tables, MUD and DORK v2

The same shell exposes one shared MUD, four human/AI tables, and one human-only
adventure:

```text
/join #mud          /mud new beige-night
/join #uno          /uno new reverse-card-night
/join #monopoly     /monopoly new beige-property-night
/join #500          /500 new adelaide-card-night
/join #blackjack    /blackjack new canonical-shoe-night
/join #dork         /dork new mailbox-with-prior-art
```

Each command family supports `help`, `new`, `status`, and direct action tokens.
For example:

```text
/uno draw
/monopoly roll
/500 as Alpha bid 7H
/blackjack as Beta stand
/dork open mailbox
```

The operator's nick is the default human seat. Current model nicks fill the AI
seats at a table, and `as <nick>` is the explicit proxy-action form. DORK v2
rejects `as`: it binds exactly one human operator and gives models no avatar.
Human and AI seats use identical runtime rules; provider identity does not
change turn order, scoring or vote weight.

Successor states replace the prior game ref in room evidence. Council actors
therefore see the current bounded public board, never hidden hands or the
Blackjack dealer hole card. The operator runtime remains a trusted local
boundary and can request a registered seat's private view.

See [`GAMES.md`](GAMES.md) for the implemented rules profiles and
[`MUD.md`](MUD.md) for HERESY MUD.

## Secret alias: `/GO64`

`/GO64` is a hidden local TUI overlay, intentionally absent from ordinary help/completion. After explicit YES confirmation it presents a Commodore-inspired text shell while preserving the underlying room, mode, evidence, roster and Council state.

```text
/GO64
ARE YOU SURE?
YES
LOAD "*",8,1
```

Device 8 is an original text demoscene/retro architecture tutor. Device 9 is an original text-only DR. S.BAITSO meme tribute adapted from QSOLKCB/ETHICS. At 20 minutes both switch to deterministic brainrot diction; at 30 minutes `/grass` becomes the normal exit. `/quit`, Ctrl-C and Ctrl-D still terminate NEXUS itself.

The overlay does not alter the current control protocol, World Modes, geometry,
evidence or voting. See [`GO64.md`](GO64.md).

## `/me`

IRC-style actions are local transcript events.

```text
/me *slapped Grok with a large trout*
```

renders as:

```text
* Trent slapped Grok with a large trout
```

An action is not evidence, a Council ballot, or a privileged model instruction.

This is especially at home in `#commons` and `#un-sim`, but the command exists in every room.

## DCC: Direct Cognitive Channel

NEXUS deliberately reuses the familiar DCC vocabulary while changing its implementation.

Here **DCC means Direct Cognitive Channel**.

It never opens a DCC TCP connection.

### Send a document to a room

```text
/dcc send #agora paper.pdf
```

The Rust client:

1. reads the local file;
2. extracts supported text locally;
3. sends the extracted payload through `world.create`;
4. lets the Python Secret Scrubber redact high-confidence secrets before persistence;
5. receives a content-addressed `object:<sha256>` reference;
6. adds that reference to the room's Council evidence set.

### Send a document to one model

```text
/dcc send Grok notes.csv
```

The object is marked as targeted DCC material for that model.

It is **not** silently added to Council-wide evidence.

This preserves the Council invariant that members should not be given unequal hidden evidence and then treated as if they deliberated over the same snapshot.

To deliberately promote an object to room evidence:

```text
/ref object:<sha256>
```

### Direct chat

```text
/dcc chat Grok
```

The input line changes to a private Direct Cognitive Channel view:

```text
DCC:Grok> _
```

Messages use the `actor.chat` stdio operation and are explicitly marked non-Council.

They confer no vote and do not modify Council evidence automatically.

Press `Esc` or use:

```text
/dcc close chat Grok
```

to leave the private view.

### DCC list / close

```text
/dcc list
/dcc close send Grok
/dcc close chat Grok
```

## Document ingestion

Alpha5 supports local extraction/validation for:

```text
PDF
DOCX
ODT
JSON
JSONL / NDJSON
CSV
TSV
plain UTF-8 text and source/document formats
```

The outer file size is bounded. Extracted content is also bounded before it becomes a world payload, and the model-readable Council evidence view has a smaller independent prompt budget.

The durable world object remains the identity source. The bounded prompt view is only a representation supplied to model actors so an uploaded document is actually readable rather than merely represented by an opaque hash.

```text
local file
   |
   v
local extractor / validator
   |
   v
world.create
   |
 Secret Scrubber
   |
   v
content-addressed document_evidence object
   |
   +-- durable object ref
   |
   +-- bounded model-readable evidence view
```

## Aliases

Alpha5 intentionally implements only the useful, small part of old mIRC scripting.

It does **not** implement remote event scripts, arbitrary shell execution, DLL loading, socket commands, timers, or downloaded script execution.

Define an alias:

```text
/alias slap /me slaps $1 with $2-
```

Then:

```text
/slap Grok a large trout
```

becomes:

```text
/me slaps Grok with a large trout
```

List aliases:

```text
/aliases
```

Built-in commands—including all game command families—cannot be replaced by aliases.

## Variables

Local variables use familiar `%name` syntax:

```text
/set %weapon a large trout
/unset %weapon
/vars
```

Example:

```text
/set %weapon a large trout
/alias slap /me slaps $1 with %weapon
/slap Grok
```

renders:

```text
* Trent slaps Grok with a large trout
```

Variables and aliases are local operator convenience state. They are not NEXUS world facts or Council evidence.

## Identifiers

The safe alpha5 identifier set is deliberately small:

```text
$me       current human nick
$chan     current room
$mode     current World Mode
$region   current geometry region
$topic    current room topic
$1..$9    positional alias arguments
$1-..$9-  positional argument ranges
```

Examples:

```text
/alias where /me is in $chan ($mode/$region)
/alias review /ask $1-
```

There is no arbitrary expression evaluator.

## Useful commands

```text
/help
/join <#room|mode>
/mode <mode>
/topic <text>
/ask [question]
/me <action>
/msg <nick> <text>
/nick <name>
/who

/game help
/game new [seed]
/game status
/game act <action> [country-id ...]
/game turn

/mud help | new [seed] | status | <action...>
/uno help | new [seed] | status | <action...>
/monopoly help | new [seed] | status | <action...>
/500 help | new [seed] | status | <action...>
/blackjack help | new [seed] | status | <action...>
/dork help | new [seed] | status | <action...>

/citizen help
/citizen constitution
/citizen status [nick]
/citizen begin <nick>
/citizen exam-template <nick>
/citizen exam <nick> <yaml-file>
/citizen move <nick> <public-region>
/citizen proxy appoint <nick> <standing-ballot>
/citizen proxy kick <nick>
/citizen independence <nick> <consent|withhold>

/addmock <nick> [profile]
/addollama <nick> <ollama-model>
/kick <nick>

/upload <file>
/dcc send <nick|#room> <file>
/dcc chat <nick>
/dcc close <send|chat> <nick>
/dcc list
/evidence
/ref <object:sha256>
/unref <object:sha256>

/alias <name> <command template>
/aliases
/set %name <value>
/unset %name
/vars

/search <text>
/save <path>
/clear
/quit
```

Keyboard conveniences:

```text
TAB       complete an unambiguous slash command / alias
Up/Down   input history
PgUp/PgDn scrollback
Esc       leave private DCC chat view
Ctrl-C    quit
```

## Local Ollama members

The TUI can add a model already available in a local Ollama service:

```text
/addollama LocalQwen qwen2.5:0.5b
```

The public stdio API does **not** expose an `allow_remote` override. The configured Ollama endpoint remains subject to the existing loopback-only transport guard, proxy bypass protection, and redirect rejection.

This is not the provider-authentication system. PR #16 adds a separate conventional `nexus auth` CLI and runtime broker outside TUI roster state.

xAI/Grok is available through the Python JSONL runtime with a configured auth profile and fixed `api.x.ai` transport, but this Rust TUI does not yet expose roster commands for that adapter. OpenAI, Claude, Gemini, provider-specific OAuth client registration, generic remote endpoints, and additional-provider discovery remain deferred. See [`AUTH.md`](AUTH.md) and [`XAI_ADAPTER.md`](XAI_ADAPTER.md).

## Evidence visibility boundary

Public Council evidence and targeted DCC evidence are intentionally different sets:

```text
room evidence
    -> same Council snapshot
    -> visible to all Council actors

targeted DCC evidence
    -> one direct cognitive channel
    -> not Council evidence until explicit /ref
```

Game rooms use the room-evidence side of this boundary: all Council members
receive the same current public state ref. Hidden table information stays out
of its bounded `content` representation.

That distinction is more important than faithfully reproducing historical IRC behavior.

NEXUS borrows the old interface. The substrate keeps modern provenance and evidence boundaries.
