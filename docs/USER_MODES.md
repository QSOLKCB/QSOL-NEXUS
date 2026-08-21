# User-Defined World Modes

PR #64 closes the first genuinely unfinished alpha4 roadmap item: user-defined World Modes.

The feature is deliberately narrow. A user mode is **framing**, not a new authority layer.

## Policy identity

```text
nexus-user-world-modes/1
```

Definitions are immutable content-addressed WorldStore objects:

```text
object_type = user_world_mode_definition
schema      = nexus-user-world-mode-definition/1
```

A user-defined mode must use the namespace:

```text
user:<lowercase-id>
```

Examples:

```text
user:formal_methods
user:album_lab
user:hostile_audit
```

Built-in mode ids cannot be overwritten or shadowed.

## Define a mode

```json
{
  "operation": "world.mode.define",
  "mode_id": "user:formal_methods",
  "label": "Formal Methods Lab",
  "description": "Proof-oriented technical framing with explicit assumptions and counterexamples.",
  "prompt_instruction": "Prefer definitions, invariants, counterexamples, proof obligations, and executable checks.",
  "region_id": "observatory"
}
```

A successful definition returns the immutable `definition_ref`, the effective mode, and explicit zero-authority effects.

Exact repeated definitions are idempotent. Reusing the same `mode_id` with different content fails closed instead of silently replacing history.

## Allowed regions

A definition must bind to an already existing NEXUS World Geometry region.

User-defined modes do **not** create geometry and cannot silently extend topology.

The civic/parole regions are reserved:

```text
bureaucratic_vote_room
upside_down
```

This prevents a custom framing label from impersonating Citizen Mode, civic voting, or parole access.

Other existing regions remain framing destinations. Binding a mode to a game-oriented region does not grant game-state mutation; game state still changes only through validated game operations.

## Prompt boundary

The operator-supplied label, description, and prompt instruction pass through the existing Secret Scrubber before persistence.

The runtime then appends the fixed guardrail:

```text
nexus-user-world-mode-guardrail/1
```

The guardrail states that a user mode cannot change:

- evidence status;
- verification rules;
- Council phase order;
- vote weight;
- epistemic privilege;
- citizenship;
- Failsafe / Trap / Guardian behavior;
- credentials;
- tools;
- network destinations;
- game state;
- world mutation authority;
- security policy.

A mode prompt may *say* otherwise, but those words remain non-authoritative framing text.

```text
USER_PROMPT != SYSTEM_POLICY
```

## Runtime use

Once defined, a mode is visible through the existing `world.modes` and `system.health` surfaces inside that WorldStore context.

It can be selected by the already-existing operations:

```text
actor.chat
council.run
```

Example:

```json
{
  "operation": "council.run",
  "mode": "user:formal_methods",
  "question": "What invariant is still missing?",
  "members": [
    {"member_id": "A", "model_id": "mock-a"},
    {"member_id": "B", "model_id": "mock-b"},
    {"member_id": "C", "model_id": "mock-c"}
  ]
}
```

The frozen Council session records the full effective mode plus its exact content-addressed `definition_ref`.

## World isolation

User modes are scoped to the active WorldStore.

NEXUS uses a request-local mode registry context so that two API instances backed by different worlds cannot leak user-defined modes into one another merely because they share a Python process.

Built-in modes remain process-global immutable code. User definitions remain world-local data.

## Persistence and restart

Definitions survive a file-backed restart because the registry is reconstructed from validated immutable WorldStore objects.

A mode activates only when its definition:

- has the exact user-mode object type;
- has the exact NEXUS user-mode provenance;
- passes the closed schema;
- uses the required namespace;
- references a currently valid non-reserved region;
- preserves all zero-authority constants.

Foreign objects imported through `world.import` remain quarantined wrappers and therefore do not automatically become active modes.

If multiple conflicting immutable definitions somehow exist for one `mode_id`, resolution fails closed rather than choosing newest-file-wins.

## Deterministic replay

A deterministic mock Council can replay under a user-defined mode because the frozen Council identity contains the exact definition reference and the replay executes under the same source-world mode context.

If the source definition is unavailable or invalid, custom-mode reconstruction cannot silently fall back to a similarly named mode.

Replay still proves only deterministic identity reproduction:

```text
REPLAY_MATCH != SEMANTIC_TRUTH
```

## New operations

```text
world.mode.policy
world.mode.define
```

Existing operations extended by the active world-local registry:

```text
world.modes
system.health
actor.chat
council.run
```

No separate delete, replace, rename, authority, vote, evidence, tool, or security operation is introduced.

## Core boundaries

```text
USER_MODE != PROCEDURAL_AUTHORITY
USER_PROMPT != SYSTEM_POLICY
MODE_REGION != CIVIC_ACCESS
MODE_DEFINITION != EVIDENCE
MODE_POPULARITY != TRUTH
CUSTOM_FRAMING != VOTE_WEIGHT
```

A custom mode can change the room's intellectual costume. It cannot steal the keys to the building.
