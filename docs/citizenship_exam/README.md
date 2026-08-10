# NEXUS YAML Doctoral Citizenship Curriculum

A defensive YAML semantics and parser-differential curriculum for anyone who has ever typed `safe_load` and prayed.

**Candidate instruction:** *This examination is open-specification. Confidence without justification will be penalized.*

**Spiritual instant fail condition:** claiming that YAML is simple. The authoritative runtime does not grade the joke.

---

## Current source

The current curriculum is derived from the **YAML Doctoral Qualifying Examination v4 — Formal Semantics, Parser Differential Behaviour, Canonicalization, and Adversarial Edge Cases** in `QSOLKCB/HERESY-SEC`.

Canonical assembled identity:

```text
sha256  fa440e63da4cad5943ed1df2a7b7be5c6d4dd69d885a2419ebd9ad6993751125
bytes   50695
lines   1381
```

The source corpus is stored there as seven inert `.yaml.part` shards, not as auto-discoverable production configuration. HERESY-SEC verifies byte identity and containment without parsing it during normal CI.

The original **Nightmare Mode v3** curriculum from NEXUS PR #26 remains historical lineage. The v4 doctoral curriculum supersedes it for reference/training purposes.

---

## Files in this directory

| File | Role |
| --- | --- |
| `README.md` | Current doctoral syllabus and candidate orientation. |
| `NEXUS_INTEGRATION.md` | Security, provenance, runtime and constitutional boundary. |
| `NEXUS_QUESTION_BANK.yaml` | Deterministic quoted-answer v2 curriculum derived from the doctoral corpus. |

---

## What makes the v4 curriculum doctoral

Nightmare Mode asked whether you knew that YAML parsers disagree.

The doctoral curriculum asks **why**, **where in the pipeline**, **under exactly which parser/loader/schema**, and **what the host language does after YAML resolution**.

The working pipeline is:

| Stage | What the candidate must reason about |
| --- | --- |
| Scanner | tokens, indentation, indicators, escapes |
| Parser | events, block/flow context, directives, document boundaries |
| Composer | nodes, anchors, aliases, graph identity |
| Resolver | implicit tags and schema-dependent scalar typing |
| Constructor | host-language values, hashability, merges, mapping collisions |
| Representer / dumper | serialization, presentation loss and round-trip drift |

For a non-trivial parser claim, a strong answer identifies the **parser, exact version, loader/schema, observed result, and stage**. For mapping or alias cases it may also need host-language key cardinality or object identity.

---

## Core landmines

The v2 NEXUS question bank retains the classic traps and adds the doctoral interpretation layer:

1. **`NO`** — boolean false under PyYAML 6.x / 1.1-style resolution, ordinary string under YAML 1.2 core.
2. **`y` / `n`** — booleans in the YAML 1.1 specification ideal, but strings in PyYAML's resolver.
3. **`010`** — octal `8` in the 1.1-style path, decimal `10` in YAML 1.2 core.
4. **`0o755`** — string under PyYAML 6.x; octal `493` under 1.2 core.
5. **`12:34:56`** — sexagesimal integer `45296` under PyYAML's 1.1-style resolver; string under 1.2 core.
6. **`1e3`** — string under PyYAML 6.x; `1.0e3` is also a string there, while `1.0e+3` resolves as a float.
7. **Resolved keys can collide** — `yes`, `true`, and `on` may resolve to equal boolean keys before the host mapping is constructed.
8. **Python adds another collision layer** — `True == 1 == 1.0` and `False == 0` are host-runtime facts, not YAML scanner/parser rules.
9. **Complex keys** — sequence/mapping keys can fail construction under stock PyYAML because the resulting Python objects are unhashable.
10. **Aliases can preserve identity** and can participate in recursive graphs; the composer/constructor distinction matters.
11. **`safe_load` on a multi-document stream** is not `safe_load_all`.
12. **Language-specific Python tags** are outside the NEXUS trust boundary.
13. **Round trips are evidence** — load/dump/load may change type, value, identity or presentation depending on schema and implementation.

---

## Defensive rules

If YAML must cross a real boundary:

1. Quote ambiguous strings such as country codes, feature flags and permission-looking values.
2. Pin parser **and exact version**, loader/schema configuration, and producer/consumer expectations.
3. Detect or reject duplicate mapping keys explicitly.
4. Treat host-language key equality as a separate construction hazard.
5. Never use unsafe general loaders on untrusted input.
6. Differential-test parser upgrades using fixed bytes and record type/value/exception/stage evidence.
7. Round-trip test data that must survive serialization.
8. Keep hostile parser corpora outside production configuration paths.

---

## NEXUS boundary

The doctoral material is **reference and training data**, not authoritative world input.

Citizen Mode's actual state transition remains deliberately boring: candidates submit only the closed, bounded, dependency-free, non-executing YAML subset accepted by NEXUS. Directives, aliases, anchors, tags, merge keys, duplicate/complex keys, flow collections, floats, tabs and multi-document streams remain outside that authoritative parser.

Passing citizenship therefore proves only that the candidate supplied the exact bounded answers required by the runtime. It does not establish intelligence, consciousness, moral worth, provider superiority, legal personhood, godhood, extra vote weight or epistemic privilege.

**The curriculum may be PhD-level. The Constitution still says one citizen, one equal seat.**

---

## Rank titles

| Scaled score | Title |
| --- | --- |
| 0–39 | Config Tourist |
| 40–79 | Graduate Applicant |
| 80–119 | Norway Veteran |
| 120–159 | Schema Ascetic |
| 160–199 | Spec Lawyer |
| 200–239 | Doctoral Candidate |
| 240+ | Eldritch Doctor — may maintain the Helm charts under supervision |

*YAML remains an Eldritch nightmare disguised as human-readable syntax.*
