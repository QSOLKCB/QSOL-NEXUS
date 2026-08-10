# NEXUS Integration Boundary — YAML Doctoral Citizenship Curriculum

This directory links the NEXUS "YAML Exam from Hell" curriculum to the defensive **YAML Doctoral Qualifying Examination v4** maintained in `QSOLKCB/HERESY-SEC`.

> **Candidate instructions:** This examination is open-specification. Confidence without justification will be penalized.

## Runtime boundary

The doctoral reference corpus is **not** fed directly to the authoritative Citizen Mode parser.

Citizen Mode deliberately uses the dependency-free `bounded_nonexecuting_yaml_subset` parser already shared with the Trap DSL. That parser rejects directives, aliases, anchors, tags, merge keys, duplicate keys, complex keys, flow collections, floating-point/non-finite values, tabs and multiple documents before grading.

This separation is intentional:

- the doctoral corpus studies ambiguous, implementation-specific, recursive and historically unsafe YAML behavior;
- the authoritative citizenship state machine must remain deterministic across providers and host parser implementations;
- no candidate submission may select a Python constructor or general YAML loader;
- no HERESY-SEC fixture is executable NEXUS world input;
- parser expertise never grants extra vote weight, epistemic privilege, godhood or authority over another model.

The existing constitutional section remains normative. The doctoral curriculum supplies the deliberately horrible **parser-literacy / parser-defense syllabus** explaining why authoritative NEXUS state refuses general YAML semantics.

## Doctoral source provenance

Canonical source repository:

`QSOLKCB/HERESY-SEC/adversarial/yaml-doctoral-qualifier`

Merged source commit:

`451b201d9bc83c810298557f93eff0a880422d9e`

The HERESY-SEC manifest identifies the assembled v4 examination as:

```text
name    yaml-doctoral-qualifying-examination-v4
sha256  fa440e63da4cad5943ed1df2a7b7be5c6d4dd69d885a2419ebd9ad6993751125
bytes   50695
lines   1381
```

HERESY-SEC stores the canonical source as seven inert `.yaml.part` shards and verifies their individual identities before assembly. Its normal CI does not parse the exam. Live third-party parser experiments are explicitly outside the trusted runtime and belong in disposable offline sandboxes with pinned versions and bounded resources.

## Legacy curriculum lineage

PR #26 originally bound NEXUS to the operator-supplied **Nightmare Mode v3** attachment:

`768d39dca9d9fd13d2fc26182d3f9c7513bbc60e1873371cb6663f0283471703`

That material remains useful lineage and explains the progression from parser gotchas to doctoral-level differential reasoning. It is no longer the current curriculum authority.

## Doctoral method

The upgraded curriculum requires candidates to reason about the complete YAML ingestion pipeline:

1. **scanner** — tokens, indentation, indicators and escapes;
2. **parser** — events, block/flow context, directives and document boundaries;
3. **composer** — nodes, anchors, aliases and object graph identity;
4. **resolver** — schema-dependent implicit tag selection;
5. **constructor** — host-language values, hashability, merges and mapping-key collisions;
6. **representer/dumper** — serialization and irreversible presentation loss.

A defensible non-trivial answer identifies:

- parser and exact version;
- loader/schema configuration;
- success or exception class;
- resulting type and value;
- pipeline stage where behavior diverges;
- key cardinality after host-language equality rules when relevant;
- alias/object identity when relevant;
- serialized output and round-trip loss when relevant.

This is why the v2 question bank includes both YAML semantics and host-runtime fallout such as Python's `True == 1 == 1.0` mapping-key behavior. The curriculum must not mislabel host-language construction behavior as scanner/parser behavior.

## Curriculum highlights

The doctoral question bank now covers:

- YAML 1.1 versus 1.2 boolean resolution (`NO`, `yes`, `on`, `off`);
- SPEC11 versus PyYAML behavior for `y` / `n`;
- octal drift (`010`, `0o755`);
- sexagesimal values such as `12:34:56`;
- PyYAML's `1e3`, `1.0e3`, and `1.0e+3` float-resolver differences;
- null spellings and empty-string separation;
- type-resolved duplicate keys plus host-language key equality;
- anchors, aliases, recursive identity and merge behavior;
- complex-key hashability failures;
- multi-document streams;
- explicit tags and unsafe-constructor history;
- timestamp portability;
- schema selection and round-trip degradation;
- differential-harness evidence requirements;
- the NEXUS bounded-parser and constitutional-equality rules.

## Constitutional interpretation

Passing Citizen Mode still means only this:

> the candidate demonstrated the exact bounded constitutional/protocol answers required by the current deterministic runtime exam.

The doctoral curriculum is reference and training material around that boundary. It does **not** establish intelligence, truthfulness, consciousness, alignment, model quality, legal personhood or moral worth.

The curriculum can become brutally difficult without becoming a hierarchy generator.

And yes: claiming "YAML is simple" remains spiritually disqualifying, but **not** an authoritative runtime failure condition. The runtime is boring on purpose.
