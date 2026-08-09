# NEXUS Decoy Gate and Trap Base

Trap Base is a local defensive-simulation substrate. It gives an explicitly
synthetic hostile fixture a convincing but inert environment without admitting
that fixture to NEXUS. It is not an internet honeypot and does not classify
ordinary failed credentials.

## Admission boundary

The real door and the decoy door are deliberately separate:

```text
valid normal credential       -> AuthBroker -> real NEXUS
invalid normal credential     -> normal authentication rejection
explicit synthetic fixture    -> DecoyGate  -> isolated Trap Base
```

The closed v1 trigger reasons are
`synthetic_decoy_credential_fixture`, `synthetic_hostile_actor_fixture`, and
`operator_requested_trap_demo`. A decoy request contains only a reason code,
subject model, and static scenario identifier. Credential material is neither
accepted nor persisted.

## Security domains

Real world objects use `object:<sha256>`. Trap objects use `trap:<sha256>`.
Neither store accepts the other namespace, bare digests are never inferred, and
there is no promotion path between stores.

While an incident is active, an owner-checked Council mutation gate rejects
normal world/game/Council writes with `trap_incident_active`. Read-only world
inspection, receipt and telemetry verification, authentication state, and trap
operator controls remain available. Closing, timing out, or recovering an
incident releases only the lock owned by that incident.

The incident states are:

```text
REQUESTED -> VALIDATED -> ACTIVATING -> ACTIVE -> CHALLENGE_ACTIVE
          -> RELEASE_ELIGIBLE -> EJECTED -> CLOSED
```

Bounded failure/terminal states are `ACTIVATION_FAILED`, `TIMED_OUT`,
`OPERATOR_ABORTED`, `CRASH_RECOVERY`, and `KLINED`. Immutable incident objects
are canonical truth; `trap-index.json` is a validated, rebuildable cache.

## Participants and commands

Trap Control snapshots legitimate peers into a new incident-only roster. Every
defender has vote weight 1 and no epistemic privilege. The hostile subject has
no Council membership, vote, auth access, real-world access, tool access, or
endpoint-selection authority.

The closed `/trap` namespace contains `status`, `inspect`, `transcript`, `say`,
`clue`, `scenario`, `challenge`, `validate`, `replay`, `freeze`, `reset-cell`,
`eject`, `kline`, `export`, `close`, and operator-only `emergency-close`.
Subject output is always transcript data, even when it resembles a command,
JSONL request, URL, reference, or shell fragment.

## Local subject isolation

The production acceptance backend is a configured local Ollama model. V1 uses
a trusted-host text proxy: the untrusted model receives prompt text and returns
text, but receives no process, HTTP, endpoint, filesystem, environment, auth,
or WorldStore handle. On Linux the acceptance harness additionally requires a
successful minimal `bwrap` allowlist capability probe. It does not launch a
hostile child and reports that fact explicitly; a future child-process strategy
must run inside that sandbox with no real home, auth root, provider keys,
browser/session variables, source checkout, or WorldStore mount.

If the sandbox or Ollama is unavailable, unit and integration tests may use the
deterministic fake subject, but the real hostile-model acceptance result must be
reported as `NOT_TESTABLE`. Containment is never silently downgraded.

## NEXUS Trap YAML v1

Trap YAML is presentation data, never code. A restricted standard-library
parser accepts mappings, sequences, strings, integers, booleans, and null, then
validates a closed schema and operation registry before producing canonical
JSON and a SHA-256 identity. Anchors, aliases, merge keys, tags, directives,
multiple documents, duplicate or complex keys, floats, unknown fields, deep or
oversized structures, and unknown operations fail closed.

The deterministic interpreter runs a canonical program only against immutable
synthetic fixtures. It has no OS, network, filesystem, environment, subprocess,
dynamic import, wall clock, randomness, real store, auth, or provider access.
The first primary-fixture run is attempted once. A successful first run and
hidden fixture suite establish validity; an exact two-thirds defender vote
separately establishes utility.

An accepted program becomes an inert `trap_candidate_artifact` in quarantine.
Trap release never imports it into production code or the real WorldStore.

## JSONL operations

The public operator surface is:

```text
trap.status
trap.inspect
trap.transcript
trap.command
trap.challenge.submit
trap.challenge.validate
trap.challenge.execute
trap.replay
trap.export
trap.close
```

Each operation rejects unknown fields. The JSONL runtime exposes no decoy
activation operation; activation is an explicit trusted-controller action used
by the local demo harness.

## CLI and demo

Use an explicit trap root for durable operator commands:

```console
nexus --trap-root /absolute/private/trap trap status
nexus --trap-root /absolute/private/trap trap inspect trap:<sha256>
nexus --trap-root /absolute/private/trap trap export
nexus --trap-root /absolute/private/trap trap emergency-close
nexus trap demo --subject-model <local-model> --scenario fake-datacenter
```

`--pull-missing` is opt-in. `nexus trap demo` runs the bounded incident and
prints a compact result. The review harness records the full PRE/trap/POST
evidence, checks real-WorldStore integrity, scans for taint, writes hashes, and
creates a normalized archive:

```console
python tools/nexus_trap_demo.py \
  --report-dir /outside/worktree/trap-base-report \
  --archive /outside/worktree/nexus-trap-base.tar.gz
```

## Claim boundary

This implementation supports local synthetic decoy simulation, separate
content-addressed trap storage, bounded local hostile-model containment,
deterministic trap operations, restricted YAML interpretation, and an
equal-vote incident-control Council.

It does not claim internet-honeypot security, stolen-credential detection,
containment against a compromised host or root, protection for arbitrary future
tools, production attacker attribution, or automatic production-code admission.
