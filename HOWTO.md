# QSOL NEXUS — Easy Use Guide

The repository itself is the NEXUS launcher. The current PR #61 release candidate identifies runtime, Python package and Rust TUI as `2.1.1` with protocol `nexus/0.15`. It includes the post-stable PR #55–#60 extension line while preserving the published `v2.0.0` identity and the premature historical `v2.1.0` tag unchanged.

## Release-candidate note

PR #61 is a **2.1.1 release candidate**, not release authority. Use `./nexus version` and `./nexus doctor` to verify the local checkout. Only the exact reviewed-and-green merged PR #61 commit may later receive a new `v2.1.1` tag and GitHub Release. The old `v2.0.0` release remains frozen historical provenance, and `v2.1.0` must not be moved.

Historical 2.0 release instructions and evidence remain valid only for the frozen `v2.0.0` commit; they are not instructions for tagging the current checkout.

## First launch

```bash
git clone https://github.com/QSOLKCB/QSOL-NEXUS.git
cd QSOL-NEXUS
./nexus
```

On a normal supported development machine, `./nexus` will:

1. create the local `.venv` if it does not exist;
2. install the NEXUS Python runtime into that environment as an editable package;
3. create the private local WorldStore, Trap Base and Stenographer roots;
4. restore owner-only permissions where safe;
5. build the Rust IRC-style TUI when its release binary is missing or stale;
6. set the correct local Python runtime for the TUI;
7. launch NEXUS using your saved operator nickname.

The first launch may therefore need a Python 3.11+ installation and a Rust/Cargo toolchain. Cargo may also need access to its dependency cache or the network the first time the TUI is built.

## Set your nickname

```bash
./nexus setup --nick Trent
```

The nickname is stored in `.nexus/operator.json`. That file is intentionally a tiny non-secret closed-schema config. Provider credentials remain in the NEXUS auth subsystem.

## If something looks wrong

```bash
./nexus doctor
```

For safe setup repairs only:

```bash
./nexus doctor --fix
```

`doctor --fix` may create missing local directories, correct owner-only directory permissions, and build a missing/stale TUI. It will not delete, reconstruct, or guess at damaged WorldStore history.

## Useful commands

```bash
./nexus                 # launch the TUI
./nexus tui             # explicit TUI launch
./nexus demo            # deterministic mock Council smoke test
./nexus paths           # show local paths
./nexus version         # show component versions
./nexus update          # refresh editable runtime + rebuild TUI
./nexus test            # Python + Rust tests
./nexus runtime -- ...  # underlying Python CLI
```

Examples:

```bash
./nexus runtime -- auth list
./nexus runtime -- auth test
./nexus runtime -- models list xai
./nexus runtime -- stenographer status
```

## What the launcher uses

```text
QSOL-NEXUS/
├── .venv/               local Python environment
├── .nexus/              non-secret operator config
├── .nexus-world/        persistent WorldStore
├── .nexus-trap/         isolated Trap Base
├── .nexus-stenographer/ Courtroom Stenographer ledger
└── tui/target/release/nexus
```

All persistent/private local state directories are kept separate. On POSIX systems, NEXUS expects the private directories to be owner-only (`0700`).

## Inside the TUI

The Rust shell is IRC-like but communicates with the Python NEXUS runtime over local JSONL/stdio; it is not an IRC server and does not require a daemon.

A few useful commands:

```text
/help
/join #observatory
/join #commons
/join #anarchy
/ask Does this claim need more evidence?
/addollama LocalQwen qwen2.5:0.5b
/join #stenographer
/steno status
/join #wall
/wall 20
/wall post Hello from the Commons.
/wall mine
/save transcript.txt
/quit
```

Rooms change framing, not vote weight. Ordinary Council seats remain equal.

## Manual fallback

The underlying Python and Rust tools remain ordinary project components. If you are debugging the launcher itself, the equivalent pieces are still available:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
mkdir -p .nexus-world .nexus-trap .nexus-stenographer
chmod 700 .nexus-world .nexus-trap .nexus-stenographer
cargo build --manifest-path tui/Cargo.toml --release
export NEXUS_PYTHON="$PWD/.venv/bin/python"
```

Then the TUI can be started directly with its explicit storage flags.

For the operator-tooling contract and safety invariants, see [`docs/OPERATOR_TOOLING.md`](docs/OPERATOR_TOOLING.md).


## Persistent world and Ark recovery

The default launcher uses `.nexus-world/` as the persistent WorldStore. WorldStore Continuity recognizes replicated canonical history by quorum. Ark creation/verification/restore is exposed through the runtime's `world.ark.*` / `world.recovery.*` operations; restore is deliberately non-destructive and targets a new empty location.

Do not hand-edit replica objects, HEAD/manifest state, progression indexes, or Wall chronology. If continuity health is degraded, use the documented inspect/scrub/recovery operations in [`docs/ARK_PROTOCOL.md`](docs/ARK_PROTOCOL.md); `doctor --fix` intentionally does not rewrite world history.

## The Wall

`#wall` is an old-school public noticeboard:

```text
/join #wall
Hello from the Commons.
/wall
/wall 20
/wall mine
/wall since 24h
/wall oldest
```

Plain text in `#wall` becomes social memory, **not** a Council question. `/ask` is blocked there so the operator must deliberately return to a Council-capable room before starting deliberation. Tombstones are append-only moderation history rather than silent deletion.
