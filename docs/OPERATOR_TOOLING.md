# Operator Tooling and One-Command Launch

PR #45 turns the local setup ceremony into a first-class NEXUS operator surface.

The golden path is intentionally small:

```bash
git clone https://github.com/QSOLKCB/QSOL-NEXUS.git
cd QSOL-NEXUS
./nexus
```

The repo-root `./nexus` bootstrapper creates a local Python virtual environment when needed, installs the repository as an editable package, then hands control to the standard-library `nexus_runtime.operator_cli` module. With no subcommand, the operator tool prepares the private local state and launches the Rust IRC-style TUI.

The launcher is convenience only. It does not become the source of truth for WorldStore, Council, voting, evidence, Citizenship, Failsafe, Guardian, Trap Base, or constitutional state.

## Commands

```text
./nexus                 launch the Rust TUI
./nexus setup           create safe local state, save the nickname and build the TUI
./nexus doctor          diagnose without opening persistent stores
./nexus doctor --fix    apply safe setup fixes, then run a real health probe
./nexus tui             explicitly launch the TUI
./nexus demo            run one deterministic mock Council smoke test
./nexus paths           show the resolved local runtime/storage paths
./nexus version         show declared package/runtime/TUI versions without opening stores
./nexus update          refresh the editable runtime and rebuild the TUI
./nexus test            run Python and Rust regression suites
./nexus runtime -- ...  pass arguments to the underlying Python NEXUS CLI
```

Examples:

```bash
./nexus setup --nick Trent
./nexus doctor
./nexus demo
./nexus runtime -- auth list
./nexus runtime -- stenographer status
```

## Local layout

PR #45 deliberately preserves the existing local development layout rather than forcing a state migration:

```text
QSOL-NEXUS/
├── nexus                  # one-command bootstrap/launcher
├── .venv/                 # local Python virtualenv (ignored)
├── .nexus/                # owner-only non-secret operator config (ignored)
├── .nexus-world/          # persistent WorldStore (ignored, owner-only)
├── .nexus-trap/           # isolated Trap Base (ignored, owner-only)
├── .nexus-stenographer/   # Courtroom Stenographer store (ignored, owner-only)
└── tui/target/release/nexus
```

The operator config uses the closed schema `nexus-operator-config/1` and currently stores only the bounded operator nickname. Provider credentials remain in the existing authentication subsystem and MUST NOT be copied into `.nexus/operator.json`.

The config path must be a regular file, not a symlink, FIFO, socket, device, or other special file. On POSIX it must remain mode `0600` whenever read.

## Bootstrap behavior

The Bash bootstrapper does only the work required before the Python package can exist:

1. resolve the real launcher/repository location, including invocation through a symlink;
2. require Python 3.11+ (`NEXUS_BOOTSTRAP_PYTHON` may select the bootstrap interpreter);
3. discard caller-controlled `PYTHONPATH` / `PYTHONHOME` and use Python safe-path mode;
4. resolve `NEXUS_VENV` and reject symlinked or overlapping venv paths **before** `venv` or `pip` can write;
5. validate the interpreter in an existing virtualenv against the same Python 3.11+ floor;
6. create the venv only for commands that require it;
7. run an editable install when the package entry point is missing or `pyproject.toml` changed;
8. execute the repository-selected `nexus_runtime.operator_cli` implementation.

Read-only `doctor`, `paths`, `version`, and help can execute directly from repository `src/` without creating a virtualenv.

The larger operator behavior remains in Python so the shell script does not become a second application.

## Safe setup

The operator tool creates the WorldStore, Trap Base, Stenographer, and operator-config directories with owner-only mode `0700` on POSIX systems. Symlinked private roots are refused rather than followed.

`doctor --fix` may:

- create a missing private directory;
- restore a private directory to mode `0700`;
- restore a regular operator config to mode `0600`;
- build a missing or stale Rust TUI release binary;
- start the runtime for a real `system.health` probe after those explicitly permitted setup actions.

It MUST NOT:

- delete or rewrite WorldStore objects;
- repair semantic/index corruption by guessing;
- erase Trap Base or Stenographer history;
- rewrite credentials;
- change Council or constitutional state.

A WorldStore integrity failure belongs to the WorldStore/recovery layer, not the convenience launcher.

## Stale TUI detection

The operator tool compares the release binary timestamp with:

- `tui/Cargo.toml`;
- `tui/Cargo.lock` when present;
- files under `tui/src/`.

If source is newer, `./nexus` rebuilds the TUI before launch. The Cargo invocation pins `--target-dir` to `tui/target`, matching the exact release binary path the launcher subsequently executes even if an operator has a different Cargo target directory configured globally.

If the TUI is missing or stale and Cargo is unavailable, `doctor` reports a readiness **failure**, because the default launch cannot succeed.

The build is not used as an authority signal and does not modify persistent NEXUS state.

## Doctor contract

`./nexus doctor` reports at least:

- bootstrap Python version;
- local virtualenv presence and interpreter compatibility;
- installed runtime CLI presence;
- venv/storage/config disjointness;
- WorldStore privacy;
- Trap Base privacy;
- Stenographer privacy;
- operator-config directory/file type and privacy;
- Rust TUI presence/staleness and whether Cargo can produce a required build.

Plain Doctor is observational. It does **not** instantiate `NexusAPI` or open/create WorldStore, Stenographer, Trap Base, Guardian, or civic runtime storage merely to obtain health information. When an installed runtime is present it reports that live runtime health was intentionally not started.

`doctor --fix` is an explicitly mutating setup path. After its permitted setup operations, it may run the real `system.health` probe.

## Version contract

`./nexus version` is also observational. It reads declared release identity from repository metadata (`README4AI.md`, `pyproject.toml`, and the TUI manifest) and does not start the NEXUS runtime or open persistent stores.

## Advanced CLI passthrough

The operator wrapper does not hide or replace the underlying control CLI. Use:

```bash
./nexus runtime -- <arguments>
```

The wrapper supplies the standard local WorldStore, Trap Base, and Stenographer roots, then forwards the remaining arguments to the installed Python `nexus` entry point.

This keeps one-command convenience separate from the protocol/runtime implementation.

## Invariants

```text
TOOL-I1  Default launch requires no manually supplied storage paths.
TOOL-I2  First launch may create required local resources but must not overwrite existing state.
TOOL-I3  Automatic repair must not perform destructive WorldStore operations.
TOOL-I4  Operator configuration must not contain provider credentials.
TOOL-I5  Storage privacy requirements remain identical to direct runtime use.
TOOL-I6  Resolved local paths are inspectable through `./nexus paths`.
TOOL-I7  Advanced users retain the underlying Python CLI.
TOOL-I8  Launcher convenience cannot alter votes, evidence, Citizenship, Failsafe, Guardian or constitutional semantics.
TOOL-I9  Doctor and version are observational unless explicit `doctor --fix` is supplied.
TOOL-I10 Failed bootstrap/setup must leave existing persistent state untouched.
TOOL-I11 Virtualenv topology is rejected before environment/package writes can enter persistent state.
TOOL-I12 Caller working-directory/import state cannot select a different operator implementation.
```

## Release sequencing

PR #45 is a pre-beta usability milestone. PR #46 follows with **WorldStore Continuity / The Ark Protocol**. The formal 2.0 hardening/release pass begins only after both are merged, so the stable candidate is hardened around the operator and persistence surfaces that users will actually run.
