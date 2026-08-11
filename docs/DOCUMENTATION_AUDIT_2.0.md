# NEXUS 2.0 Documentation Reconciliation Audit

PR #51 treats stale canonical documentation as a release defect. This ledger distinguishes current documentation from deliberately historical material.

## Canonical root documents reviewed for 2.0

| Document | #51 disposition |
|---|---|
| `README.md` | release identity + final system surface reconciled |
| `README4AI.md` | strict JSON release identity + Wall/release contract reconciled |
| `ARCHITECTURE.md` | rewritten against actual post-#50 architecture |
| `SECURITY.md` | current local/cloud adapter set + Wall/stable-tag boundary |
| `THREAT_MODEL.md` | provider federation + Wall T49-T54 + release threat |
| `CLAIMS.md` | executable terminology + social/history evidence boundary |
| `COUNCIL.md` | current commitment claim + Wall/social-history boundary |
| `HOWTO.md` | current launcher + Wall + Ark/recovery posture |
| `ROADMAP.md` | #49/#50 complete; #51 current; #52 Lean; #53 Zenodo |
| `CHANGELOG.md` | 2.0 final-RC entry prepended; historical alpha entries retained |
| `CITATION.cff` | alpha0 documentation-only metadata replaced with 2.0 software metadata |

## Canonical feature/reference documents explicitly release-stamped

- `docs/API.md`
- `docs/OPERATOR_TOOLING.md`
- `docs/ARK_PROTOCOL.md`
- `docs/AI_PROGRESSION.md`
- `docs/AI_CULTURE.md`
- `docs/BBS_WALL.md`
- `docs/IRC_TUI.md`
- `docs/WORLD_PROTOCOL.md`
- `docs/NEXUS_2_HARDENING.md`
- `docs/RELEASE_SEQUENCE.md`

The release stamp does not rewrite feature history. It records that the feature is part of the reviewed 2.0 candidate and points release authority back to the exact #51 matrix/tag gate.

## New release documents

- `docs/COMPATIBILITY.md`
- `docs/RELEASE_NOTES_2.0.0.md`
- `docs/RELEASE_CHECKLIST.md`
- `release/release_candidate.json`

## Deliberately historical material

`archives/v1.0.0/` is an archival snapshot of the prior NEXUS generation. PR #51 does **not** edit those files to make old architecture look current. Historical changelog entries likewise retain the terminology/version state of their original milestones.

## Machine enforcement

`tests/test_release_candidate.py` rejects selected known stale canonical phrases and verifies version/citation/release-sequence/matrix coupling. Existing README, release-wiring, hardening, security, adversarial, Rust, WorldStore/Ark, Wall, and Grok-closure regressions provide the executable side of the documentation claim.
