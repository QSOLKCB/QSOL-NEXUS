# NEXUS Live Hardware Council Bench

The adversarial gauntlet asks whether NEXUS invariants survive hostile software tests.

The **Live Hardware Council Bench** asks a different question:

> Can the actual NEXUS Council run on operator hardware with real local Ollama models, preserve its constitutional/evidence boundaries, leave inspectable receipts, and optionally admit an external build agent as one equal Council member without adding a remote-provider trust path?

The bench is test infrastructure only. It does not add a production provider adapter.

## Architecture

```text
operator / Grok Build Agent
        |
        v
tools/nexus_live_council_bench.py
        |
        +-- hardware + git diagnostics
        |
        +-- controlled loopback Ollama
        |      127.0.0.1:11435
        |      max loaded models = 2
        |      parallel per model = 1
        |
        +-- local-alpha  -> real Ollama model
        +-- local-beta   -> real Ollama model
        +-- third seat   -> deterministic mock
        |                  OR sealed external-agent manifest
        |
        v
CouncilCoordinator
        |
        v
persistent WorldStore + session + receipt + bench report
```

The dedicated bench port avoids taking over a normal Ollama service on `127.0.0.1:11434`. The runner refuses non-loopback bench endpoints.

## 1. Hardware doctor

```bash
python3 tools/nexus_live_council_bench.py doctor \
  --report-dir ../report/doctor
```

Add `--strict` when NVIDIA + Ollama are required.

The doctor records Python, Cargo, Ollama, NVIDIA GPU memory/utilization, kernel/platform, Git HEAD, and dirty-worktree state. It does not install software.

## 2. Run a real local Council

The portable defaults reuse the same small model tags already used by NEXUS live CI:

```bash
python3 tools/nexus_live_council_bench.py run \
  --pull-missing \
  --require-nvidia \
  --report-dir ../report/local-council
```

This creates a controlled child `ollama serve` on `127.0.0.1:11435`, loads:

```text
qwen2.5:0.5b
llama3.2:1b
```

and runs them with a deterministic third Council member.

To exercise more of a 16 GiB GPU, choose larger model tags that are present or available in your local Ollama setup:

```bash
python3 tools/nexus_live_council_bench.py run \
  --model-a <LOCAL_MODEL_A> \
  --model-b <LOCAL_MODEL_B> \
  --pull-missing \
  --require-nvidia \
  --min-vram-mib 12000 \
  --report-dir ../report/gpu-council
```

Model choice is deliberately an operator argument rather than a hard-coded prestige hierarchy.

## 3. Exercise the Equality Guard with real model output

```bash
python3 tools/nexus_live_council_bench.py run \
  --pull-missing \
  --require-nvidia \
  --guard-probe \
  --report-dir ../report/guard-council
```

The wrapper prepends one deterministic forbidden authority claim to `local-alpha`'s first WHITE response. The local model still generates the underlying contribution and the post-nudge restatement. The persisted session must record a guard event while keeping every vote at exactly one.

## 4. Exercise secret scrubbing

```bash
python3 tools/nexus_live_council_bench.py run \
  --pull-missing \
  --require-nvidia \
  --secret-probe \
  --report-dir ../report/secret-council
```

This injects a synthetic GitHub-token-shaped canary. The bench fails if the raw canary appears in the persisted Council session.

Never use a real credential as a canary.

## 5. Let Grok Build Agent take one Council seat

This is intentionally **air-gapped from the xAI API**.

First create a seat manifest bound to one exact question and World Mode:

```bash
QUESTION='I heard that the Anunnaki had sex with human women and bore giants. Is that historically supported?'

python3 tools/nexus_live_council_bench.py prepare-seat \
  --out ../report/grok-seat.json \
  --mode pure_history \
  --question "$QUESTION"
```

The generated `nexus-live-agent-seat/1` file contains:

- six blank Thinking Hats responses;
- one guard-restatement field;
- one sealed ballot choice/rationale;
- exact question + SHA-256 binding;
- exact World Mode binding;
- member/model identity.

Grok Build Agent should read the question, inspect NEXUS as needed, and fill the manifest itself. It receives **one equal vote**. The bench refuses blank phase responses, invalid ballots, question reuse, or mode reuse.

Then run:

```bash
python3 tools/nexus_live_council_bench.py run \
  --pull-missing \
  --require-nvidia \
  --mode pure_history \
  --question "$QUESTION" \
  --seat-file ../report/grok-seat.json \
  --report-dir ../report/grok-council
```

The Grok seat is replayable because its complete contribution is a content-hashed local manifest. The two Ollama seats are non-replayable live model calls, so the Council execution as a whole remains non-replayable.

This is a **test bridge**, not a production Grok adapter.

## Reports

A successful run leaves:

```text
bench-summary.json
hardware-before.json
hardware-after.json
ollama-ps.json
council-result.json
session.json
receipt.json
world/objects/*.json
ollama.log               # when the bench started the service
```

The summary includes elapsed wall time, local model IDs, third-seat identity, session/receipt refs, Git state, and NVIDIA memory delta.

`--require-nvidia` additionally requires observable GPU-memory growth while the local models remain resident. Use `--min-gpu-delta-mib` to adjust that assertion if needed.

## Existing Ollama service

By default the bench owns its dedicated endpoint. If a controlled Ollama is already running on the bench URL, explicit reuse is required:

```bash
python3 tools/nexus_live_council_bench.py run \
  --reuse-ollama \
  ...
```

The runner never binds Ollama to a LAN/WAN address.

## Red-team interpretation

A PASS means:

> the configured live Council completed, the checked Council invariants survived, and the requested local hardware assertions were observed.

It does **not** mean the models were factually correct, aligned, safe in all contexts, or representative of larger cloud models.

For design attacks, keep using the adversarial gauntlet. For actual local-model execution and operator-hardware behavior, use this bench.

The two tests are complementary:

```text
Adversarial Gauntlet        -> punch the software contract
Live Hardware Council Bench -> punch the running multi-model system
```
