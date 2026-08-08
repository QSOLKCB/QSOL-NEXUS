# CLI / TUI Direction

## Goal

NEXUS 2.x should feel like a good coding CLI: install it, inspect the world, choose a mode, create a Council, ask a question, inspect the deliberation, run instruments, move through world regions, and revisit resulting objects later.

Provider authentication remains part of the long-term operator experience, but it is deliberately **not the next implementation priority**.

The planned split is:

```text
Rust CLI/TUI
    |
    | local structured protocol
    v
Python NEXUS runtime
    |
    +-- Council
    +-- world state
    +-- modes + geometry
    +-- telemetry
    +-- instruments
    +-- replay / receipts
    +-- provider adapters
```

The Rust shell should remain thin. Business logic belongs in protocol-defined tooling rather than presentation code.

## Why Rust on top of Python

### Python underneath

Python is a practical reference layer for:

- scientific tooling;
- numerical experiments;
- existing QSOL scripts;
- rapid protocol iteration;
- local-model integration;
- world/mode/geometry logic;
- test fixtures.

### Rust on top

Rust is a good fit for the operator shell because it can provide:

- a responsive terminal UI;
- robust process supervision;
- predictable local binaries;
- structured input validation;
- good cross-platform CLI ergonomics;
- later hardening without forcing scientific tooling into Rust prematurely.

## Proposed commands

Names are provisional.

```text
nexus init
nexus status

nexus modes list
nexus mode inspect <mode>

nexus world map
nexus world where
nexus world inspect <object>
nexus world search <query>
nexus world lineage <object>

nexus council create
nexus council list
nexus council inspect <id>
nexus council ask <id> "question"
nexus council replay <session>

nexus telemetry inspect <session>
nexus instruments list
nexus receipt verify <receipt>

# Later authentication milestone
nexus auth list
nexus auth add
nexus auth remove <provider>
nexus auth test <provider>
nexus models list
nexus models inspect <model>
```

A command should have a non-interactive form wherever practical so NEXUS can be scripted or used over SSH.

## World-mode selection

Conceptual flow:

```text
$ nexus council create

Choose world mode
> Analytical   [Observatory]
  Historical   [Archive]
  Cultural     [Agora]
  Meme/Casual  [Commons]

Council mode: Cultural
World region: Agora (0,2)
```

The selected mode is world/protocol state rather than merely cosmetic terminal configuration.

The TUI may use very different presentation styles for different modes later, but the underlying constitutional rules remain identical.

## TUI sketch

```text
+------------------------------------------------------------------+
| QSOL NEXUS                     WORLD: local-main   REGION: AGORA  |
| MODE: Cultural                                                  |
+------------------+-----------------------------------------------+
| COUNCIL          | SESSION: object:...                           |
|                  |                                               |
| [x] member-a     | Question                                      |
| [x] member-b     | Why does this joke work here but not there?   |
| [x] member-c     |                                               |
|                  | Phase: BLACK                                  |
| World            | --------------------------------------------- |
| Observatory      | A  committed                                  |
| Archive          | B  committed                                  |
| > Agora          | C  running                                    |
| Commons          |                                               |
|                  | Equality guard: clean                         |
+------------------+-----------------------------------------------+
| [Map] [Council] [Evidence] [Telemetry] [Receipts] [Settings]     |
+------------------------------------------------------------------+
```

## Council creation sketch

```text
$ nexus council create

Name: Cultural Context Council
Mode: cultural
Region: Agora

Available local/test actors
[ ] mock/a
[ ] mock/b
[ ] mock/c
[ ] ollama/qwen-local

Select at least 3 members.

Policy
  hats: WHITE RED BLACK YELLOW GREEN BLUE
  first_pass: blind
  ballot: sealed
  threshold: 2/3
  vote_weight: fixed at 1

Create? yes
```

The `2/3` threshold is exact. A future implementation should compare integer vote counts rather than rounded floating-point approximations.

## Provider-neutral status

The TUI may show provider names because the operator needs to know what is configured. Provider presentation must not imply Council rank.

Good:

```text
OpenAI/model-a       READY    vote 1
Anthropic/model-b    READY    vote 1
Ollama/qwen-local    READY    vote 1
```

Bad:

```text
Tier 1: frontier commercial model    vote 2
Tier 2: open model                   vote 0.5
```

The same applies to mode and geometry: an Observatory session has no more epistemic authority than an Agora or Commons session merely because its label sounds more serious.

## Authentication — later milestone

The desired long-term setup still resembles modern coding CLIs:

```text
$ nexus auth add

Select provider
> OpenAI
  Anthropic / Claude
  Google / Gemini
  xAI / Grok
  Ollama / local
  Generic endpoint
```

But NEXUS should first mature the shared world, telemetry, instruments, persistence and operator shell. Remote providers should arrive into a stable world rather than define its architecture.

The exact setup methods remain adapter capabilities. NEXUS must not pretend all providers expose the same authentication flow.

## Credential principles

Credentials are operational secrets, not world knowledge.

They must never appear in:

- Council prompts;
- phase transcripts;
- world objects;
- mode/geometry objects;
- receipts;
- replay bundles;
- Git repositories;
- logs intended for archival publication.

Preferred future order:

```text
OS credential/keyring facility when available
        |
explicit external secret/environment integration
        |
operator-specified secure adapter backend
```

Plaintext project configuration should never be the default for provider secrets.

## Network visibility

When remote-provider support eventually lands, activity should be obvious in the TUI.

```text
NETWORK
openai adapter       outbound: active
anthropic adapter    outbound: idle
ollama adapter       local: active
world kernel         outbound: none
```

The trusted world should not make hidden provider calls on behalf of adapters.

## Future visualization

CLI/TUI-first does not forbid visual tools. A later viewer can render:

- the named-region world map;
- object relations;
- Council lineage;
- response-entropy telemetry;
- spectra;
- sonifications;
- experiment artifacts.

Visualization remains downstream of world objects and does not become the secret-bearing or epistemic control plane.
