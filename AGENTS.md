# QSOL NEXUS agent contract

This repository has two intentionally different documentation surfaces:

- `README.md` is the human/operator README.
- `README4AI.md` is the AI/agent manifest and MUST remain strict machine-readable JSON despite the `.md` filename.

## Mandatory README synchronization rule

If a change modifies `README.md`, the same pull request MUST also modify `README4AI.md`.

This is enforced through the reusable local composite action `.github/actions/readme-contract/action.yml`, which invokes `tools/validate_readme_contract.py`. Workflows must reuse that action rather than duplicating base/head SHA derivation or validator command logic.

Do not bypass the rule by copying human prose wholesale into `README4AI.md`. Translate the changed architectural facts, release state, invariants, operations, or boundaries into the structured JSON fields that an AI can consume deterministically.

## Before modifying NEXUS

1. Parse `README4AI.md` as strict JSON.
2. Respect its `normative_precedence`, `authority_invariants`, `security_boundaries`, and `modification_contract` fields.
3. Use executable runtime behavior and tests as higher authority than roadmap prose.
4. Do not invent execution, verification, credentials, provider success, replayability, or authority not established by code/tests/runtime evidence.
5. Run `python3 tools/validate_readme_contract.py` for documentation changes.

## Validator modes

The default remains the complete human/machine contract:

```text
python3 tools/validate_readme_contract.py --mode contract
```

Focused tooling may deliberately select a narrower concern:

```text
--mode manifest         strict README4AI JSON/schema/shape validation only
--mode human-coupling   machine manifest plus labeled README release/link coupling
--mode sync             README.md/README4AI.md paired-change audit; requires a commit range
```

CI passes `--github-event "$GITHUB_EVENT_PATH"` through the composite action so PR and push base/head SHAs are derived in one implementation rather than repeated across workflows.

## Machine-manifest preservation

`README4AI.md` must remain:

- UTF-8 strict JSON;
- one top-level JSON object;
- free of duplicate keys;
- free of NaN/Infinity or any numeric literal that decodes non-finitely;
- structurally typed for required arrays and objects;
- targeted primarily at AI/agent consumption rather than human presentation;
- synchronized with the labeled current-release fields in `README.md`.
