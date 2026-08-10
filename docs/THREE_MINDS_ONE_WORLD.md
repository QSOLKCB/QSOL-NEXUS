# NEXUS 2.0-alpha11 — Three Minds, One World

> **Multiple minds. One world. Shared evidence. Equal voice.**

Alpha11 is the explicit shared-world demonstration promised by the NEXUS roadmap.
It is deliberately **sequential**, not a disguised three-seat chat: one model leaves a
content-addressed contribution in the world, a different model arrives later and reads
it, and a third model arrives later still, invokes a bounded deterministic instrument,
and attempts falsification without deleting the earlier work.

The permanent runner is:

```text
tools/nexus_three_minds_demo.py
```

The orchestration and instrument contract live in:

```text
src/nexus_runtime/three_minds.py
```

## Demonstration contract

```text
Mind A enters
  -> reads task object
  -> proposes falsifiable hypothesis + test
  -> leaves immutable hypothesis object

Mind B enters later
  -> reads task + Mind A object
  -> independently reproduces / critiques
  -> leaves immutable reproduction object

Mind C enters later
  -> reads task + A + B
  -> requests nexus.integer-primality/1
  -> instrument result becomes immutable evidence
  -> Mind C attempts falsification from the complete lineage

NEXUS
  -> preserves every stage
  -> creates three_minds_run
  -> creates and verifies a normal receipt
```

The default benchmark hypothesis is intentionally small and boring:

```text
all supplied integers are prime
```

The default fixture includes `25`, so the deterministic instrument has a concrete
falsifier. This is not intended as an impressive mathematics benchmark. It exists so
the architecture can demonstrate a clean difference between:

```text
model proposal / interpretation
        versus
bounded deterministic evidence
```

## Quick hermetic run

No model server or cloud credential is needed for the default three-mock run:

```bash
PYTHONPATH=src python3 tools/nexus_three_minds_demo.py \
  --world /tmp/nexus-alpha11-world
```

The output is canonical JSON containing refs for:

```text
task_ref
hypothesis_ref
reproduction_ref
instrument_result_ref
falsification_ref
run_ref
receipt_ref
```

Run the command again with the same persistent world directory and the earlier objects
remain inspectable. The new run never edits or replaces them.

## Heterogeneous live run

The runner accepts the same member objects already admitted by `actor.chat`. Raw cloud
credentials are **not** command-line arguments; remote models use existing NEXUS auth
profiles.

Example shape:

```bash
PYTHONPATH=src python3 tools/nexus_three_minds_demo.py \
  --world .nexus-alpha11-world \
  --auth-root .nexus-auth \
  --mind-a '{
    "member_id":"LocalOpen",
    "model_id":"YOUR_OLLAMA_MODEL",
    "adapter_id":"ollama"
  }' \
  --mind-b '{
    "member_id":"OpenAI",
    "model_id":"YOUR_OPENAI_MODEL_ID",
    "adapter_id":"openai",
    "auth_profile":"default"
  }' \
  --mind-c '{
    "member_id":"Gemini",
    "model_id":"YOUR_GEMINI_MODEL_ID",
    "adapter_id":"gemini",
    "auth_profile":"default"
  }'
```

Use the repository's normal authentication and model-discovery commands to choose
provider model IDs. The runner does not add a new credential path or arbitrary remote
endpoint override.

The same harness can use xAI, Anthropic, Groq, Together, LM Studio, AnythingLLM, or a
loopback OpenAI-compatible model because actor creation remains owned by the existing
provider-aware NEXUS API.

## The first deliberately tiny instrument

Alpha11 includes one **versioned, bounded, deterministic** evidence-producing
instrument:

```text
nexus.integer-primality/1
```

It accepts at most 128 exact integers in the inclusive range:

```text
2 .. 10,000,000
```

For every value it records:

```text
is_prime
smallest_factor   # null for prime values
```

The implementation is standard-library integer arithmetic only. It has no network,
shell, filesystem, dynamic-code, plugin, model, or floating-point path.

Its claim boundary is intentionally narrow:

> **Exact integer primality for the supplied bounded fixture only.**

A result of `all_prime=true` therefore means only that no supplied value falsified the
benchmark hypothesis. It is not a proof of a larger sequence rule. A composite value is
a direct falsifier for the fixed benchmark claim about that fixture.

This instrument is the smallest possible bridge toward the broader alpha7 instrument
architecture. It does **not** pretend that general QEC, SPECTRAL, SONIFICATION,
numerical, symbolic, or laboratory tool admission is complete.

## World objects and lineage

The demonstration creates the following ordinary content-addressed WorldStore objects:

```text
three_minds_task
three_minds_hypothesis
three_minds_reproduction
instrument_result
three_minds_falsification
three_minds_run
receipt
```

Every model stage records:

- sequence index;
- requested public member identity (`member_id`, `model_id`, `adapter_id`);
- effective model identity returned by `actor.chat`;
- exact evidence refs supplied to that stage;
- world mode and geometry region;
- previous-stage ref;
- content;
- claim status;
- whether Failsafe substituted the requested actor;
- `additional_votes_created = 0`.

The final run object stores the entire ordered lineage and the bounded instrument evidence
state. A normal `receipt.verify` call must resolve every input ref and the final run ref.

## Equality and governance boundary

This demonstration is not itself a Council vote. It creates no extra seat and no ballot.
Member objects are nevertheless required to satisfy the same constitutional metadata:

```text
vote_weight = 1
epistemic_privilege = none
```

Exactly three distinct `member_id` values and three distinct adapter/model identities are
required. Open/closed status, provider branding, account tier, parameter count, or model
size does not alter the sequence or authority.

If a requested actor is already contained by NEXUS Failsafe, normal `actor.chat` routing
still applies; the stage records that a replacement occurred rather than silently
pretending the original model spoke.

## Evidence and persistence boundary

Each later mind receives earlier objects through the normal bounded NEXUS evidence path.
The demonstration does not concatenate hidden provider state or invent shared model
memory. The **WorldStore objects are the memory**.

For mock-only runs, `execution_replayable=true` because every model contribution is
replayable. Any live/local/cloud model makes the run non-replayable at the model-execution
layer, while the persisted protocol/evidence refs remain inspectable and tamper-evident.

The demonstration proves only that the configured NEXUS runtime can preserve and pass a
shared lineage through three sequential actor boundaries plus one bounded instrument.
It does not prove:

- that a model understood the evidence;
- that a model is truthful, conscious, aligned, or intelligent;
- that model consensus is evidence;
- that the integer fixture is scientifically interesting;
- that every future instrument is safe or deterministic;
- that all persistent-world migration work is complete.

## CI / acceptance split

Normal CI uses two levels:

1. a three-mock restartable persistent-world run;
2. a hermetic heterogeneous path using mock + OpenAI + Gemini actor construction with
   patched provider generation, so no network or credential is required.

An operator-authorized live heterogeneous archive remains a **manual acceptance run**.
It should record the chosen model IDs, auth-profile names (never credentials), git commit,
run/receipt refs, and any provider/runtime limitations.

That split is intentional: CI proves the contract without spending money or depending on
external model availability; a live run demonstrates the same contract against real
provider boundaries.
