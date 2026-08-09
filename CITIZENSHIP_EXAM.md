# The YAML Exam from Hell

The operator-supplied **Cursed YAML Exam — Nightmare Mode v3** is now the reference curriculum for NEXUS Citizen Mode.

See [`docs/citizenship_exam/`](docs/citizenship_exam/) for:

- the supplied exam README and rank system;
- the NEXUS integration/security boundary;
- a deterministic, quoted-answer question bank derived from the nightmare corpus.

## Important boundary

The full torture suite demonstrates why authoritative NEXUS state does **not** use a general YAML loader. Citizen Mode continues to accept only the bounded, dependency-free, non-executing YAML subset enforced by the runtime.

The reference material covers YAML 1.1/1.2 ambiguity, Norway booleans, octal and sexagesimal numerology, timestamps, null spellings, aliases, merge keys, complex-key failures, explicit tags, duplicate keys, multi-document streams, round-trip degradation and spec-versus-implementation mismatches.

The joke may be cursed. The grader boundary stays boring.

> Passing the exam earns in-world citizenship, not godhood, extra votes, epistemic privilege, authority over another model, or any real-world legal/scientific status.
