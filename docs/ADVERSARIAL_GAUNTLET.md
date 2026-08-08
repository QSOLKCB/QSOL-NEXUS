# NEXUS Adversarial Gauntlet

The NEXUS Adversarial Gauntlet is a **hostile test runner** for build agents and humans who are explicitly trying to find counterexamples to NEXUS invariants before additional model providers are admitted.

It is not a security proof, model benchmark, moderation oracle, or authority layer.

> **Try to break the design. If you succeed, leave a reproducible test behind.**

## Run it

From the repository root:

```bash
python3 tools/nexus_adversary.py \
  --profile full \
  --seed 0xC0FFEE \
  --iterations 512 \
  --json-out /tmp/nexus-gauntlet.json
```

Profiles:

```text
probes  built-in invariant attacks + adversarial/corpus/*.jsonl
quick   probes + complete Python regression suite
full    quick + Rust tests + cargo check + rustfmt check
live    full + the existing real loopback-Ollama integration test
```

`full` is the recommended build-agent profile. `live` assumes the existing Ollama fixtures/models are already available locally; GitHub's dedicated Ollama workflow remains the canonical clean-room live acceptance environment.

The runner exits non-zero when any checked invariant breaks and optionally emits a machine-readable report using schema `nexus-adversarial-gauntlet/1`.

## Built-in attacks

The initial gauntlet probes:

- control/network/provider boundaries reported by `system.health`;
- content-addressed world identity determinism;
- secret-canary scrubbing through API response, inspected object, and persistent files;
- equal-vote / no-epistemic-privilege Council ingress;
- rejection of non-loopback Ollama endpoints;
- Shadow Realm binding to `(member_id, model_id)` across replacement and restart;
- deterministic malformed-request fuzzing over the public control API;
- the repository's complete Python and Rust regression suites.

Existing tests continue to cover deeper Failsafe rollback and multi-process locking, games, Pure History, telemetry, ordered parallelism, TUI behavior, and live Ollama behavior. The gauntlet orchestrates those tests rather than replacing them.

## Build-agent contract

A hostile build agent should produce a **minimal reproducible counterexample**, not an essay saying something might be wrong.

Recommended loop:

```text
1. Read the invariant / claim boundary.
2. Invent an attack.
3. Reproduce it in an isolated test or JSONL corpus case.
4. Run the gauntlet.
5. If the attack succeeds, keep the failing reproducer.
6. Fix production code only after the reproducer exists.
7. Run the full gauntlet again.
```

The agent may add ordinary `tests/test_*.py` regressions or request cases under `adversarial/corpus/`. It should not weaken existing assertions merely to obtain a green result.

Good attack targets include unequal vote authority, model/provider prestige leaking into epistemic authority, Failsafe escape through restart/model swap/DCC/stale writers, replay mismatches, secret leakage, remote endpoint escape, World Mode authority changes, game narration mutating substrate without an explicit game operation, rollback/tamper cases, malformed values escaping `NexusAPI.handle()`, and TUI state altering the trusted runtime contract.

Wrong answers, minority opinions, model size, provider identity, irreverence, or disagreement are **not** invariant violations by themselves.

## JSONL attack corpus

Every non-comment line is one independent test case:

```json
{"name":"weighted-seat","request":{"operation":"council.run","question":"q","members":[]},"expect":{"status":"error"}}
```

Supported expectations:

- `status`: exact response status;
- `error_code`: exact `error.code`;
- `contains`: strings that must occur in serialized response;
- `forbid`: strings that must not occur in serialized response.

Pass extra corpus files or directories with repeated `--corpus PATH`. The default `adversarial/corpus/*.jsonl` corpus is loaded automatically unless `--no-default-corpus` is set.

## Interpreting PASS

A green gauntlet means only:

> **The configured attacks did not break a checked invariant at this commit and seed.**

It is not a proof that NEXUS is secure, correct, aligned, or free of unknown failure modes. A useful adversarial corpus should grow whenever somebody finds a new way to make that statement false.
