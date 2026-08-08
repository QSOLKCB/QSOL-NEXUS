# CLI / TUI Direction

## Goal

NEXUS 2.x should feel like a good coding CLI: install it, configure providers, authenticate, choose models, create a Council, ask a question, inspect the deliberation, run instruments, and revisit the resulting world objects later.

The planned split is:

```text
Rust CLI/TUI
    |
    | local structured protocol
    v
Python NEXUS tooling/runtime
    |
    +-- Council
    +-- world state
    +-- instruments
    +-- replay / receipts
    +-- provider adapters
```

This document describes the intended operator experience only. Nothing here is implemented in the architecture-only alpha.

## Why Rust on top of Python

### Python underneath

Python is a practical first reference layer for:

- scientific tooling;
- numerical experiments;
- existing QSOL scripts;
- rapid protocol iteration;
- provider adapter development;
- test fixtures;
- local-model integration.

### Rust on top

Rust is a good fit for the operator shell because it can provide:

- a responsive terminal UI;
- robust process supervision;
- predictable local binaries;
- structured input validation;
- good cross-platform CLI ergonomics;
- later hardening without forcing the scientific tooling into Rust prematurely.

The TUI should remain thin. Business logic belongs in protocol-defined tooling rather than being trapped in presentation code.

## Proposed commands

Names are provisional.

```text
nexus init
nexus status

nexus auth list
nexus auth add
nexus auth remove <provider>
nexus auth test <provider>

nexus models list
nexus models inspect <model>

nexus council create
nexus council list
nexus council inspect <id>
nexus council ask <id> "question"
nexus council replay <session>

nexus world inspect <object>
nexus world search <query>
nexus world lineage <object>

nexus instruments list
nexus receipt verify <receipt>
```

A command should have a non-interactive form wherever practical so NEXUS can be scripted or used over SSH.

## First-run provider setup

Conceptual flow:

```text
$ nexus auth add

Select provider
> OpenAI
  Anthropic / Claude
  Google / Gemini
  xAI / Grok
  Ollama / local
  Generic endpoint

Adapter: openai
Supported setup methods:
> provider-supported interactive setup
  API credential
  environment / external secret

Follow provider setup...

Connection test: PASS
Models discovered: 4

Add models to a Council now? [y/N]
```

The exact setup methods are adapter capabilities. NEXUS must not pretend all providers expose the same authentication flow.

## Credential principles

Credentials are operational secrets, not world knowledge.

They must never appear in:

- Council prompts;
- phase transcripts;
- world objects;
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

## TUI sketch

```text
+------------------------------------------------------------------+
| QSOL NEXUS                                      WORLD: local-main |
+------------------+-----------------------------------------------+
| COUNCIL          | SESSION: NXC-184                              |
|                  |                                               |
| [x] GPT model    | Question                                      |
| [x] Claude model | Does observation X support hypothesis Y?      |
| [x] Gemini model |                                               |
| [x] Grok model   | Phase: BLACK                                  |
| [x] Qwen local   | --------------------------------------------- |
|                  | A  committed                                  |
| Providers        | B  committed                                  |
| OpenAI      OK   | C  running                                    |
| Anthropic   OK   | D  committed                                  |
| Google      OK   | E  committed                                  |
| xAI         OK   |                                               |
| Ollama      OK   | Equality guard: clean                         |
+------------------+-----------------------------------------------+
| [World] [Council] [Evidence] [Experiments] [Receipts] [Settings] |
+------------------------------------------------------------------+
```

## Council creation sketch

```text
$ nexus council create

Name: Astrophysics Council

Available models
[ ] openai/model-a
[ ] anthropic/model-b
[ ] google/model-c
[ ] xai/model-d
[ ] ollama/qwen-local

Select at least 3 members.

Policy
  hats: WHITE RED BLACK YELLOW GREEN BLUE
  first_pass: blind
  ballot: sealed
  threshold: 0.667
  vote_weight: fixed at 1

Create? yes

Council created: council:astrophysics
```

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

## Network visibility

Remote-provider activity should be obvious in the TUI.

```text
NETWORK
openai adapter       outbound: active
anthropic adapter    outbound: idle
ollama adapter       local: active
world kernel         outbound: none
```

The trusted world should not make hidden provider calls on behalf of adapters.

## Future visualization

CLI/TUI-first does not forbid visual tools. A later viewer can render completed graphs, spectra, sonifications, images, or experiment lineage. The important rule is that visualization remains downstream of world objects and does not become the secret-bearing or epistemic control plane.
