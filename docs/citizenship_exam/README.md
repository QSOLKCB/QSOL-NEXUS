# The Cursed YAML Exam

A progressive YAML 1.1 / 1.2 torture suite for anyone who has ever typed `safe_load` and prayed.

**Instant fail condition:** claiming that YAML is simple.

---

## Contents

| File | What it is |
|------|------------|
| `funniest_log_ever.md` | **Warm-up.** Original “YAML 1.1 vs 1.2 ambiguity” document (booleans-from-hell, octal `010`, sexagesimal clocks, null cult). |
| `cursed_yaml_exam.yaml` | **Nightmare Mode (v3).** Full exam: Norway industrial complex, numerology, anchors/merges, complex keys, tags, multi-doc streams, schema trinity, final boss, oral-defense chapters. |
| `grade_cursed_yaml_exam.py` | **Automated grader / answer key.** Loads the exam under PyYAML (and optionally ruamel.yaml), runs 200+ checks, prints differentials, round-trip samples, and a rank title. |
| `README.md` | This file. |

---

## Quick start

### Requirements

- Python 3.9+ (tested on 3.12 / 3.14)
- [PyYAML](https://pypi.org/project/PyYAML/) (required)
- [ruamel.yaml](https://pypi.org/project/ruamel.yaml/) (optional, for YAML 1.2 differentials)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pyyaml ruamel.yaml
```

### Take the exam

1. Open `cursed_yaml_exam.yaml`.
2. For each chapter, write type **and** value under:
   - **P11** — PyYAML `yaml.safe_load` / `safe_load_all` (YAML 1.1-ish)
   - **R12** — ruamel.yaml / Go `yaml.v3` (YAML 1.2 core-ish)
3. Predict exceptions, key counts after collisions, and round-trip loss.
4. Do **not** peek at the grading key comments at the bottom until you have answers.

### Grade yourself (automated)

```bash
python grade_cursed_yaml_exam.py
python grade_cursed_yaml_exam.py -v                 # every check
python grade_cursed_yaml_exam.py --json report.json # machine-readable
python grade_cursed_yaml_exam.py --no-ruamel        # PyYAML only
python grade_cursed_yaml_exam.py --exam path/to/cursed_yaml_exam.yaml
```

Exit codes:

| Code | Meaning |
|------|---------|
| `0` | All automated checks passed |
| `1` | One or more checks failed (exam drift or parser change) |
| `2` | Hard failure (missing exam file or PyYAML) |

Manual / oral chapters (**Ch17 prose, Ch18 defense, Ch19 weapons**) are **not** auto-scored.

---

## Exam map (Nightmare Mode)

| Chapter | Topic |
|---------|--------|
| 0 | Directives that lie (`%YAML`, `%TAG`) |
| 1 | Norway problem (booleans as country codes / keys) |
| 2 | Numerology (octal, hex, binary, sexagesimal, floats) |
| 3 | Timestamps |
| 4 | Null cult (`null` / `Null` / `NULL` / `~` / empty) |
| 5 | Anchors, aliases, merge keys, identity graph |
| 6 | Complex keys (hashability is a social construct) |
| 7 | Block scalars & chomping (`|` `|+` `|-` `>` …) |
| 8 | Flow style |
| 9 | Explicit tags (`!!str` `!!bool` `!!binary` …) |
| 10 | Duplicate keys & merge-induced duplicates |
| 11 | Round-trip degradation |
| 12 | Strings that look like syntax |
| 13 | Whitespace, encoding, homoglyphs |
| 14 | Schema trinity (Failsafe / JSON / Core / 1.1) |
| 15 | Final boss |
| 16 | Multi-document streams |
| 17 | **Spec vs implementation** (PyYAML ≠ full 1.1) |
| 18 | Oral defense |
| 19 | Write your own weapon |

---

## Landmines you will step on

These are **implementation facts** under common tools (especially **PyYAML 6.x**), not always pure spec:

1. **`yes` / `no` / `on` / `off` / `NO`** → booleans in YAML 1.1; mostly strings in YAML 1.2 core (except `true`/`false`).
2. **`y` / `n`** are booleans in the YAML 1.1 **spec**, but **strings** in PyYAML’s resolver.
3. **`010`** → octal `8` in 1.1; decimal `10` in 1.2. Value change, not just type.
4. **`0o755`** → string in PyYAML 1.1; octal int in 1.2.
5. **`12:34:56`** → sexagesimal int `45296` in 1.1; string in 1.2.
6. **`1e3`** stays a **string** in PyYAML; use `1.0e+3` if you want a float.
7. **Keys collide** when resolved types match (`yes`/`true`/`on` → one `True` key). Last write wins in PyYAML; modern 1.2 libs may error.
8. **Sequence/map keys** are unhashable under stock PyYAML (`ConstructorError`) — they do **not** auto-become tuples.
9. **`safe_load`** on a multi-doc file → `ComposerError`; use **`safe_load_all`**.
10. **`yaml.load`** without a safe loader is how `!!python/object/apply` becomes RCE. Never do that.

---

## Rank titles (from the exam)

| Scaled score | Title |
|--------------|--------|
| 0–40 | Config Tourist |
| 41–80 | YAML Apprentice (has been paged once) |
| 81–120 | Norway Veteran |
| 121–160 | Schema Ascetic |
| 161–200 | Spec Lawyer (knows PyYAML ≠ 1.1) |
| 201+ | Eldritch Clerk — you may maintain the company's Helm charts |

---

## Defensive rules (if you must ship YAML)

1. **Quote** anything that is not a plain decimal integer or a deliberate boolean `true`/`false`.
2. Pin a **schema** (and a library version) on both producer and consumer.
3. Prefer **YAML 1.2** parsers when talking across languages.
4. Never use bare `yaml.load` / unsafe loaders on untrusted input.
5. Round-trip test: load → dump → load again; diff types and values.
6. Country codes, feature flags (`on`/`off`), and permissions (`0755`) are especially cursed — quote them.

---

## License / vibe

Public domain dedication for the exam text and grader, or treat as CC0.  
No warranty. If this ruins your afternoon, you are welcome.

*YAML is an Eldritch nightmare disguised as human-readable syntax.*
