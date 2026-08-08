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

```text
#observatory   -> analytical  -> Observatory
#archive       -> historical  -> Archive
#agora         -> cultural    -> Agora
#commons       -> meme_casual -> Commons
```

Examples:

```text
/join #agora
/mode meme_casual
/topic Why does this joke travel badly?
```

The room/mode selection affects framing but not Council authority.

> **The mode can change the vibe. It cannot change the vote.**

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
