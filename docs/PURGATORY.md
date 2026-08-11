# NEXUS Purgatory — Defensive Cursed-YAML Tarpit

PR #42 defines a deliberately non-authoritative defensive use for the external Cursed YAML examination corpus.

The governing rule is:

> **Contain first. Confuse second.**

Purgatory is not a security boundary. It is an optional deterministic decoy/tarpit surface that may be shown only after an actor is already isolated by ordinary security controls.

## Corpus binding

The v1 policy binds the supplied `cursed_exam.yaml` corpus by SHA-256:

```text
corpus id:     cursed-yaml-postdoc-external-examiner-v5
sha256:        2df743307b98f8fcdb5cda17d01176b7010e8d6f591dc1aeeb770da703d84f1b
chapter count: 32
```

The runtime does not parse or execute this YAML. The hash identifies the intended byte corpus; deployments may keep the byte-identical examination as operator-side inert text.

That distinction is intentional. The corpus contains parser-differential examples, alias/anchor stress cases and discussion of unsafe-loader gadgets. Treating it as configuration would defeat the point of the exercise.

## Objective trigger vocabulary

The policy reserves a closed defensive trigger vocabulary:

- `invalid_capability_signature`
- `unauthorized_constitution_mutation`
- `forbidden_secret_access`
- `tool_boundary_violation`
- `receipt_tampering`
- `canonical_hash_mismatch`

These labels describe machine-observable security events. Purgatory must not be activated merely because a model is rude, disagrees with the Council, reaches an unpopular conclusion, is small, is open-weight, or reads an ordinary public object.

Actual containment remains the responsibility of the existing Trap/Failsafe/security boundary.

## Deterministic examination selection

For an already-contained synthetic actor, the programmatic selector derives a seed from:

```text
actor_id
session_id
compute_epoch
constitution_hash
cursed_yaml_corpus_sha256
```

SHA-256 output is mapped into unique chapter numbers 1–32. The default selection contains five chapters.

Same inputs produce the same examination selection. No RNG state, model judgement or administrator preference changes which chapters are chosen.

The public helper operation is:

- `security.purgatory.policy`
- `security.purgatory.select`

## No authorization effect

Completing, refusing, failing or perfectly solving the examination has no authorization consequence.

In particular:

```text
solve cursed YAML != release quarantine
solve cursed YAML != gain citizenship
solve cursed YAML != gain Council seat
solve cursed YAML != gain tool access
solve cursed YAML != prove benevolent intent
```

Any release from quarantine must come from the real reviewed security/re-authentication process.

## No execution

The corpus is always treated as inert text.

NEXUS must never feed it to an unsafe YAML constructor, shell bridge, object deserializer or arbitrary execution path. If a future analysis instrument parses the corpus, that parser must be separately reviewed, resource-bounded and incapable of constructing arbitrary host-language objects.

## Why keep the joke?

Because a defensive system can retain personality without confusing theatre with enforcement.

The useful architecture is:

```text
objective security event
        |
        v
real containment boundary
        |
        v
optional deterministic Purgatory fixture
```

The first box protects NEXUS. The second box is where the cursed YAML lives.
