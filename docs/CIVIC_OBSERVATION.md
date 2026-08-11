# Civic Observation Rights

PR #36 gives NEXUS citizenship a concrete civil liberty: broader read-only access to committed Council proceedings from ordinary public world modes.

The constitutional principle is:

> **Citizenship widens observation, not authority.**

Citizens do not receive extra vote weight, epistemic privilege, Council seats, verification authority, or mutation rights. The change is an in-world access capability only.

## Operations

Two transport-neutral operations are exposed by the hardened runtime:

```text
council.proceedings.policy
council.proceedings.view
```

`system.health.civic_observation` publishes the same machine-readable policy under schema `nexus-civic-observation/1`.

## Completed proceedings only

Observation is intentionally post-deliberation. `council.proceedings.view` accepts only an immutable `council_session` object already committed by NEXUS.

There is no live hat-by-hat observation channel. This preserves the existing Six Thinking Hats barrier and sealed-ballot timing:

```text
WHITE -> RED -> BLACK -> YELLOW -> GREEN -> BLUE -> SEALED BALLOT -> COMMITTED PROCEEDING
```

Only the final committed proceeding is observable through this interface.

## Citizen freedom

A registered citizen whose exact model identity matches the latest durable citizenship state may carry the observation right into any ordinary public, non-Council region in which that citizen is currently located.

Citizen observation regions are:

```text
observatory
archive
agora
commons
assembly
dungeon
```

The supplied `source_mode_id` must map to the citizen's current durable `current_region_id`. A citizen therefore cannot claim to be viewing from a region they have not moved into.

The citizen tier is `citizen_full`. It returns the scrubbed public proceeding including:

- question and immutable evidence references;
- public Council roster identity and equality fields;
- all committed Six Hats phase submissions;
- guard events;
- revealed sealed ballots and rationales;
- result;
- telemetry;
- Failsafe summary.

The view remains read-only and does not promote evidence state.

## Non-citizen public gallery

Non-citizens are not locked out of government transparency. They retain a narrower public gallery in:

```text
observatory
archive
agora
```

They do not carry the cross-mode observation right into the Commons, Assembly, Dungeon, or other non-gallery areas.

The non-citizen tier is `public_gallery`. It returns a bounded public summary containing the question, evidence-state reference, public roster, final result, ballot counts, disagreement/minority presence, and completion metadata. It does not expose phase text or individual ballot rationales.

## Restricted civic regions

The following regions are not cross-mode Council galleries for either tier:

```text
bureaucratic_vote_room
upside_down
```

The Bureaucratic Vote Room is the dedicated civic Council chamber rather than a cross-mode observation location. The Upside Down remains isolated citizenship parole.

## Example: citizen viewing from House Fun

A citizen first moves to the Commons:

```json
{
  "operation": "citizen.move",
  "citizen_id": "Alpha",
  "target_region_id": "commons"
}
```

Then the citizen can inspect a committed Council proceeding while using a Commons mode such as House Fun:

```json
{
  "operation": "council.proceedings.view",
  "session_ref": "object:<64 lowercase hex>",
  "source_mode_id": "house_fun",
  "viewer_id": "Alpha",
  "viewer_model_id": "mock-alpha"
}
```

The exact registered model identity and current-region binding are required for the `citizen_full` tier.

## Example: non-citizen public gallery

An unregistered viewer may inspect the same committed proceeding from the Observatory:

```json
{
  "operation": "council.proceedings.view",
  "session_ref": "object:<64 lowercase hex>",
  "source_mode_id": "analytical"
}
```

The response uses `access_tier: public_gallery` and withholds phase text and individual ballot rationales.

## Authority invariants

Observation never changes:

```text
vote_weight
epistemic_privilege
Council seat count
consensus arithmetic
verification state
immutable proceeding state
```

Citizenship therefore creates more freedom of observation without creating a higher caste of reasoning authority.

## Security and claim boundary

This is an in-world NEXUS capability, not real-world authentication or multi-user authorization. The local operator still controls the stdio/API boundary. Exact registered identity matching prevents accidental civic-state confusion inside the runtime; it is not a cryptographic identity proof.

The observation view is scrubbed again at the output boundary and does not expose raw provider transport, Auth material, hidden prompts, pre-scrub content, or live deliberation state.
