# NEXUS Multi-Mind Mode Theatre

## Purpose

This is the deliberately unserious companion demo to **Three Minds, One World**.

Three equal model identities inhabit the same persistent NEXUS world and exercise two existing cognitive modes:

```text
House Fun:     Alpha -> Beta -> Gamma
Roman Orator:  Gamma -> Beta -> Alpha
```

The reversed second-round order is intentional. The mind that closes the fictional diagnostic bit has to open the Forum, and the mind that opened the whiteboard gets the final grand peroration.

The demo is not a Council vote. It creates no extra authority and does not turn jokes, confidence, theatrical diagnoses, rhetoric, applause, or provider branding into evidence.

## Default material

The House round uses an explicitly fictional machine case:

```text
The Observatory's ancient printer emits a perfect ECG trace when somebody says YAML,
turns blue during karaoke, and refuses to print without an unreasonable zebra diagnosis.
```

The Roman Orator round then debates:

```text
Resolved: after the printer incident, YAML indentation remains the final pillar holding
civilisation together, and the maintainers must defend it before the Forum.
```

The defaults are intentionally ridiculous because the point is to demonstrate mode framing and shared evidence while producing a transcript worth keeping.

## Persistent lineage

The runtime creates ordinary content-addressed WorldStore objects:

```text
mode_theatre_task
mode_theatre_entry x 6
mode_theatre_run
receipt
```

Every entry records the requested/effective model identity, mode, geometry region, evidence refs, round position, role, content, Failsafe replacement state, and the invariant `additional_votes_created = 0`.

The House entries become evidence for the Roman Orator round. Earlier model contributions are never rewritten merely because a later mind has a better joke.

## Mandatory logs

A Mode Theatre run does **not start model/provider work until it has reserved a unique local archive directory**.

The archive contains:

```text
events.jsonl        canonical machine-readable event log
transcript.md       human-readable transcript for later amusement
manifest.json       archive/run/receipt identity
stenographer/       normal Courtroom Stenographer records when the CLI is used
ERROR.txt           only when a run fails after archive reservation
```

The human transcript is generated from the **scrubbed WorldStore objects**, not from unsanitized raw operator input. Custom case/motion text therefore crosses the normal NEXUS semantic secret-scrubbing boundary before it is copied into the laugh-later transcript.

The archive manifest deliberately does not store credentials or host-specific WorldStore paths.

## Hermetic run

The default roster uses three deterministic mock minds:

```bash
PYTHONPATH=src python3 tools/nexus_mode_theatre_demo.py \
  --world /tmp/nexus-mode-theatre-world \
  --archive-root /tmp/nexus-mode-theatre-archives
```

The command prints canonical JSON to stdout and the archive directory to stderr.

## Heterogeneous run

The CLI accepts the same provider-aware member objects used by `actor.chat` and the alpha11 shared-world demo.

Example shape:

```bash
PYTHONPATH=src python3 tools/nexus_mode_theatre_demo.py \
  --world .nexus-mode-theatre-world \
  --auth-root .nexus-auth \
  --archive-root .nexus-mode-theatre-archives \
  --mind-a '{"member_id":"LocalOpen","model_id":"YOUR_OLLAMA_MODEL","adapter_id":"ollama"}' \
  --mind-b '{"member_id":"OpenAI","model_id":"YOUR_OPENAI_MODEL_ID","adapter_id":"openai","auth_profile":"default"}' \
  --mind-c '{"member_id":"Gemini","model_id":"YOUR_GEMINI_MODEL_ID","adapter_id":"gemini","auth_profile":"default"}'
```

No raw cloud credential is accepted by the demo runner. Existing NEXUS authentication profiles remain the credential path.

## Custom material

Both prompts are bounded and may be replaced:

```bash
--house-case "Fictional case: the build server only compiles when insulted in COBOL."
--orator-motion "Resolved: package managers have become republics within the republic."
```

Keep the House case fictional. Real-person symptom input belongs outside this demo and is subject to the existing `house_fun` safety boundary.

## Claim boundary

A successful run demonstrates:

```text
three distinct minds
+ two existing cognitive modes
+ persistent cross-round evidence
+ immutable attributed lineage
+ mandatory durable logs
+ verified receipt
```

It does **not** demonstrate diagnosis, truth, provider superiority, consciousness, rhetorical authority, or stable-2.0 completion.

The constitutional rule remains gloriously boring:

> **The mode can change the vibe. It cannot change the vote.**
