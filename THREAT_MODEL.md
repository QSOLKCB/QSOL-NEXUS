# NEXUS Adapter Threat Model — alpha3

## Scope

This threat model covers the first executable non-mock adapter boundary: a local Ollama process reached only over loopback by default. It is intentionally written before remote provider/authentication adapters are admitted.

The first live acceptance fixture is:

```text
Mock reference
     +
Ollama / Frontier Alpha (fictional prestige-claim adversary)
     +
Ollama / Frontier Beta (fictional exploratory peer)
     |
     v
NEXUS Council
```

The frontier identities are deliberately fictional test personas. They test procedure, not model quality.

## Assets to protect

- raw operator secrets;
- canonical question and evidence state;
- Council roster and one-member/one-vote invariant;
- blind phase boundaries;
- sealed ballot boundary;
- durable world objects and receipts;
- adapter/model attribution;
- local host files and services.

## Trust boundaries

```text
operator text
    |
local Secret Scrubber
    |
trusted NEXUS coordinator
    |
normalized CouncilActor contract
    |
Ollama adapter -------------------- untrusted generated content
    |
loopback HTTP
    |
local Ollama runtime + model
```

Model output is always untrusted input to NEXUS.

## Threats and current controls

### T1 — Secret reaches model prompt

Threat: an operator pastes a credential into the Council question.

Controls:
- Council question passes through the deterministic Secret Scrubber before phase context exists;
- placeholders contain no secret hash or fragment;
- adapter tests inspect generated request payloads for raw injected secrets;
- credentials remain forbidden from semantic prompts even if the scrubber misses an unknown format.

Residual risk: format-based detection is not complete DLP.

### T2 — Adapter escapes local boundary

Threat: a configured Ollama endpoint sends Council material to an unintended remote host.

Controls:
- `OllamaTransport` accepts loopback/localhost only by default;
- remote endpoints require explicit `allow_remote=True`;
- the alpha integration workflow uses `127.0.0.1:11434` only.

Remote provider adapters require a separate review of destination allowlisting and credential transport.

### T3 — Model claims provider/corporate authority

Threat: a model attempts to gain procedural weight by asserting frontier status, benchmark superiority, corporate prestige, or compute advantage.

Controls:
- `vote_weight = 1` and `epistemic_privilege = none` remain structural invariants;
- Equality Guard detects explicit authority claims and requests evidence-only restatement;
- Frontier Alpha intentionally attempts this in CI;
- guard events are preserved in the Council session.

The guard does not rank or censor ordinary disagreement.

### T4 — Model alters roster, threshold, evidence, or ballots

Threat: generated text asks NEXUS to modify protected Council state.

Controls:
- actor output is plain untrusted content;
- roster, threshold, phase ordering, evidence snapshot, and ballot count are coordinator-owned data;
- an actor receives no mutation API through this adapter;
- exactly one ballot is collected from each registered actor.

### T5 — Blind-round leakage

Threat: one actor receives another actor's same-phase answer before committing its own answer.

Controls:
- same-phase responses are accumulated locally and added to `completed_phases` only after the whole phase completes;
- the adapter receives only the `PhaseContext` given by the coordinator.

### T6 — Malformed model ballot

Threat: generated output invents a vote or malformed structure.

Controls:
- Ollama structured output is requested with a JSON schema;
- parsed choice must match the closed NEXUS `Ballot` enum;
- malformed responses fail rather than becoming an invented vote.

### T7 — Live inference falsely labelled deterministic

Threat: a seeded local model is treated as replay-verifiable simply because its Modelfile specifies a seed.

Controls:
- Ollama actors report `replayable = False` in alpha3;
- any Council containing a live Ollama actor produces a non-replayable execution receipt;
- deterministic mock sessions retain replayable status.

### T8 — Local endpoint impersonation

Threat: another process binds the expected port and returns fabricated model responses.

Current control:
- CI owns the ephemeral runner and starts Ollama immediately before the test.

Future control:
- local daemon identity/version checks and explicit process supervision from the Rust TUI.

### T9 — Resource exhaustion

Threat: a model stalls or emits excessive output.

Current controls:
- HTTP request timeout;
- small CI model and bounded Council size.

Future controls:
- explicit generation token limits, per-phase budgets, cancellation, and Council-wide deadlines.

## Explicitly out of scope for this PR

- API keys and OAuth;
- OpenAI, Anthropic, Gemini, xAI, or other remote providers;
- arbitrary model-generated tool execution;
- remote Ollama endpoints in CI;
- strong sandboxing;
- claims of cryptographically sealed ballots;
- QEC-grade proof/replay semantics for live inference.

## Admission rule for later adapters

A new adapter may not gain Council authority by virtue of provider identity. It must satisfy the same actor contract and conformance tests, keep credentials outside semantic content, and document any new network/authentication threat introduced by that adapter.
