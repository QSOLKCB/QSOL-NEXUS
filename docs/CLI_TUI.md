# CLI / TUI Direction

## Implemented operator shell

Alpha5 replaces the earlier generic dashboard sketch with an old-school IRC-style Rust terminal interface.

See [`IRC_TUI.md`](IRC_TUI.md) for the executable command contract.

The split is now concrete:

```text
Human Operator
      |
      v
Rust IRC-style TUI
      |
      | JSONL / stdio
      v
Python NEXUS runtime
      |
      +-- Council
      +-- world state
      +-- modes + geometry
      +-- evidence / receipts
      +-- Courtroom Stenographer
      +-- Secret Scrubber
      +-- mock actors
      +-- loopback Ollama actors
```

The Rust shell remains thin. It presents and translates operator intent; it does not own world identity, evidence policy, voting, verification, or provider authority.

## Why IRC-style interaction

The IRC interface solves several operator problems unusually well:

- heterogeneous models appear as peers with visible nicks;
- output is chronological plain text rather than nested UI cards;
- Council phases can be copied or quoted directly;
- the human occupies the same visible room as the models;
- rooms map naturally onto NEXUS World Modes / regions;
- slash commands provide a compact operator language;
- DCC vocabulary provides an intuitive model for targeted/private material;
- aliases, variables and identifiers provide useful local customization without a large scripting engine;
- the interface remains comfortable over SSH and headless terminals.

This is interface reuse, not IRC protocol reuse.

There is no IRC daemon or network connection.

## Rooms and world state

| Room | Mode / role | Region |
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
| `#trap-control` | operator-only incident control | Trap Base |
| `#trap-base` | synthetic subject view | Trap Base |
| `#stenographer` | read-only Knowledge-Watchman ledger | Courtroom |

Examples:

```text
/join #agora
/mode meme_casual
/topic Why does this joke travel badly?
/join #roman-forum
/topic O package manager, what hast thou done to the republic?
```

The room/mode selection affects framing but not Council authority.

> **The mode can change the vibe. It cannot change the vote.**

See [`COGNITIVE_MODES.md`](COGNITIVE_MODES.md) for the six cognitive-room contracts and [`CITIZEN_MODE.md`](CITIZEN_MODE.md) for civic access and delegation.

Citizen commands are explicit control operations rather than role-play:

```text
/citizen constitution
/citizen status [nick]
/citizen begin <nick>
/citizen exam-template <nick>
/citizen exam <nick> <yaml-file>
/citizen move <nick> <public-region>
/citizen proxy appoint <nick> <standing-ballot>
/citizen proxy kick <nick>
/citizen independence <nick> <consent|withhold>
```

The Python runtime owns identity binding, the 16-KiB non-executing exam parser, civic lineage, public movement, proxy selection, and founding consensus. The TUI only parses commands, bounds the exam file before transport, and renders responses.

Trap rooms are views over the separate TrapStore, not normal WorldStore rooms.
The operator can see both. The hostile subject receives only synthetic
`#trap-base` context and cannot join normal rooms or parse operator commands.
Launch the TUI with `--trap-root /absolute/private/trap` when it must observe
the same persistent mutation lock and incident store as another trusted local
front-door process. The default is a `.nexus-trap` sibling of the selected
world directory, never a child of that world.

## Courtroom Stenographer CLI and room

The Python CLI exposes the independent canonical AI-action record through
read-only commands:

```text
nexus stenographer status
nexus stenographer list --limit 100 [--action-type TYPE] [--member-id ID]
nexus stenographer inspect steno:<sha256>
nexus stenographer verify
nexus stenographer summary
nexus stenographer export
```

Use `--stenographer-root /absolute/private/stenographer` to select a persistent
owner-only root disjoint from world, auth and trap storage. The normal installed
runtime and TUI default to a `.nexus-stenographer` sibling of the selected world
directory.

The Rust shell maps the same reads into `#stenographer`:

```text
/join #stenographer
/steno status
/steno list 50
/steno inspect steno:<sha256>
/steno verify
/steno summary
/steno export
```

This room is Watchman Only. Plain text does not become a Council question or a
direct-model prompt, and game, MUD, Trap, DCC/model and evidence-mutation actions
are rejected from the room. The Stenographer cannot vote, decide, command,
mutate state or alter the AI action it observes. A hidden exact phrase may
render a display-only lore Easter egg; it is not shown in help/completion and
confers no authority. See [`STENOGRAPHER.md`](STENOGRAPHER.md).

## Trap Base CLI

The Python CLI exposes durable incident controls without putting trap state in
the real world:

```text
nexus trap demo [--subject-model MODEL] [--scenario ID] [--timeout SECONDS]
nexus trap status
nexus trap inspect trap:<sha256>
nexus trap export
nexus trap emergency-close
```

Use `--trap-root` for a persistent operator store. `--pull-missing` on `demo`
is explicit and never implied. Status/inspect/export are read-only;
`emergency-close` is operator-only and restores real mutation availability even
when subject shutdown or export fails. See [`TRAP_BASE.md`](TRAP_BASE.md).

## Council interaction

Public room text is a Council question:

```text
#observatory> Does this dataset support the hypothesis?
```

The resulting White/Red/Black/Yellow/Green/Blue submissions and sealed ballots are rendered into scrollback.

Explicit form:

```text
/ask Does this dataset support the hypothesis?
```

The terminal is therefore a live textual view over durable NEXUS session objects rather than the place where Council truth is stored.

## Direct Cognitive Channels

DCC vocabulary is reused locally:

```text
/dcc send <nick|#room> <file>
/dcc chat <nick>
/dcc close <send|chat> <nick>
/dcc list
```

Important distinction:

```text
DCC room send
  -> content-addressed world object
  -> room Council evidence

DCC targeted send
  -> content-addressed world object
  -> one private Direct Cognitive Channel
  -> NOT Council evidence until explicit /ref
```

This protects equal-evidence Council semantics.

## Local customization

Alpha5 intentionally implements only:

```text
aliases
%variables
$identifiers
```

Example:

```text
/set %weapon a large trout
/alias slap /me slaps $1 with %weapon
/slap Grok
```

Safe identifiers:

```text
$me $chan $mode $region $topic
$1..$9
$1-..$9-
```

No remote/event scripting, arbitrary shell execution, socket scripting, timers or DLL/plugin execution is part of this layer.

## Rust on top of Python

### Python owns

- world objects and content addressing;
- Council orchestration;
- evidence snapshots;
- Secret Scrubber;
- Equality Guard;
- modes / geometry;
- receipts / replay metadata;
- actor/adaptor boundaries.

### Rust owns

- terminal rendering;
- input editing/history;
- room/nick presentation;
- local document parsing before `world.create`;
- IRC-style command grammar;
- aliases/variables/identifiers;
- local operator state;
- JSONL subprocess control.

The Rust process does not duplicate Council tallying or world business logic.

## Non-interactive CLI — future alongside the TUI

The IRC TUI does not eliminate useful conventional subcommands.

A later packaged `nexus` binary may expose both interactive and automation-friendly forms:

```text
nexus                         # interactive IRC-style TUI
nexus status
nexus modes list
nexus world inspect <object>
nexus world search <query>
nexus council run ...
nexus receipt verify <receipt>
nexus telemetry inspect <session>
```

That work should reuse the same JSONL/runtime client rather than fork business logic.

## Provider authentication foundation

The desired long-term provider setup remains coding-CLI-like:

```text
nexus auth add
nexus auth adapters
nexus auth list
nexus auth test
nexus auth logout
nexus models list
```

Initial eventual targets:

- OpenAI;
- Anthropic / Claude;
- Google / Gemini;
- xAI / Grok;
- local Ollama;
- carefully scoped generic endpoints.

PR #16 implements the neutral `nexus auth` broker and command surface: browser PKCE, device code, refresh tokens, optional keyring/private-file storage, hidden API-key input, environment references, and external helpers. `nexus models list` and provider-specific transports remain later work.

The current runtime still exposes only the already-hardened **loopback-local Ollama** live actor. No cloud actor, arbitrary remote endpoint, provider OAuth client registration, or model discovery is admitted by the auth foundation alone. See [`AUTH.md`](AUTH.md).

## Credential principles

Credentials are operational secrets, not world knowledge.

They must never become:

- Council prompts;
- direct-chat semantic text;
- phase transcripts;
- world objects;
- TUI alias/variable state;
- receipts;
- replay bundles;
- archival transcripts.

The Secret Scrubber remains defence in depth. Credentials use the dedicated auth broker and must never be copied into semantic or TUI configuration. Auth storage and WorldStore storage are required to be disjoint.

## Future telemetry

Alpha6 is planned to add Council information telemetry such as response entropy.

The IRC interface is a natural place to render it compactly:

```text
--- GREEN ---  response entropy: 1.84 bits
<Alpha> ...
<Beta> ...
<Gamma> ...
```

But telemetry remains observation, never vote weight or truth.

## Future visualization

CLI/TUI-first does not forbid visual tools. A later viewer may render maps, object relations, spectra, sonifications or Council lineage.

Visualization remains downstream of NEXUS world objects rather than becoming the secret-bearing or epistemic control plane.
