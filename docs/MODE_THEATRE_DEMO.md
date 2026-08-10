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
mode_theatre_evidence_context x 6
mode_theatre_entry x 6
mode_theatre_run
receipt
```

Every entry records the requested/effective model identity, mode, geometry region, immutable source refs, the exact bounded evidence-context ref actually supplied to the actor, round position, role, content, Failsafe replacement state, and the invariant `additional_votes_created = 0`.

Earlier model contributions are never rewritten merely because a later mind has a better joke.

## Bounded all-source evidence

The generic NEXUS evidence renderer has strict per-object and total character budgets. Passing every growing transcript object directly would therefore allow an oldest-first context to consume the budget before a later House or Forum contribution becomes model-readable.

Mode Theatre avoids claiming continuity it cannot prove. Before **every** actor call it creates one compact `mode_theatre_evidence_context` object. That object:

- lists every immutable source ref required for that turn;
- contains a bounded excerpt from every listed source;
- stays below the generic per-object evidence limit;
- is the only evidence ref passed to that actor call;
- records that excerpts are convenience views and the original immutable source objects remain authoritative.

For the final Forum speaker the compact source index therefore represents:

```text
task
+ House 1
+ House 2
+ House 3
+ Forum 1
+ Forum 2
```

The demo claims **bounded all-source representation**, not that every character of every previous model response fits inside one prompt.

## Mandatory logs

A Mode Theatre run does **not start model/provider work until it has reserved a unique local archive directory**.

The archive contains:

```text
events.jsonl        canonical machine-readable event log
transcript.md       human-readable transcript for later amusement
manifest.json       pre-success archive commitment and source identity
stenographer/       normal Courtroom Stenographer records when the CLI is used
ERROR.txt           only when a run fails or is interrupted after archive reservation
```

The human transcript is generated from the **scrubbed WorldStore objects**, not from unsanitized raw operator input. Custom case/motion text therefore crosses the normal NEXUS semantic secret-scrubbing boundary before it is copied into the laugh-later transcript.

The archive manifest is committed **before** the successful `mode_theatre_run` object and receipt are created. If manifest creation fails, NEXUS does not persist a successful Mode Theatre run or verified success receipt. The later `mode_theatre_run` stores the archive commitment ref, so WorldStore success can only claim that the already-committed archive exists.

The manifest deliberately avoids a stronger claim than NEXUS can verify. It records that archive inputs came from WorldStore objects after the runtime's high-confidence scrubber and that raw credentials are not intentionally collected, but it sets `credential_absence_verified` to `false`. An unrecognized secret format cannot therefore be mistaken for a certified secret-free archive.

No host-specific WorldStore path is stored in the archive manifest.

## Interrupts

A live provider call can take long enough for an operator to press Ctrl-C. The CLI catches `KeyboardInterrupt` only long enough to write a fixed `ERROR.txt` interruption marker into the already-reserved archive, then re-raises the interrupt so normal Ctrl-C exit behavior is preserved.

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
+ bounded all-source cross-round evidence
+ immutable attributed lineage
+ pre-success mandatory durable logs
+ verified receipt
```

It does **not** demonstrate diagnosis, truth, provider superiority, consciousness, rhetorical authority, certified secret absence, or stable-2.0 completion.

The constitutional rule remains gloriously boring:

> **The mode can change the vibe. It cannot change the vote.**
