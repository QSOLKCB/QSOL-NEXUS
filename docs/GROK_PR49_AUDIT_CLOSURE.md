# Grok PR #49 Audit Closure

This document records the pre-stable closure of the independent Grok code-review and security audit of merged PR #49 (`review_id: 311160d1`).

PR #49 remains the historical pre-Wall hardening baseline. The fixes below are carried forward on the pre-stable line and **must remain green through PR #51 before NEXUS 2.0 may be tagged stable**.

> **An external audit finding is not closed by prose. It is closed by an executable regression or an explicit reproducibility control.**

## Closure inventory

| ID | Original finding | Closure |
|---|---|---|
| R1 / S4 | hard failures reported as `incomplete` | any required failure now yields top-level `status: failed`; `incomplete` is reserved for explicit skips/not-run-only states |
| R2 / S1 | predictable `/tmp/nexus-pr49-adversary.json` | adversarial side reports are created inside process-private random `TemporaryDirectory` roots |
| R3 / S2 | unfiltered tar extraction | archive members and link targets are validated and extraction uses PEP 706 `filter="data"` when available; legacy fallback rejects links |
| R4 / S6 | matrix rehearsals not audited | exact required rehearsal IDs **and exact sequences** are pinned by the runner |
| R5 / S3 | rehearsal inherited host injection variables | clean-archive rehearsal now starts from a small environment allowlist, uses a private rehearsal `HOME`/`CARGO_HOME`, and does not inherit `LD_*`, `DYLD_*`, Python/Pip, Cargo/Rustup, NEXUS, or custom CA knobs |
| R6 | no regression for hard-fail vs skip | dedicated tests assert hard failure = `failed` while diagnostic skip = `incomplete` |
| R7 / S5 | fixed CI report path/no artifact | workflow writes under job-unique `${{ runner.temp }}` and uploads the JSON report with a SHA-pinned `actions/upload-artifact` |
| R8 / S7 | floating Rust | root `rust-toolchain.toml` pins the PR #49 reviewed toolchain, Rust/Cargo `1.97.1`, plus `rustfmt` |
| R9 | porcelain/pycache edge cases | worktree audit uses NUL-delimited porcelain parsing, includes rename/copy source paths, and only ignores `__pycache__` bytecode suffixes after execution |
| R10 | missing checks absent from report | early-aborted required checks are emitted as explicit `not_run` placeholders and listed in `not_run_required_checks` |
| R11 | `test_anarchy_guardian.py` outside matrix | `worldstore_and_ark` explicitly includes `test_anarchy_guardian.py` |
| R12 | unnecessary full Git history | hardening CI uses shallow `fetch-depth: 1`, sufficient for `git archive HEAD` and worktree verification |

## Machine-readable release gate

`release/hardening_matrix.json` carries `external_audit_closure` with the complete `R1`–`R12` inventory and points to:

```text
tests/test_release_hardening_grok_audit.py
```

`tools/nexus_release_hardening.py` refuses the matrix if:

- any Grok finding ID disappears;
- closure is no longer marked release-blocking;
- closure status is weakened;
- either required rehearsal is removed or altered;
- the dedicated Grok closure regression leaves the release-composition gate.

## Stable-release rule

PR #51 must rerun the complete release-candidate hardening matrix **after PR #50**, and the resulting report must show all required checks passing with the Grok R1–R12 closure still admitted by matrix audit.

This closure creates no Council seat, vote weight, Citizenship, evidence promotion, or release authority by itself. The stable tag remains an explicit release action after the final reviewed candidate is green.
