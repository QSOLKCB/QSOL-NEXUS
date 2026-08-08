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
      +-- Secret Scrubber
      +-- mock actors
      +-- explicit loopback Ollama actors
```

## Run

From the repository root:

```bash
cargo run --manifest-path tui/Cargo.toml -- --world .nexus-world --nick Trent
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

The first NEXUS rooms map directly to the alpha4 world geometry:

```text
#observatory   -> analytical  -> Observatory
#archive       -> historical  -> Archive
#agora         -> cultural    -> Agora
#commons       -> meme_casual -> Commons
```

Examples:

```text
/join #agora
/join cultural
/mode meme_casual
```

Changing room changes mode and world region. It does not change evidence rules, vote weights, verification, the Secret Scrubber, or the Equality Guard.

> **The mode can change the vibe. It cannot change the vote.**

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

This is especially at home in `#commons`, but the command exists in every room.

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

Built-in commands cannot be replaced by aliases.

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

This is not the future provider-authentication system.

OpenAI, Claude, Gemini, Grok cloud APIs, credentials, OAuth, generic remote endpoints, and provider discovery remain deferred.

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

That distinction is more important than faithfully reproducing historical IRC behavior.

NEXUS borrows the old interface. The substrate keeps modern provenance and evidence boundaries.
