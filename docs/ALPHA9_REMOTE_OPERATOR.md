# Alpha9 Remote Operator Surface

QSOL-NEXUS alpha9 completes the engineering side of authentication and remote-provider setup without moving credentials into the semantic runtime.

The provider-neutral authentication broker and the first fixed-destination xAI transport already existed before this milestone. Alpha9 adds the missing operator surfaces and a reproducible way to archive a real live acceptance run.

## Architecture

```text
existing auth broker / secret store
           |
           | profile name only
           v
nexus-remote-setup  (Rust operator TUI)
           |
           +-- auth adapters/list/test
           +-- live xAI model discovery
           +-- ephemeral mixed roster setup
           +-- Council run over JSONL runtime
           |
           v
existing NEXUS runtime / Council

raw credential bytes never cross this seam
```

The existing secure enrollment path remains:

```text
python3 -m nexus_runtime auth add ...
```

The Rust operator surface intentionally does not implement an API-key text box.

## Rust remote operator TUI

The new binary lives at:

```text
tui/src/bin/nexus-remote-setup.rs
```

Run it from the repository root with:

```bash
cargo run --manifest-path tui/Cargo.toml --bin nexus-remote-setup
```

Optional operational roots can be supplied through non-secret environment variables:

```text
NEXUS_AUTH_ROOT
NEXUS_WORLD
NEXUS_TRAP_ROOT
NEXUS_STENOGRAPHER_ROOT
NEXUS_PYTHON
NEXUS_PYTHONPATH
```

### Commands

```text
help
auth adapters
auth list
auth test xai [profile]
auth add
models xai [profile]
add xai <nick> <model> [profile]
add ollama <nick> <model>
add mock <nick> [profile]
remove <nick>
roster
ask <question>
quit
```

`auth add` does not accept a credential. It prints the existing secure enrollment commands instead.

The roster is ephemeral. A remote member contains only:

```json
{
  "member_id": "RemoteXAI",
  "model_id": "grok-4.5",
  "adapter_id": "xai",
  "auth_profile": "default",
  "timeout_seconds": 600
}
```

The profile name is an operational reference. It is not the secret itself.

```text
AUTH_PROFILE_REFERENCE != CREDENTIAL
```

The runtime resolves the credential only at the already-admitted auth/transport boundary.

## Equal-vote remote Council

The operator TUI can combine:

- fixed-destination xAI remote members;
- loopback Ollama members;
- deterministic mock members.

Council equality remains runtime-owned. The TUI never sends a custom vote weight or epistemic privilege.

```text
PROVIDER_IDENTITY != VOTE_WEIGHT
PROVIDER_IDENTITY != EPISTEMIC_PRIVILEGE
```

The existing runtime still enforces the four-seat xAI remote cap.

## Live xAI acceptance harness

A real network acceptance run is deliberately separate from CI:

```text
tools/live_xai_acceptance.py
```

CI may run only:

```bash
python3 tools/live_xai_acceptance.py --self-test
```

That structural self-test does not contact xAI.

A real run requires an explicit authorization flag:

```bash
PYTHONPATH=src python3 tools/live_xai_acceptance.py \
  --authorize-live-xai \
  --profile default \
  --model grok-4.5 \
  --output /absolute/path/nexus-alpha9-live-xai.json
```

The tool performs the following live preflight before the Council call:

1. resolve the named xAI profile through the existing auth broker;
2. run the admitted connection test;
3. perform live language-model discovery;
4. require the selected model to appear in discovery;
5. run one three-seat Council with two deterministic local mock peers and one live xAI peer;
6. re-read the resulting session and receipt from WorldStore;
7. write a private canonical JSON acceptance archive.

The archive contains references and bounded result metadata, not credential material or the original question text. The question is represented only by SHA-256.

The report is content addressed as:

```text
alpha9-live-acceptance:<sha256>
```

and is capped at 1 MiB canonical UTF-8.

## What the live run proves

A successful archived run establishes only that the configured path worked for that run:

```text
auth profile resolution
        +
connection test
        +
model discovery
        +
remote inference
        +
Council integration
        +
WorldStore session/receipt persistence
```

It does not establish model quality, scientific truth, provider superiority, or future availability.

```text
CONNECTION_SUCCESS != TRUTH
MODEL_DISCOVERY != MODEL_ENDORSEMENT
LIVE_ACCEPTANCE != SCIENTIFIC_VALIDATION
```

## Alpha9 completion state

Engineering work is complete when the Rust operator surface and acceptance harness pass hermetic CI.

The milestone's empirical live-network checkbox remains open until an operator actually runs the harness with a real local xAI profile and archives the resulting report. CI must never fabricate or substitute that evidence.

A second remote provider remains out of scope for this PR. Any second provider must receive its own descriptor, auth path, threat-model review, tests, and review before admission.
