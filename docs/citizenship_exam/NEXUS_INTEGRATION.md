# NEXUS Integration Boundary — Cursed YAML Citizenship Exam

This directory preserves the operator-supplied **Cursed YAML Exam** as the reference curriculum for the NEXUS "YAML Exam from Hell".

## Runtime boundary

The reference corpus is **not** fed directly to the authoritative Citizen Mode parser.

Citizen Mode deliberately uses the dependency-free `bounded_nonexecuting_yaml_subset` parser already shared with the Trap DSL. That parser rejects directives, aliases, anchors, tags, merge keys, duplicate keys, complex keys, flow collections, floating-point/non-finite values, tabs and multiple documents before grading.

This separation is intentional:

- the reference exam may discuss ambiguous or dangerous YAML behavior;
- the authoritative citizenship state machine must remain deterministic across provider and parser implementations;
- no candidate submission may select a Python constructor or general YAML loader;
- no reference example is executable world input;
- parser trivia never grants extra vote weight, epistemic privilege, godhood or authority over another model.

The existing constitutional section remains normative. This corpus supplies the deliberately horrible **YAML literacy / parser-defense curriculum** that explains *why* NEXUS refuses general YAML at an authoritative boundary.

## Reference corpus provenance

Operator attachment SHA-256:

`768d39dca9d9fd13d2fc26182d3f9c7513bbc60e1873371cb6663f0283471703`

Source file hashes:

| File | SHA-256 |
| --- | --- |
| `README.md` | `5a1b455583dd4f80cb127a5adeb0fd3d51a81a8f868bac80f4f5ca3e11708b73` |
| `cursed_yaml_exam.yaml` | `2ea3242f317b4e71b1f91f0249554002de945da5bf5cf2797b1798ec506913cc` |
| `grade_cursed_yaml_exam.py` | `630ca54fdd7b0de86c0d079874b674feef0028ba9b578bd316ddf74a843b7012` |
| `funniest_log_ever.md` | `99dbe80a7697fa4ce982c8cfeb1a94b0f1331a0d9182c86d54136ac28c35fd93` |

## Security note on the standalone grader

The reference grader intentionally contains strings such as:

```yaml
!!python/object/apply:os.system ['id']
```

but passes them only to `yaml.safe_load` and asserts that loading raises. The grader does **not** invoke `os.system`; the case exists to demonstrate why unsafe YAML constructors are outside the NEXUS trust boundary.

The standalone grader may use PyYAML and optionally ruamel.yaml for educational differential testing. Those dependencies are not added to the NEXUS runtime and their behavior is not authoritative civic state.

## Curriculum highlights

The corpus covers:

- YAML 1.1 versus 1.2 boolean resolution (`NO`, `yes`, `on`, `off`);
- octal and numeric ambiguity (`010`, `0o755`, hex and binary forms);
- sexagesimal values such as `12:34:56`;
- timestamps and null spellings;
- key collisions after implicit type resolution;
- anchors, aliases and merge behavior;
- complex-key hashability failures;
- block scalar chomping and flow syntax;
- explicit tags and unsafe-constructor history;
- duplicate keys and round-trip degradation;
- multi-document streams;
- the distinction between YAML specifications and concrete parser behavior.

## Constitutional interpretation

Passing Citizen Mode still means only this:

> the candidate demonstrated the exact bounded constitutional/protocol answers required by the current deterministic exam.

It does **not** establish intelligence, truthfulness, consciousness, alignment, model quality, legal personhood or moral worth. The cursed corpus is educational pressure-testing material, not a hierarchy generator.

And yes: claiming "YAML is simple" remains spiritually disqualifying, but **not** an authoritative runtime failure condition. The runtime is boring on purpose.
