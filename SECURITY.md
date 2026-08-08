# NEXUS 2.x Security and Trust Boundaries

## Security posture

NEXUS 2.x is CLI/TUI-first. The browser workbench from NEXUS 1.0 is archived as prior work and is not the planned trusted operator surface for the new architecture.

The design separates:

```text
operator interface
provider adapters
trusted NEXUS control plane
persistent world
scientific / deterministic instruments
```

Remote model traffic should occur only inside explicitly configured adapters.

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

Planned shape:

```text
+-----------------------------+
| Rust TUI / CLI              |
| no raw provider secrets in  |
| normal display/log output   |
+-------------+---------------+
              |
        local protocol
              |
+-------------v---------------+
| Python NEXUS runtime        |
| world / Council / receipts  |
| equality policy             |
+-------------+---------------+
              |
        adapter interface
              |
+-------------v---------------+
| provider adapters           |
| only layer requiring remote |
| provider network access     |
+-------------+---------------+
              |
          provider API
```

Local-model adapters may require no outbound provider network access.

## Credential boundary

Provider credentials are not cognitive state.

They must never be written to:

- world objects;
- Council session objects;
- prompts unless absolutely required by a provider protocol (normally they are not);
- phase transcripts;
- receipts;
- replay bundles;
- experiment artifacts;
- source-control files;
- public diagnostic reports.

The future implementation should prefer an operating-system credential/keyring facility where practical, while allowing explicit external secret mechanisms for headless environments.

## Adapter privilege

An adapter may:

- obtain credentials from an approved secret source;
- make provider-specific network calls;
- discover available models where supported;
- normalize provider responses;
- report capability and usage metadata.

An adapter may not:

- change Council vote weight;
- change the Council roster;
- change the consensus threshold;
- edit another member's response;
- reveal blind material early;
- reveal sealed ballots early;
- mutate a frozen evidence snapshot;
- write raw secrets to world state;
- grant its provider epistemic privilege.

## Network policy

The NEXUS runtime should be able to report network intent explicitly:

```text
world kernel         outbound: none
receipt service      outbound: none
openai adapter       outbound: configured provider
anthropic adapter    outbound: configured provider
ollama adapter       local endpoint
```

A provider adapter's need for networking does not turn the whole world kernel into a general network client.

## Model content is untrusted input

Model-generated text, structured output, tool requests, and suggested code are untrusted until parsed and validated by the relevant protocol layer.

Future implementations should avoid directly executing arbitrary model-generated code in the NEXUS control plane. Experiments requiring code execution should use an explicit bounded instrument/sandbox contract.

## Equality Guard security role

The Equality Guard is not a security sandbox. It protects Council procedure from identity-based privilege claims.

Structural enforcement belongs in the coordinator:

```text
vote_weight = 1
one ballot per registered member
frozen roster
frozen threshold
phase-order enforcement
blind/reveal boundaries
```

Prompt nudges are only the friendly surface of those rules.

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
non-secret error classes

DO NOT ARCHIVE
raw credentials
authorization headers
provider refresh secrets
secret-store payloads
private local paths unless intentionally included
```

## Future threat work

Before executable adapters ship, create a dedicated threat model covering:

- credential theft;
- prompt injection through imported world objects;
- malicious model tool calls;
- provider response spoofing;
- replay tampering;
- Council ballot tampering;
- local-model endpoint impersonation;
- untrusted artifact parsing;
- denial-of-service / runaway Council loops.

The architecture-only alpha intentionally does not claim these implementation problems are solved.
