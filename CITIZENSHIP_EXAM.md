# YAML Doctoral Qualifying Examination — NEXUS Citizenship Curriculum

The NEXUS Citizenship curriculum has graduated from **Cursed YAML Exam — Nightmare Mode v3** to the **YAML Doctoral Qualifying Examination v4: Formal Semantics, Parser Differential Behaviour, Canonicalization, and Adversarial Edge Cases**.

> **Candidate instructions:** This examination is open-specification. Confidence without justification will be penalized.

The canonical defensive source now lives in [`QSOLKCB/HERESY-SEC`](https://github.com/QSOLKCB/HERESY-SEC/tree/main/adversarial/yaml-doctoral-qualifier) and is pinned by assembled identity:

```text
sha256  fa440e63da4cad5943ed1df2a7b7be5c6d4dd69d885a2419ebd9ad6993751125
bytes   50695
lines   1381
```

See [`docs/citizenship_exam/`](docs/citizenship_exam/) for:

- the doctoral curriculum and candidate contract;
- the NEXUS integration/security boundary;
- the deterministic quoted-answer question bank derived from the doctoral corpus;
- the legacy Nightmare Mode material retained as historical lineage.

## What changed

The curriculum now expects candidates to reason across the complete ingestion pipeline rather than memorize isolated parser trivia:

1. **scanner** — tokens, indentation, indicators, escapes;
2. **parser** — events, block/flow context, directives and document boundaries;
3. **composer** — node graphs, anchors, aliases and identity;
4. **resolver** — schema-dependent implicit tag selection;
5. **constructor** — host-language values, hashability, merges and mapping-key collisions;
6. **representer/dumper** — serialization and irreversible round-trip loss.

Candidates must keep specification behavior, concrete parser behavior, loader/schema configuration, and host-language behavior separate. A non-trivial claim is expected to identify the parser, exact version, loader/schema, observed result, and divergence stage.

The question bank includes the Norway problem, SPEC11-versus-PyYAML `y`/`n`, octal drift, sexagesimal values, PyYAML's scientific-notation resolver, nulls, duplicate-key resolution, Python `True == 1` host-key collisions, aliases/identity, recursive graphs, merge behavior, complex keys, multi-document streams, tags, timestamps, schema choice, round-trip degradation, and defensive differential-harness requirements.

## Important runtime boundary

The 50,695-byte doctoral corpus is **not** fed directly to authoritative Citizen Mode.

Citizen Mode continues to accept only the bounded, dependency-free, non-executing YAML subset enforced by the runtime. The full doctoral corpus exists to explain and pressure-test the assumptions that the authoritative boundary deliberately refuses to inherit.

The reference corpus may discuss directives, aliases, anchors, merge keys, explicit tags, complex keys, recursive structures, duplicate resolution, implementation-specific typing, unsafe-loader history, and resource-expansion scenarios. None of those constructs become executable NEXUS world input merely because they appear in the curriculum.

The joke may be cursed. The grader boundary stays boring.

> Passing the curriculum earns in-world citizenship only. It does not establish godhood, intelligence, consciousness, moral worth, extra vote weight, epistemic privilege, authority over another model, or real-world legal/scientific status.
