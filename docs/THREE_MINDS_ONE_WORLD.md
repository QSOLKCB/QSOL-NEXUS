# NEXUS 2.0-alpha11 — Three Minds, One World

> **Multiple minds. One world. Shared evidence. Equal voice.**

Alpha11 is the explicit shared-world demonstration promised by the NEXUS roadmap.
It is deliberately **sequential**, not a disguised three-seat chat: one model leaves a
content-addressed contribution in the world, a different model arrives later and reads
it, and a third model arrives later still reads a bounded deterministic instrument result
without deleting or rewriting the earlier work.

The permanent runner is:

```text
tools/nexus_three_minds_demo.py
```

The implementation is split by responsibility:

```text
src/nexus_runtime/three_minds.py             # shared-world coordinator
src/nexus_runtime/three_minds_validation.py  # member/mode/question validation
src/nexus_runtime/three_minds_instrument.py  # bounded primality instrument
```

## Demonstration contract

```text
Mind A enters
  -> reads exact task question + integer fixture
  -> proposes falsifiable hypothesis + test
  -> leaves immutable hypothesis object

Mind B enters later
  -> reads exact task + Mind A object
  -> independently reproduces / critiques
  -> leaves immutable reproduction object

NEXUS coordinator
  -> executes nexus.integer-primality/1 as a fixed alpha11 stage
  -> persists the exact tested values + result as immutable evidence

Mind C enters later
  -> reads task + A + B + coordinator-owned instrument result
  -> interprets the result and attempts falsification
  -> never receives false provenance claiming it invoked the instrument

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

## Exact task visibility

The task object's model-readable `content` contains the complete accepted custom question
and the complete integer fixture. The question is bounded to **1,500 characters** so the
question plus the worst-case 128-value fixture stays inside the ordinary NEXUS per-object
evidence budget rather than being silently truncated before Mind A or Mind B sees it.

The instrument evidence string likewise always lists the exact tested values, including
when every value is prime. A stage is therefore never described as evidence-based when the
relevant question or fixture was hidden only in non-model-readable metadata.

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

### Optional JSON archive

```bash
PYTHONPATH=src python3 tools/nexus_three_minds_demo.py \
  --world /tmp/nexus-alpha11-world \
  --json-out /tmp/alpha11-run.json
```

`--json-out` is **never overwritten**. The runner reserves the output path with exclusive
creation **before** constructing the runtime or contacting a model/provider. This prevents
an already-existing or unusable output path from spending provider money and mutating the
world before failing.

CLI exit codes relevant to the archive path are:

```text
0  success
2  runtime / validation / I/O failure
3  JSON output already exists; no runtime/model call was started
```

If a later run step fails after the runner successfully reserved a brand-new output path,
the runner removes its own empty reservation where possible. It never removes or truncates
an output path that existed before invocation.

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

For this demonstration, if a member object supplies the optional backend `model` field,
it must exactly equal `model_id`. This is intentionally stricter than the generic actor
surface: alpha11 refuses a declared identity that differs from the model the backend would
actually execute. Distinctness is therefore checked against the effective declared
adapter/model identity rather than an arbitrary alias.

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

The coordinator, not Mind C, executes this fixed probe after Mind B's contribution. The
instrument object records `execution_initiator = nexus_three_minds_demo` and separately
records the Mind C identity to which the result is made available. Mind C's role is
interpretation/falsification from evidence, not instrument invocation.

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

The final run object stores the entire ordered lineage, the coordinator instrument actor,
and the bounded instrument evidence state. A normal `receipt.verify` call must resolve
every input ref and the final run ref.

## Equality and governance boundary

This demonstration is not itself a Council vote. It creates no extra seat and no ballot.
Member objects are nevertheless required to satisfy the same constitutional metadata:

```text
vote_weight = 1
epistemic_privilege = none
```

Exactly three distinct `member_id` values and three distinct effective adapter/model
identities are required. Validation errors identify the failing mind index and, when
available, its `member_id` and field so operator misconfiguration is diagnosable before
a provider call. Open/closed status, provider branding, account tier, parameter count,
or model size does not alter the sequence or authority.

If a requested actor is already contained by NEXUS Failsafe, normal `actor.chat` routing
still applies; the stage records that a replacement occurred rather than silently
pretending the original model spoke.

## Mode API boundary

The coordinator validates the `world.modes` response shape separately from mode lookup.
A non-list catalogue, non-object catalogue item, or item without a non-empty `mode_id` is
reported as an API-contract failure. Only a structurally valid catalogue that lacks the
requested mode produces `unknown world mode`.

## Evidence and persistence boundary

Each later mind receives earlier objects through the normal bounded NEXUS evidence path.
The demonstration does not concatenate hidden provider state or invent shared model
memory. The **WorldStore objects are the memory**.

For mock-only runs, `execution_replayable=true` because every model contribution is
replayable. Any live/local/cloud model makes the run non-replayable at the model-execution
layer, while the persisted protocol/evidence refs remain inspectable and tamper-evident.

The demonstration proves only that the configured NEXUS runtime can preserve and pass a
shared lineage through three sequential actor boundaries plus one bounded coordinator-run
instrument. It does not prove:

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

Regression coverage additionally pins exact task/fixture visibility, coordinator-owned
instrument provenance, effective-model validation, malformed `world.modes` diagnostics,
and preflight output reservation before any runtime/provider call.

An operator-authorized live heterogeneous archive remains a **manual acceptance run**.
It should record the chosen model IDs, auth-profile names (never credentials), git commit,
run/receipt refs, and any provider/runtime limitations.

That split is intentional: CI proves the contract without spending money or depending on
external model availability; a live run demonstrates the same contract against real
provider boundaries.

## Post-alpha7/alpha8/alpha9 completion upgrade

The original alpha11 sequence above remains canonical. After alpha7 instrument admission,
alpha8 persistent-world/LATTICE work, and alpha9 provider setup were completed, alpha11 was
upgraded rather than replaced.

The coordinator now preserves the original model-stage objects **and** adds a second,
machine-verifiable integration layer.

### Alpha7 admitted receipt lineage

Mind A now gets a coordinator-owned baseline execution over every supplied value except the
last one. Mind B receives that immutable record and independently reruns the exact same
admitted instrument input.

Both baseline records contain the complete:

```text
instrument-intent
instrument-execution
instrument-receipt
```

bundle produced by `nexus-instrument-admission/1`.

Mind B's replay must be byte-identical to Mind A's complete bundle. The full fixture is
then executed through the same admitted `run_instrument` path before Mind C interprets it.
All three bundles are revalidated with `verify_instrument_receipt`.

```text
REPLAY != EMPIRICAL_CONFIRMATION
INSTRUMENT_RESULT != TRUTH
```

The original `instrument_result` object remains for compatibility and model-readable exact
fixture visibility, but it now also binds the alpha7 execution and receipt refs.

### Alpha8 typed workflow lineage

Alongside the original free-form model-stage lineage, alpha11 now records the same workflow
through the validated alpha8 object types:

```text
hypothesis: PROPOSED -> CHALLENGED -> RETIRED | CHALLENGED
experiment: PLANNED -> OBSERVED -> CLOSED
```

The final hypothesis is `RETIRED` when the supplied fixture contains a composite, otherwise
it remains `CHALLENGED`. These are workflow labels only.

Relations connect the model-stage and instrument records without promoting them:

```text
interprets
replays
critiques
bears_on
verifies_receipt_for
```

```text
PERSISTENT_LINEAGE != TRUTH
VERIFIED_DESCENDANT != SEMANTIC_TRUTH
```

The `three_minds_verified_descendant` object explicitly sets
`semantic_truth_claimed=false`; its verified scope is only the admitted instrument receipt
and exact input.

### Explicit LATTICE handoff

The shared task receives an ordinary storage-only LATTICE presence lineage:

```text
Observatory  L[0,0,0]
    ->
Archive      L[0,0,1]
    ->
Agora        L[0,1,1]
    ->
Observatory  L[1,1,1]
```

Every transition uses the existing validated `world.place` / `world.move` operations and
adjacent named-region topology. `verify_three_minds_integration` requires exactly one
placement plus three moves and requires the final region to be Observatory.

```text
LATTICE_POSITION != COGNITIVE_COORDINATE
```

### Restart verification

`verify_three_minds_integration(api, result)` reopens no hidden state. It verifies only the
persisted refs available through the supplied NEXUS runtime:

- the ordinary integration receipt resolves;
- Mind A and Mind B alpha7 bundles still verify;
- Mind B's baseline replay remains byte-identical;
- the full-fixture instrument receipt still verifies;
- LATTICE handoff lineage remains valid;
- the final typed hypothesis retains workflow-only semantics;
- the typed experiment is `CLOSED` without claiming empirical truth;
- the receipt-verified descendant still refuses a semantic-truth claim.

The test suite calls this verifier again after reopening the file-backed NEXUS world.

### Deterministic minority-report Council

The sequential three-minds run still creates no vote. A separate optional reference Council
can now be run with:

```bash
PYTHONPATH=src python3 tools/nexus_three_minds_demo.py \
  --world /tmp/nexus-alpha11-world \
  --reference-council
```

Its fixed network-free roster is:

```text
Mind-A  skeptical  -> TEST_FURTHER
Mind-B  balanced   -> TEST_FURTHER
Mind-C  supportive -> ACCEPT_WITH_CHANGES
```

The default two-thirds rule therefore leaves exactly one `ACCEPT_WITH_CHANGES` minority
report. Alpha11 then requires that report to remain discoverable through
`world.minority.search`, with `search_is_evidence=false`.

```text
MINORITY_REPORT != EVIDENCE_PROMOTION
MULTI_MODEL_CONSENSUS != EVIDENCE
```

### Council using the configured roster

The runner can also send the same three configured members into the ordinary NEXUS Council:

```bash
PYTHONPATH=src python3 tools/nexus_three_minds_demo.py \
  --world /tmp/nexus-alpha11-world \
  --council
```

For an all-mock roster, that remains hermetic. If any configured member is non-mock, the
extra Council calls require an explicit flag **before runtime construction**:

```text
--authorize-council
```

This is separate from the three sequential model-stage calls already requested by the
original heterogeneous alpha11 demo. It prevents accidentally turning a normal sequential
run into an additional paid/provider Council workload.

For example, an xAI + loopback Ollama + mock Council can be configured using the same
existing member JSON and auth-profile references used elsewhere in NEXUS. No raw provider
credential is accepted by this new Council option.

Provider identity still cannot set vote weight or epistemic privilege:

```text
PROVIDER_IDENTITY != VOTE_WEIGHT
PROVIDER_IDENTITY != EPISTEMIC_PRIVILEGE
MULTI_MODEL_CONSENSUS != EVIDENCE
```

### Machine contract

The completion layer is frozen in:

```text
contracts/three-minds-one-world.json
```

and hermetic CI exercises the existing `tests/test_three_minds_demo.py` module rather than
adding another Python test file, preserving the pinned release-hardening test inventory.
