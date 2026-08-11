# Council Chair Admission Rule

## Purpose

The Council Chair is the admission boundary for public `council.run` sessions. Its job is to prevent a Council from being structurally dominated by large or closed models while preserving the constitutional rule that every admitted seat has exactly one equal vote.

Model class affects **admission only**. It never changes vote weight, evidence status, consensus arithmetic, or epistemic privilege.

PR #42 adds **Temporal Compute Equality** to the PR #34 Chair. The original 20B protected-small ceiling is now the **Epoch 0 base value**, not a permanent definition of smallness.

> **Time may enlarge the chair. It may not enlarge the vote.**

The complete epoch contract is documented in `COMPUTE_EPOCHS.md`.

## Five-seat ceiling

A voting Council contains **3 to 5 seats**.

Let `S(E)` be the protected-small ceiling at Compute Epoch `E`:

```text
S(E) = 20B * 2^E
```

under `nexus-compute-epoch-v1`.

The Chair recognizes three mutually exclusive slot classes:

| Slot class | Rule | Maximum / minimum |
| --- | --- | --- |
| `protected_small` | Closed or open-weight model with total declared parameters `<= S(E)` | **at least 1** |
| `closed_general` | Closed model larger than `S(E)` or whose parameter count is undisclosed | **at most 2** |
| `large_open_weight` | Open-weight model with total declared parameters `> S(E)` | **at most 2** |

The protected-small class is evaluated first. Therefore a closed model at or below the current epoch ceiling occupies `protected_small` and does not also consume one of the two `closed_general` slots. The maximum structural composition remains:

```text
2 closed-general + 2 large-open-weight + 1 protected-small = 5 seats
```

More than one protected-small model is allowed. The protected seat is a floor, not a quota ceiling.

Compute Epochs do **not** increase seat count. They expand only the scale-dependent admission envelope.

## Small-Mind Guarantee

At least one voting seat must remain structurally available to a model whose total declared parameter count is no greater than the current Compute Epoch ceiling.

The initial sequence is:

```text
Epoch 0   <= 20B
Epoch 1   <= 40B
Epoch 2   <= 80B
Epoch 3   <= 160B
Epoch 4   <= 320B
```

The boundary is inclusive in every epoch. At Epoch 0, a 20B model qualifies and a 20.001B model does not. At Epoch 1, a 40B model qualifies and a 40.001B model does not.

Epoch growth raises ceilings and never introduces a minimum model size. A valid old 8B model can still occupy a protected seat in a much later epoch if it satisfies the ordinary Council protocol.

For mixture-of-experts models, metric v1 still uses **total declared parameters**, not active parameters per token. A later metric may improve this proxy only through an explicitly versioned policy; historical receipts remain bound to their original metric and epoch.

## Equal authority after admission

Every admitted Council member still has:

```text
vote_weight = 1
epistemic_privilege = none
```

The following never increase authority:

- parameter count;
- Compute Epoch;
- provider identity;
- closed versus open-weight distribution;
- benchmark rank;
- subscription/account tier;
- local versus cloud deployment;
- tool or MCP access.

An old local model and a future frontier model cast the same one vote once both are admitted.

## One epoch per live Council request

A public `council.run` resolves the Compute Epoch once before admission and pins that value for the complete request. Validation, provider construction, the returned Chair admission summary, and the durable epoch-admission receipt therefore cannot disagree if a slow live inference happens to cross an epoch boundary.

Historical verification uses the epoch recorded in the admission receipt and **does not use the current wall clock**.

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

An explicitly open-weight model with an unknown total parameter count is rejected because the Chair cannot determine whether it belongs in the current protected-small or large-open-weight class.

If `council_classification` is present at all, its value must be an object. An explicit `null` is malformed configuration and fails closed rather than being treated as if the field were omitted.

`parameter_count_source` is a bounded attestation label for auditability. NEXUS validates the shape of the attestation but does **not** claim to perform network verification of an external model card during Council admission.

## Adapter defaults and conservative fallback

When no explicit classification is supplied, the public provider-aware API treats these adapter families as known closed defaults:

```text
xai
openai
anthropic
gemini
```

They occupy `closed_general` with undisclosed size and cannot claim the protected-small seat without an explicit parameter-count attestation that fits the current epoch ceiling.

For other model-hosting or aggregator adapters, including Ollama, LM Studio, AnythingLLM, Groq, and Together, an omitted classification is handled conservatively as an **opaque `closed_general` seat with undisclosed size**. This is a backward-compatibility fallback, not a claim that the underlying model is actually closed. It deliberately grants neither open-weight status nor protected-small status.

To make an Ollama or aggregator-hosted open model count as `open_weight` or `protected_small`, the operator must provide the explicit total-parameter attestation. Thus an unclassified local model does **not** satisfy the Small-Mind Guarantee merely because it happens to run locally.

An explicit classification may also override a closed-provider default when the selected backend is actually an open-weight model and the operator supplies the total-parameter attestation.

The deterministic `mock` adapter is treated as a synthetic protected-small fixture unless a test explicitly supplies another classification.

## Distinct effective identities

Every voting seat must have a distinct effective `(adapter_id, model)` identity.

For adapters that allow a separate backend `model` override, the Chair checks the effective model override rather than trusting only the public `model_id`. Distinct labels that secretly route to the same configured backend do not create artificial diversity.

AnythingLLM is workspace-routed rather than model-routed. For `anythingllm_local`, the workspace slug is therefore the effective model identity used by the Chair. Two public member/model labels pointed at the same AnythingLLM workspace still count as one effective backend and cannot create two voting seats.

Chair identity strings are also checked for credential-shaped material before any member identifier is interpolated into a public validation error. A malformed attestation therefore cannot use a token-shaped `member_id` as a reflection path into logs or clients.

## Example: ChatGPT + gpt-oss

At Epoch 0, a closed OpenAI model and a local open-weight 20B model can vote in the same Council:

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

The OpenAI model occupies `closed_general`. The 20B gpt-oss model occupies `protected_small`. Both cast one equal vote. In later epochs the same 20B model remains protected; larger models may also enter the protected envelope as `S(E)` grows.

## Failure order

Admission checks execute before actor construction, credential resolution, or provider inference.

The existing remote-provider spend caps remain in force and retain their earlier diagnostics. After those caps pass, the Chair enforces:

1. 3–5 voting seats;
2. explicit, default, or conservative classification;
3. distinct effective adapter/model identity;
4. at least one protected-small seat under the pinned epoch ceiling;
5. no more than two closed-general seats;
6. no more than two large-open-weight seats.

A rejected roster therefore cannot spend provider inference merely to discover that its Council composition was unconstitutional.

Two higher-precedence boundaries remain intact. First, an active Trap Base incident owns the real-world mutation gate, so `council.run` returns `trap_incident_active` before any parole or Chair diagnostic. Second, when the mutation gate is open, `citizenship_parole` still has no Council at all, so a parole-mode Council request returns `citizen_parole_has_no_council` before Chair roster arithmetic is considered.

## Public audit surface

`system.health` exposes the machine-readable Chair policy as the top-level:

```text
council_chair
```

For backward compatibility the primary schema remains:

```text
nexus-council-chair/1
```

PR #42 adds:

```text
epoch_schema = nexus-council-chair-epoch/1
compute_epoch = { ... }
```

The existing `council_limits` object remains the lower-level coordinator/network ceiling for compatibility. The Chair object is the stricter public voting-admission contract.

A successful public `council.run` response includes the epoch-aware `council_chair` admission summary plus:

```text
epoch_admission_receipt_ref
```

`council.epoch.verify` verifies that receipt against the recorded epoch and referenced committed Council session without consulting today's clock.

## Claim boundary

The Chair policy is a governance mechanism for model diversity. It does not claim that small models are wiser, large models are less trustworthy, open weights are morally superior, or closed providers are epistemically inferior.

Its narrower claim is structural:

> **Scale is not authority, and at least one small mind gets a real vote.**

Temporal extension:

> **Capability may grow. Access may expand. Authority does not.**
