# Council Chair Admission Rule

## Purpose

The Council Chair is the admission boundary for public `council.run` sessions. Its job is to prevent a Council from being structurally dominated by large or closed models while preserving the constitutional rule that every admitted seat has exactly one equal vote.

Model class affects **admission only**. It never changes vote weight, evidence status, consensus arithmetic, or epistemic privilege.

## Five-seat ceiling

A voting Council contains **3 to 5 seats**.

The Chair recognizes three mutually exclusive slot classes:

| Slot class | Rule | Maximum / minimum |
| --- | --- | --- |
| `protected_small` | Closed or open-weight model with **<=20B total declared parameters** | **at least 1** |
| `closed_general` | Closed model that is larger than 20B or whose parameter count is undisclosed | **at most 2** |
| `large_open_weight` | Open-weight model with **>20B total declared parameters** | **at most 2** |

The protected small seat is classified **first**. Therefore a closed model at or below 20B occupies `protected_small` and does not also consume one of the two `closed_general` slots. This preserves the intended maximum composition:

```text
2 closed-general + 2 large-open-weight + 1 protected-small = 5 seats
```

More than one small model is allowed. The protected seat is a floor, not a quota ceiling.

## Small-Mind Guarantee

At least one voting seat must remain structurally available to a model whose total declared parameter count is no greater than 20 billion.

The seat may be either closed or open-weight.

```text
parameter_count_millions <= 20_000
```

The threshold is inclusive. A 20B model qualifies; a 20.001B model does not.

For mixture-of-experts models, the Chair uses **total declared parameters**, not active parameters per token. A 200B MoE that activates 12B per token is not treated as a <=20B model.

## Equal authority after admission

Every admitted Council member still has:

```text
vote_weight = 1
epistemic_privilege = none
```

The following never increase authority:

- parameter count;
- provider identity;
- closed versus open-weight distribution;
- benchmark rank;
- subscription/account tier;
- local versus cloud deployment;
- tool or MCP access.

A 7B local model and a frontier closed model cast the same one vote once both are admitted.

## Model classification metadata

A model that needs to claim an open-weight or protected-small class supplies a closed, machine-readable classification under `capability_metadata.council_classification`:

```json
{
  "capability_metadata": {
    "council_classification": {
      "distribution": "open_weight",
      "parameter_count_millions": 20000,
      "parameter_count_basis": "total_declared",
      "parameter_count_source": "model_card:gpt-oss-20b"
    }
  }
}
```

Allowed `distribution` values are:

```text
closed
open_weight
```

Known counts must be positive exact integers in **millions of total declared parameters** and must use:

```text
parameter_count_basis = total_declared
```

An undisclosed count is accepted only for a closed classification and uses:

```json
{
  "distribution": "closed",
  "parameter_count_millions": null,
  "parameter_count_basis": "undisclosed",
  "parameter_count_source": "provider:undisclosed"
}
```

An explicitly open-weight model with an unknown total parameter count is rejected because the Chair cannot determine whether it belongs in the protected-small or large-open-weight class.

`parameter_count_source` is a bounded attestation label for auditability. NEXUS validates the shape of the attestation but does **not** claim to perform network verification of an external model card during Council admission.

## Adapter defaults and conservative fallback

When no explicit classification is supplied, the public provider-aware API treats these adapter families as known closed defaults:

```text
xai
openai
anthropic
gemini
```

They occupy `closed_general` with undisclosed size and cannot claim the protected-small seat without an explicit <=20B attestation.

For other model-hosting or aggregator adapters, including Ollama, LM Studio, AnythingLLM, Groq, and Together, an omitted classification is handled conservatively as an **opaque `closed_general` seat with undisclosed size**. This is a backward-compatibility fallback, not a claim that the underlying model is actually closed. It deliberately grants neither open-weight status nor protected-small status.

To make an Ollama or aggregator-hosted open model count as `open_weight` or `protected_small`, the operator must provide the explicit total-parameter attestation. Thus an unclassified 7B local model does **not** satisfy the Small-Mind Guarantee merely because it happens to run locally.

An explicit classification may also override a closed-provider default when the selected backend is actually an open-weight model and the operator supplies the total-parameter attestation.

The deterministic `mock` adapter is treated as a synthetic protected-small fixture unless a test explicitly supplies another classification.

## Distinct effective identities

Every voting seat must have a distinct effective `(adapter_id, model)` identity.

For adapters that allow a separate backend `model` override, the Chair checks the effective model override rather than trusting only the public `model_id`. Distinct labels that secretly route to the same configured backend do not create artificial diversity.

## Example: ChatGPT + gpt-oss

A closed OpenAI model and a local open-weight 20B model can vote in the same Council:

```json
[
  {
    "member_id": "ChatGPT",
    "model_id": "gpt-chat",
    "adapter_id": "openai",
    "auth_profile": "default"
  },
  {
    "member_id": "gpt-oss",
    "model_id": "gpt-oss:20b",
    "adapter_id": "ollama",
    "capability_metadata": {
      "council_classification": {
        "distribution": "open_weight",
        "parameter_count_millions": 20000,
        "parameter_count_basis": "total_declared",
        "parameter_count_source": "model_card:gpt-oss-20b"
      }
    }
  },
  {
    "member_id": "ThirdMind",
    "model_id": "another-small-model",
    "adapter_id": "mock"
  }
]
```

The OpenAI model occupies `closed_general`. The 20B gpt-oss model occupies `protected_small`. Both cast one equal vote.

## Failure order

Admission checks execute before actor construction, credential resolution, or provider inference.

The existing remote-provider spend caps remain in force and retain their earlier diagnostics. After those caps pass, the Chair enforces:

1. 3-5 voting seats;
2. explicit, default, or conservative classification;
3. distinct effective adapter/model identity;
4. at least one protected-small seat;
5. no more than two closed-general seats;
6. no more than two large-open-weight seats.

A rejected roster therefore cannot spend provider inference merely to discover that its Council composition was unconstitutional.

A separate semantic precedence rule remains: `citizenship_parole` has no Council at all, so a request for a parole-mode Council is rejected as `citizen_parole_has_no_council` before Chair roster arithmetic is considered.

## Public audit surface

`system.health` exposes the machine-readable Chair policy as the top-level:

```text
council_chair
```

The existing `council_limits` object remains the lower-level coordinator/network ceiling for compatibility. The Chair object is the stricter public voting-admission contract.

A successful public `council.run` response also includes:

```text
council_chair
```

That run-specific object records the admitted slot class for every requested seat, the aggregate slot counts, and the unchanged one-vote/no-privilege rule.

## Claim boundary

The Chair policy is a governance mechanism for model diversity. It does not claim that small models are wiser, large models are less trustworthy, open weights are morally superior, or closed providers are epistemically inferior.

Its narrower claim is structural:

> **Scale is not authority, and at least one small mind gets a real vote.**
