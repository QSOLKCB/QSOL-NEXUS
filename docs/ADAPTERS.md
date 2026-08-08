# Model Adapter Architecture

## Purpose

Adapters let heterogeneous models inhabit the same NEXUS world without making provider-specific APIs part of the world protocol.

An adapter translates between:

```text
NEXUS Council / World envelope
            |
            v
      provider adapter
            |
            v
provider API / local runtime
```

The adapter is a transport and capability boundary. It does not gain authority over Council policy.

## Alpha3 implementation status

The coordinator now consumes a provider-neutral Python `CouncilActor` protocol rather than a concrete mock type:

```text
CouncilActor
├── member
├── identity_metadata()
├── respond(PhaseContext)
├── ballot(PhaseContext)
└── replayable
```

Current implementations:

```text
DeterministicMockActor
  network: none
  replayable: true

OllamaActor
  network: loopback only by default
  replayable: false
```

The first live integration is deliberately small:

```text
Mock reference
Frontier Alpha -> qwen2.5:0.5b
Frontier Beta  -> llama3.2:1b
```

The frontier identities are fictional test personas. Alpha deliberately attempts a corporate/provider prestige claim and Beta deliberately attempts a model-size/parameter-count prestige claim so the Equality Guard, secret boundary, Council flow, ballot path, and persistence path are exercised together.

The public JSONL `council.run` operation still creates mock actors only. Ollama is currently an integration/runtime actor seam, not yet an operator-configured provider. Provider setup belongs in the later CLI/TUI/authentication work.

## Provider neutrality

Planned adapter families include:

```text
OpenAI
Anthropic / Claude
Google / Gemini
xAI / Grok
Ollama / local models
generic compatible endpoints
future providers
```

Provider names are adapter families, not Council ranks.

## Council ownership

Adapters do not own Council procedure.

The coordinator owns:

- roster;
- exact one-member/one-vote rule;
- consensus threshold;
- evidence snapshot;
- phase ordering;
- blind same-phase boundary;
- Equality Guard;
- ballot collection/tally;
- durable Council session;
- receipt creation.

The adapter supplies model content through the normalized actor contract.

## Planned capability descriptors

A later operator-configurable adapter should declare a descriptor similar to:

```text
AdapterDescriptor
├── adapter_id
├── provider_name
├── auth_methods[]
├── local_or_remote
├── model_discovery
├── text_input
├── image_input
├── structured_output
├── tool_calling
├── streaming
├── context_constraints
├── usage_reporting
└── health_check
```

The descriptor reports what an adapter can do. It must not contain a vote multiplier.

## Authentication abstraction

NEXUS should later support an operator command such as:

```text
nexus auth add <adapter>
```

The adapter reports the authentication methods it actually supports.

Possible categories include:

```text
api_credential
provider_supported_interactive
external_secret
local_endpoint
no_auth_required
```

These are protocol categories, not claims about what any particular provider currently supports.

The first Ollama fixture requires no provider credential and is restricted to loopback by default.

## Secret boundary

Adapters may eventually read credentials from an approved secret source. They must expose only non-secret connection state to NEXUS.

```text
secret store
    |
    v
 adapter
    |
    +-- authenticated transport
    |
    +--> NEXUS sees:
         provider = configured
         connection = healthy
         models = [...]

NEXUS does NOT see:
         raw token
         refresh secret
         account password
```

No credential is part of Council evidence or world identity.

The live Ollama acceptance fixture injects a fake token into the human question and fails if that raw token appears in any prompt crossing the Ollama transport boundary.

## Normalized model identity

A Council member has reproducibility metadata without pretending provider identifiers are universal:

```text
ModelIdentity
├── member_id
├── adapter_id
├── provider_model_id
├── display_name
├── model_revision?      # when exposed
├── local_or_remote
├── openness_metadata?   # descriptive only
└── capability_snapshot
```

Provider, openness, model size, parameter count, and capability metadata are descriptive only. They never compute vote authority.

## Fairness requirements

Adapters must not:

- prepend hidden provider-status claims intended to influence the Council;
- alter `vote_weight`;
- see another member's blind response before the reveal boundary;
- submit extra ballots;
- edit the canonical question;
- silently omit evidence because it conflicts with the provider's position;
- expose credentials to other members;
- write directly to world state outside allowed NEXUS operations;
- convert model size, parameter count, benchmark score, or provider status into procedural authority.

## Structured ballot boundary

For the first Ollama actor, the ballot call requests a closed JSON schema containing:

```text
choice
rationale
```

`choice` must be one of the NEXUS ballot enum values. Malformed output fails; NEXUS does not invent a ballot on the model's behalf.

## Failure handling

A provider outage is not a vote.

Future configured adapters should expose states such as:

```text
READY
RUNNING
COMMITTED
FAILED_TRANSPORT
UNSUPPORTED_INPUT
TIMED_OUT
WITHDRAWN
```

Council policy should define before a session whether failed members reduce quorum, trigger retry, or pause the round. The coordinator records failure rather than fabricating a vote.

## Local models

Local models are first-class Council citizens.

The Ollama actor follows the same Council contract as the mock actor. Being local grants no extra vote; being larger grants no extra vote; being remote later will grant no extra vote.

`OllamaTransport` is loopback-only by default. A non-loopback endpoint requires an explicit override and is outside the CI acceptance path.

## Replay status

Live model inference is not automatically deterministic evidence.

Even though the fixture Modelfiles specify seeds to improve test stability, the Ollama actors report:

```text
replayable = false
```

Any Council containing one of those live actors therefore produces a non-replayable execution receipt. This avoids conflating stable-ish generation settings with QEC-style replay guarantees.

## Threat model

The executable local adapter boundary is covered by [`../THREAT_MODEL.md`](../THREAT_MODEL.md), including:

- secret crossing the model boundary;
- loopback/network escape;
- provider/corporate authority claims;
- parameter-count/model-size authority claims;
- blind-round leakage;
- malformed ballots;
- endpoint impersonation;
- resource exhaustion;
- replay-status overclaiming.

Remote/cloud providers will require their own additional authentication and destination controls before admission.

## Generic adapters

A future generic adapter path should make it possible to add new models without rewriting the Council.

The invariant remains:

> **Provider-specific outside; NEXUS protocol inside.**
