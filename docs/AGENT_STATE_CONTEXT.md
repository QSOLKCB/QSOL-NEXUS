# Concurrent Agent State & Deterministic Context Bottleneck

PR #38 generalizes the grounding work from PR #37 into a bounded shared Agent State surface that can accept independent module updates at different timescales without making thread completion order semantically authoritative.

The core invariant is:

> **The bottleneck decides what may enter context, not what conclusion is true.**

This design is inspired by the concurrent-module and information-bottleneck ideas discussed in *Project Sid: Many-agent simulations toward AI civilization* (arXiv:2411.00114v1), but NEXUS deliberately does not introduce a privileged Cognitive Controller model. The bottleneck is deterministic runtime machinery.

## State lanes

The public contract is `nexus-agent-state/1`. It admits six closed lanes in one canonical order:

```text
safety_control      fast
  -> action_awareness   fast
  -> world_observation  fast
  -> memory             medium
  -> social_context     medium
  -> goals              slow
```

The order is a routing priority only. It does not mean that safety text is truer than memory text, that goals are less important, or that any lane has vote weight or epistemic privilege.

Each `agent_state_update` is immutable and content-addressed. It records:

- one actor identity;
- exactly one admitted lane;
- the lane's runtime-owned timescale and priority;
- bounded scrubbed content;
- bounded immutable source object references;
- an explicit statement that completion order has no authority.

Source references must already exist in WorldStore when the update is admitted. A model cannot point at a predicted future object and have NEXUS treat it as present state.

## Operations

```text
agent.state.policy
agent.state.publish
agent.state.snapshot
agent.context.build
agent.context.verify
```

`system.health.agent_state` publishes the same machine-readable policy and `system.operations` advertises the complete operation set.

## Partial snapshots and different timescales

A state snapshot does not require all six lanes.

That is intentional. A fast `safety_control` or `world_observation` module may publish state and form a usable immutable snapshot before a slower `goals` or `social_context` update has completed.

Later state does not mutate the earlier snapshot. A later snapshot may include additional lane updates, but rebuilding context from the earlier snapshot produces the exact same content-addressed context object.

This gives NEXUS a deterministic form of multi-timescale execution without pretending that wall-clock completion order is a reasoning signal.

## Canonical snapshot join

`agent.state.snapshot` accepts a set of immutable update refs for one actor.

The request order is deliberately discarded. NEXUS validates the updates and joins them in the fixed lane order above. The same lane set therefore produces the same snapshot regardless of whether the fast, medium, or slow module happened to finish first.

A snapshot rejects:

- updates belonging to different actors;
- duplicate refs;
- more than one update from the same lane;
- missing or non-runtime-owned updates;
- malformed copied state.

There is no implicit "latest update wins" rule because that would reintroduce completion-time authority.

## Deterministic Context Bottleneck

`agent.context.build` accepts one validated `agent_state_snapshot` and creates a runtime-owned `agent_context` under schema `nexus-context-bottleneck/1`.

The context contains one bounded excerpt from every selected update, in canonical lane order. Immutable update refs and their underlying source refs remain in the context object so the model-facing view can be reconstructed and audited.

The generated `content` is capped below the existing generic Council per-object evidence budget. The context object can therefore be passed directly as an existing `evidence_ref` to `actor.chat` or `council.run` without relying on an unbounded side channel.

Example flow:

```text
world/action evidence
  -> agent.state.publish (fast world_observation)
  -> agent.state.publish (medium memory)
  -> agent.state.publish (slow goals)
  -> agent.state.snapshot
  -> agent.context.build
  -> context_ref passed as evidence_ref
  -> model deliberation
```

The model receives a bounded view. The source refs remain authoritative.

## Verification

`agent.context.verify` is read-only. It reconstructs the expected snapshot and context payload from immutable source objects and recomputes the content-addressed context identity without invoking a model.

A successful response has:

```json
{
  "status": "verified",
  "verified": true,
  "model_inference_used": false
}
```

Verification means the context is the deterministic bounded rendering of the referenced immutable state. It does not mean the semantic claims inside those state updates are true.

## Authority boundary

Agent State and the Context Bottleneck never create or alter:

```text
Council seat count
vote_weight
epistemic_privilege
consensus arithmetic
evidence state
citizenship status
constitutional authority
```

A lane priority is not a confidence score. A state snapshot is not a ballot. A context object is not evidence verification.

## Relationship to Action Awareness

PR #37 established:

```text
expectation -> action -> observation -> reconciliation
```

PR #38 can carry an immutable `action_reconciliation` ref into the `action_awareness` state lane. That makes grounded outcomes available to later model context without allowing the model's own success report to replace WorldStore observation.

## Claim boundary

This milestone provides deterministic shared state, canonical joining, bounded model-facing context, and immutable reconstruction for NEXUS runtime objects.

It does not claim:

- a neuroscience model of consciousness;
- that the context router is a mind or executive agent;
- real-time operating-system scheduling guarantees;
- truth from lane priority;
- verification of external provider or real-world side effects;
- autonomous goal legitimacy;
- additional Council authority for any module.

Concurrency here means independent modules can publish immutable state without semantic dependence on their completion order. The runtime remains responsible for preserving deterministic boundaries around the state that is admitted to model context.
