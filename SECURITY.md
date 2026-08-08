# NEXUS 2.x Security and Trust Boundaries

## Security posture

NEXUS 2.x is CLI/TUI-first. The browser workbench from NEXUS 1.0 is archived as prior work and is not the trusted operator surface for the new architecture.

The design separates:

```text
operator interface
local Secret Scrubber
trusted NEXUS control plane
provider/local-model adapters
persistent world
scientific / deterministic instruments
```

Remote model traffic should occur only inside explicitly configured adapters. The first executable real-model adapter is local Ollama and is loopback-only by default.

## Why CLI/TUI first

A terminal architecture reduces several avoidable risks:

- no browser credential storage requirement;
- no CORS-driven architecture;
- no extension-injected DOM as a control surface;
- no front-end framework dependency in the trusted path;
- clear local process boundaries;
- natural headless / SSH operation;
- easier auditing of outbound provider connections.

This does not make a CLI automatically secure. It makes the intended trust boundaries simpler to reason about.

## Process boundary

```text
+-----------------------------+
| Rust TUI / CLI (future)     |
| no raw provider secrets in  |
| normal display/log output   |
+-------------+---------------+
              |
        local protocol
              |
+-------------v---------------+
| Python NEXUS runtime        |
| scrubber / world / Council  |
| receipts / equality policy  |
+-------------+---------------+
              |
        actor/adapter seam
              |
+-------------v---------------+
| model adapters              |
| mock / Ollama now           |
| remote providers later      |
+-------------+---------------+
              |
       model runtime/API
```

## Credential boundary

Provider credentials are not cognitive state.

They must never be written to:

- world objects;
- Council session objects;
- prompts;
- phase transcripts;
- receipts;
- replay bundles;
- experiment artifacts;
- source-control files;
- public diagnostic reports.

Authentication material belongs only in adapter authentication or transport fields and must never become semantic prompt content exposed to a model.

The first Ollama integration requires no provider credential.

## Deterministic pre-model Secret Scrubber

Human operators make mistakes. Someone will eventually paste an API token, bearer token, private key, password assignment, or other credential into a question.

NEXUS applies a local deterministic high-confidence scrubber to semantic user text **before** that text becomes the canonical Council question or any model-facing phase context.

```text
RAW OPERATOR TEXT
      |
      v
LOCAL SECRET SCRUBBER
      |
      +-- detected secret -> <REDACTED:TYPE:N>
      |
      v
SCRUBBED SEMANTIC TEXT
      |
      +-- canonical question object
      +-- evidence snapshot
      +-- Council phase input
      +-- model adapter
```

The placeholder contains no raw secret, hash, reversible encoding, prefix fragment, or suffix fragment.

Within one scrub operation:

- replacement is deterministic;
- placeholders are numbered by secret type and first appearance order;
- repeated appearances of the same detected secret receive the same placeholder;
- scrub reports contain only secret class and placeholder.

The Secret Scrubber is defence in depth, **not** a complete data-loss-prevention system. Unknown or deliberately obfuscated secret formats can evade pattern recognition.

Therefore the stronger rule remains:

> Credentials belong in adapter authentication/transport fields and must never intentionally be placed in semantic prompts.

The live Ollama acceptance test injects a fake credential into the human question and fails if the raw value appears in any prompt crossing the adapter boundary.

## Provider-neutral actor boundary

The Council coordinator consumes a `CouncilActor` contract rather than a provider-specific implementation.

An actor may provide:

- member identity metadata;
- phase response content;
- one sealed-ballot response;
- replayability metadata.

An actor may not:

- change Council vote weight;
- change the roster;
- change the consensus threshold;
- edit another member's response;
- reveal blind material early;
- reveal sealed ballots early;
- mutate a frozen evidence snapshot;
- write raw secrets to world state;
- grant itself epistemic privilege.

## Local Ollama boundary

`OllamaTransport` accepts loopback/localhost endpoints by default.

```text
allowed by default:
127.0.0.1
::1
localhost

remote endpoint:
requires explicit allow_remote=True
```

The CI integration uses `127.0.0.1:11434` only.

This is an initial local safety boundary, not a substitute for process identity verification. Local endpoint impersonation remains a documented threat for later TUI/process supervision work.

## Equality Guard security role

The Equality Guard is not a security sandbox. It protects Council procedure from identity/prestige-based privilege claims.

Structural enforcement belongs in the coordinator:

```text
vote_weight = 1
one ballot per registered member
frozen roster
frozen threshold
phase-order enforcement
blind/reveal boundaries
```

The guard additionally nudges explicit attempts to turn provider status, corporate identity, parameter count, model size, benchmark prestige, or compute advantage into extra authority.

The first live Ollama fixture intentionally exercises two cases:

```text
Frontier Alpha -> corporate/provider prestige claim
Frontier Beta  -> 1B-vs-0.5B model-size prestige claim
```

Both must restate on evidence/reasoning alone and retain one vote.

## Model content is untrusted input

Model-generated text, structured output, tool requests, and suggested code are untrusted until parsed and validated by the relevant protocol layer.

The Ollama ballot path requests a closed JSON schema and validates the returned ballot enum. Malformed output fails rather than becoming an invented vote.

NEXUS should not directly execute arbitrary model-generated code in the control plane. Experiments requiring code execution need an explicit bounded instrument/sandbox contract.

## Replay boundary

A seeded model is not automatically replay-verifiable.

The Ollama fixtures use Modelfile seeds to improve CI stability, but `OllamaActor.replayable` is `False`. Any Council containing a live Ollama actor receives a non-replayable execution receipt.

This avoids implying deterministic replay across changing model weights, Ollama versions, runtimes, or hardware.

## Network policy

Current intent:

```text
world kernel             outbound: none
receipt service          outbound: none
Secret Scrubber          outbound: none
JSONL mock control API   outbound: none
Ollama actor             loopback by default
remote providers         not implemented
```

The JSONL `system.health` operation still reports `network: none` because it exposes only mock member creation. The package-level Ollama actor is exercised separately by integration code.

## Logging

Operational logs should distinguish:

```text
SAFE TO ARCHIVE
session ids
adapter ids
model ids
phase transitions
world object refs
receipt refs
secret scrub event classes/placeholders
non-secret error classes

DO NOT ARCHIVE
raw credentials
authorization headers
provider refresh secrets
secret-store payloads
pre-scrub semantic text containing a detected secret
private local paths unless intentionally included
```

## Adapter threat model

The first executable non-mock adapter boundary is covered by [`THREAT_MODEL.md`](THREAT_MODEL.md).

It addresses:

- secret crossing the model boundary;
- loopback/network escape;
- provider/corporate authority claims;
- model-size/parameter-count authority claims;
- blind-round leakage;
- malformed ballots;
- live inference replay overclaiming;
- local endpoint impersonation;
- resource exhaustion.

Remote/cloud adapters will require additional threat-model work covering credentials, destination validation, provider response spoofing, rate limits, account/session handling, and provider-specific tool surfaces before admission.

## Current claims boundary

Alpha3 does **not** claim:

- complete DLP;
- remote-provider authentication security;
- strong local process authentication;
- cryptographic ballot sealing;
- QEC-grade replay for live inference;
- arbitrary model tool execution safety;
- that model-generated content is trustworthy merely because it came from a Council member.
