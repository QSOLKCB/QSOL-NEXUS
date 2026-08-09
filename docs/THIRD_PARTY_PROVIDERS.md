# Third-Party Provider Endpoints

NEXUS admits a small fixed set of remote model providers through the existing `AuthBroker` and equal-vote `CouncilActor` boundary.

The rule is simple:

> **A provider can supply model output. It does not acquire Council authority.**

## Admitted providers

| Adapter | Fixed API origin | Inference path | Model discovery | Authentication |
| --- | --- | --- | --- | --- |
| `openai` | `https://api.openai.com/v1` | `POST /responses` | `GET /models` | Bearer API key |
| `anthropic` | `https://api.anthropic.com/v1` | `POST /messages` | `GET /models` | `x-api-key` + fixed `anthropic-version` |
| `gemini` | `https://generativelanguage.googleapis.com/v1beta` | `POST /models/{model}:generateContent` | `GET /models?pageSize=1000` | `x-goog-api-key` |
| `groq` | `https://api.groq.com/openai/v1` | `POST /responses` | `GET /models` | Bearer API key |
| `together` | `https://api.together.ai/v1` | `POST /chat/completions` | `GET /models` | Bearer API key |

The provider origin is part of adapter code. Public NEXUS requests cannot override it.

Together deliberately uses Chat Completions because Together's OpenAI-compatibility documentation does not currently implement the Responses API. Groq uses its current Responses API but NEXUS does not send OpenAI's `store` field because Groq documents that field as unsupported. OpenAI requests explicitly set `store: false`.

## Open-weight model paths

NEXUS now has three practical paths for open/open-weight models:

```text
ollama     local loopback models

groq       fixed-host hosted open-weight models
           examples include provider-published GPT-OSS / Llama / Qwen IDs

together   fixed-host hosted open-weight models
           model IDs are normally namespaced, e.g. provider/model
```

Open/closed status is descriptive metadata only. It never changes vote weight, consensus threshold, evidence status, or epistemic privilege.

## Authentication

Remote credentials remain outside WorldStore and outside the public JSONL request body.

Recommended headless setup:

```bash
nexus auth add openai --method env --env OPENAI_API_KEY
nexus auth add anthropic --method env --env ANTHROPIC_API_KEY
nexus auth add gemini --method env --env GEMINI_API_KEY
nexus auth add groq --method env --env GROQ_API_KEY
nexus auth add together --method env --env TOGETHER_API_KEY
```

Hidden-prompt API-key storage and no-shell external credential helpers remain available through the existing auth broker where the descriptor permits them.

Inspect configured providers without revealing secrets:

```bash
nexus auth adapters
nexus auth list
nexus auth test openai
```

Discover models:

```bash
nexus models list openai
nexus models list anthropic
nexus models list gemini
nexus models list groq
nexus models list together
```

## Direct actor example

```json
{
  "operation": "actor.chat",
  "member": {
    "member_id": "OpenAI",
    "model_id": "gpt-5.5",
    "adapter_id": "openai",
    "auth_profile": "default"
  },
  "message": "Separate observation from inference."
}
```

No API key appears in that request. `auth_profile` is an opaque local reference resolved inside the broker/transport boundary.

A Together or Groq open-weight member can use a namespaced model id:

```json
{
  "member_id": "OpenWeight",
  "model_id": "openai/gpt-oss-20b",
  "adapter_id": "together",
  "auth_profile": "default"
}
```

## Council example

Remote providers can be mixed with local and deterministic members:

```json
{
  "operation": "council.run",
  "question": "What does the evidence support?",
  "members": [
    {"member_id": "Local", "model_id": "qwen2.5:7b", "adapter_id": "ollama"},
    {"member_id": "Claude", "model_id": "claude-sonnet-4-5", "adapter_id": "anthropic"},
    {"member_id": "Gemini", "model_id": "gemini-3.5-flash", "adapter_id": "gemini"},
    {"member_id": "OpenAI", "model_id": "gpt-5.5", "adapter_id": "openai"}
  ]
}
```

The existing remote-seat ceiling is shared across all fixed-host remote providers. A Council cannot evade the cap by spreading seats across different vendors.

Every member still has:

```text
vote_weight = 1
epistemic_privilege = none
```

## Security boundary

The third-party transport deliberately keeps the xAI adapter's security posture:

- fixed HTTPS origins only;
- no operator-provided remote base URL;
- environment proxy bypass;
- HTTP redirects rejected;
- bounded request, response, timeout and model-list sizes;
- provider error bodies discarded from public errors;
- configured credential reflection rejected;
- recognized credential-shaped successful output rejected before projection into NEXUS;
- no automatic tools;
- no automatic inference retries;
- remote inference remains non-replayable;
- credentials remain in `AuthBroker` / transport state, not prompts, evidence, receipts or world objects.

Provider-side retention, logging, policy and account configuration remain provider properties. NEXUS does not claim that a local `store: false` request option creates a universal zero-retention guarantee.

## API-family differences are intentional

These transports are not implemented as one pretend-universal OpenAI endpoint.

NEXUS normalizes the provider response only after respecting the provider-native wire contract:

```text
OpenAI / Groq Responses API
    -> typed output_text blocks

Anthropic Messages API
    -> content[] text blocks

Gemini generateContent
    -> candidates[].content.parts[].text

Together Chat Completions
    -> choices[].message.content
```

The shared NEXUS prompt builder and ballot parser sit above those transport differences.

## Live-provider testing

Hermetic tests use fake HTTP openers and synthetic credentials. They verify URLs, headers, payload shapes, response parsing, credential-reflection rejection, arbitrary-endpoint rejection, model discovery and the mixed-provider remote-seat cap.

Real provider calls require operator-supplied credentials and are intentionally not performed by ordinary unit tests.

## Primary provider references

- OpenAI API reference: `https://platform.openai.com/docs/api-reference`
- Anthropic API documentation: `https://docs.anthropic.com/en/api`
- Gemini API reference: `https://ai.google.dev/api`
- Groq API documentation: `https://console.groq.com/docs`
- Together OpenAI compatibility: `https://docs.together.ai/docs/inference/openai-compatibility`
