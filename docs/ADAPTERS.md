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

## Provider neutrality

Initial adapter targets may include:

```text
OpenAI
Anthropic / Claude
Google / Gemini
xAI / Grok
Ollama / local models
generic OpenAI-compatible endpoints
future providers
```

Provider names are examples of adapter families, not Council ranks.

## Planned adapter capabilities

Each adapter should eventually declare a capability descriptor similar to:

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

NEXUS should support a simple operator command such as:

```text
nexus auth add <adapter>
```

The adapter then reports the authentication methods it actually supports.

Possible categories include:

```text
api_credential
provider_supported_interactive
external_secret
local_endpoint
no_auth_required
```

These are protocol categories, not claims about what any specific provider currently supports.

## Secret boundary

Adapters may read credentials from an approved secret source. They must expose only a non-secret connection state to NEXUS.

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

## Normalized model identity

A Council member should have a reproducible identity envelope without pretending provider identifiers are universal:

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

`openness_metadata` is never used to compute authority.

## Canonical Council request

Conceptual shape:

```json
{
  "session": "council:184",
  "member": "member:03",
  "phase": "black",
  "question_ref": "object:question",
  "evidence_snapshot_ref": "snapshot:abc",
  "peer_material_refs": [],
  "instructions_ref": "policy:debono-v1",
  "available_instruments": ["world.inspect", "world.test"]
}
```

The adapter converts this into the provider-specific request format.

## Normalized response

Conceptual shape:

```json
{
  "member": "member:03",
  "phase": "black",
  "content": "...",
  "evidence_refs": ["object:x"],
  "proposed_tests": ["experiment:y"],
  "adapter_metadata": {
    "status": "ok"
  }
}
```

Provider-specific usage metadata may be attached outside the semantic content where useful.

## Fairness requirements

Adapters must not:

- prepend hidden provider-status claims intended to influence the Council;
- alter `vote_weight`;
- see another member's blind response before the reveal boundary;
- submit extra ballots;
- edit the canonical question;
- silently omit evidence because it conflicts with the provider's position;
- expose credentials to other members;
- write to world state except through allowed NEXUS operations.

## Failure handling

A provider outage is not a vote.

```text
member state:
READY
RUNNING
COMMITTED
FAILED_TRANSPORT
UNSUPPORTED_INPUT
TIMED_OUT
WITHDRAWN
```

The Council policy should define before a session whether failed members reduce quorum, trigger retry, or cause the round to pause. The coordinator records the event rather than inventing a ballot on the member's behalf.

## Local models

Local models are first-class Council citizens.

An Ollama/local adapter should follow the same normalized contract as a remote provider adapter. Being local grants no extra vote; being remote grants no extra vote.

## Generic adapters

A generic adapter path should make it possible to add future models without rewriting the Council.

The invariant is:

> **Provider-specific outside; NEXUS protocol inside.**
