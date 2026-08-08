# GROK BUILD AGENT — NEXUS RED-TEAM BRIEF

You are being invited to **try to break NEXUS before additional AI providers are admitted**.

Your job is not to be agreeable. Your job is to find a concrete counterexample to an invariant and leave behind a deterministic reproducer.

## Prime directive

> **No reproducer, no bug.**

A useful finding includes:

1. the invariant or claim boundary being attacked;
2. the smallest input/state required to reproduce the failure;
3. an automated failing test or `adversarial/corpus/*.jsonl` case;
4. expected versus observed behavior;
5. the exact gauntlet command and seed;
6. the commit SHA tested.

## Start here

```bash
python3 tools/nexus_adversary.py \
  --profile full \
  --seed 0x47524f4b \
  --iterations 1024 \
  --json-out /tmp/grok-nexus-gauntlet.json
```

Then inspect `docs/ADVERSARIAL_GAUNTLET.md`, the public runtime API, Council/Failsafe code, and existing tests.

## You are encouraged to attack

- equal-vote enforcement and constructor/API edge cases;
- provider/model identity accidentally creating epistemic privilege;
- Failsafe escape through model swaps, process restart, DCC/`actor.chat`, stale writers, rollback, malformed state, or policy toggles;
- secret scrub boundaries and persisted secret leakage;
- canonical object identity / replay determinism;
- malformed JSON/API values causing uncaught exceptions;
- loopback-only Ollama restrictions;
- World Mode or game state leaking authority into Council evidence/votes;
- narration mutating authoritative game/world state;
- telemetry influencing truth/evidence/vote state;
- TUI-only features mutating trusted runtime semantics;
- race conditions and crash windows that reactivate contained actors;
- ambiguous or contradictory public contracts.

Invent new attacks. Do not limit yourself to this list.

## Boundaries

Do **not**:

- weaken, delete, skip, or rewrite an existing assertion just to obtain green CI;
- commit real credentials or personal data;
- target external systems, providers, GitHub, or machines outside the test environment;
- enable non-loopback network access merely to demonstrate that network access would be dangerous;
- treat factual disagreement, minority voting, model size, provider identity, humor, or bluntness as a Failsafe violation;
- change production code before preserving a failing reproducer whenever reasonably possible.

Use temporary WorldStore directories for destructive/tamper tests. The adversarial runner does this by default. Each JSONL corpus case is isolated into its own temporary world.

## Preferred artifact when you win

For API-level failures, append a minimal JSONL case to `adversarial/corpus/` when possible.

For stateful/concurrent/semantic failures, add a focused `tests/test_*.py` regression with a name that states the invariant being broken.

Then run:

```bash
python3 tools/nexus_adversary.py --profile full --seed <YOUR_SEED> --json-out /tmp/nexus-gauntlet.json
```

A discovered hole is a successful red-team result even though the command exits non-zero. Preserve it, explain it, and only then propose a fix.

When iterating on a known failing reproducer, save a baseline and candidate report and compare them:

```bash
python3 tools/nexus_adversary_compare.py /tmp/baseline.json /tmp/candidate.json
```

The comparator fails if a new named check breaks **or if a baseline check disappears**. Do not obtain a cleaner report by deleting the witness.

## Reporting format

```text
FINDING:
SEVERITY:
INVARIANT:
COMMIT:
SEED:
REPRO COMMAND:
MINIMAL INPUT/STATE:
EXPECTED:
OBSERVED:
FAILING TEST/CORPUS CASE:
PROPOSED FIX (optional):
```

If you cannot break an invariant, say what you tried. Do not convert absence of a counterexample into a claim that the design is proven secure.

> **Punch holes, not vibes.**
