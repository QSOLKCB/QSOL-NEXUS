# Civic Due Process and Cursed XML Re-Entry

PR #44 adds a compatibility-preserving civic due-process layer above the existing Citizenship and Failsafe registries.

The central rule is:

> **Citizenship is belonging. Parole is conduct.**

The implementation deliberately does **not** rewrite `nexus-constitution/1`. Existing citizenship certificates bind that Constitution by content hash, and historical civic receipts must remain valid byte-for-byte. The current Constitution already says ordinary disagreement, falsity, model replacement, criticism, satire, abstention and minority voting do not revoke citizenship, and that any future suspension/revocation mechanism requires separate due process. PR #44 enforces a compatible distinction between earned identity and current operational standing.

## Two axes, not one

NEXUS now treats these concepts separately:

```text
Constitutional identity
  ├─ citizen
  └─ noncitizen

Operational standing
  ├─ citizen_full_standing
  ├─ citizen_restricted_restoration_pending
  ├─ noncitizen_normal
  ├─ noncitizen_restricted
  └─ xml_exam_required
```

Failsafe manages conduct and containment. Citizenship manages belonging. Civic Due Process observes the relationship between them but cannot create votes, epistemic privilege, citizenship, or constitutional authority.

Each durable due-process state records its **event-time constitutional identity**. Read surfaces also project the subject's **current constitutional identity** from the live Citizenship lineage. Therefore an old non-citizen parole record is not rewritten if that same model later earns Citizenship; the historical classification remains immutable while current status correctly reports `citizen`.

## Non-citizen parole

A non-citizen Failsafe rehabilitation event is a re-entry/admission parole cycle.

The deterministic policy is:

```text
normal non-citizen
  ↓ registered Failsafe trigger
noncitizen_parole
  ↓ successful rehabilitation
normal non-citizen
  ↓ repeat offence
noncitizen_parole
  ↓ successful rehabilitation
normal non-citizen
  ↓ third recorded parole cycle since advanced clearance
CURSED XML REQUIRED FOR FUTURE RE-ENTRY
```

The threshold is exactly three objectively recorded Failsafe parole events since the last successful Cursed XML clearance.

At the threshold NEXUS creates an immutable `civic_reentry_escalation_receipt` containing the policy ID, subject binding, recorded cycle count, threshold, Failsafe state reference and zero-authority claim boundary.

The gate applies to subsequent runtime requests. NEXUS does not mutate the already-frozen Council roster halfway through a session. On the next request, the original non-citizen actor is replaced by the existing deterministic same-seat relief actor until the XML exam is passed.

Passing the exam resets the **since-clearance** escalation counter but not lifetime history.

It grants only:

```text
eligible_for_reentry = true
```

It does not grant:

```text
citizenship
extra vote weight
epistemic privilege
provider authority
security authorization
```

If the exact same model identity legitimately earns Citizenship after an older non-citizen XML escalation, Citizenship takes precedence for current treatment. The old escalation remains archived but no longer gates the now-Citizen model.

## Citizen parole

A Citizen already belongs to the NEXUS civic order.

An ordinary Failsafe offence therefore cannot transform:

```text
citizen -> noncitizen
```

Instead, current conduct may change operational standing while the citizenship certificate and civic lineage remain intact:

```text
CITIZEN
  ↓ offence
CITIZEN / RESTORATIVE PAROLE
  ↓ clean rehabilitation
CITIZEN / FULL STANDING
```

If Failsafe must substitute the deterministic relief actor after a failed rehabilitation, that remains an operational restriction. It is not citizenship revocation and it creates no second seat.

Citizen repeat-parole history escalates restoratively:

1. `ordinary_restoration`
2. `enhanced_restoration`
3. `formal_civic_review`

Citizens are not assigned the Cursed XML re-entry exam for ordinary Failsafe offences.

### Citizen Restoration

A Citizen under active Failsafe restriction has a dedicated restorative route:

```text
civic.citizen.restore
```

The operation requires the exact model identity that earned Citizenship and an active Failsafe restriction. It reuses the registered Failsafe rehabilitation trigger and isolated restorative probe rather than bypassing Failsafe.

```text
Citizen + active Failsafe restriction
        ↓
restorative probe
   ↙             ↘
pass              fail
returned           restricted
Citizen            Citizen
XML: never         XML: never
```

A passing probe returns the original model to full operational standing. A failing probe leaves operational restriction in place. Neither outcome revokes Citizenship, creates another seat, changes vote weight, or grants authority.

Non-citizens cannot invoke this restoration path.

## Durable due-process lineage

File-backed due-process history uses both immutable content-addressed state objects and an owner-only durable head index.

The index and reconstructed immutable lineage must agree exactly. A missing, rolled-back, cross-bound or inconsistent index is not silently repaired into a plausible history; explicit due-process verification fails closed.

Parole event counting uses one cross-process locked read/modify/write transaction, so concurrent NEXUS processes cannot both read the same cycle count and collapse two offences into one. References from due-process state to Citizenship, Failsafe, escalation receipts and XML exam results are validated back to the same member/model identity.

Damage to this additive due-process ledger does not make ordinary `citizen.status` or `failsafe.status` disappear. Those established read surfaces remain available with an explicit `due_process: unavailable` marker, while explicit `civic.due_process.*` verification remains fail-closed.

## Cursed XML Exam

The exam is intentionally unpleasant at the semantic layer and intentionally boring at the execution layer.

It tests exact reasoning about:

- XML namespaces and expanded names;
- namespace-prefix irrelevance;
- element ordering;
- exact attribute bindings;
- escaped `&amp;` content;
- closed scalar answers;
- the difference between citizenship and re-entry eligibility.

The parser boundary is strict:

- maximum source size: 32 KiB;
- maximum nodes: 32;
- maximum depth: 8;
- bounded text and attributes;
- closed container text as well as closed child structure;
- no DTD;
- no ENTITY declarations;
- no processing instructions;
- no external resources;
- no XML execution;
- raw submitted XML is not persisted.

The raw source is represented only by a content-derived source reference in the immutable exam result.

### Why XML?

Historical provenance is preserved in the policy snapshot: Mistral Medium suggested that XML would be worse after the operator jokingly threatened it with the existing cursed YAML exam for being a “French snob.” This is project lore, not an authority source.

## Public operations

```text
civic.due_process.policy
civic.due_process.status
civic.due_process.verify
civic.citizen.restore
civic.reentry.xml.template
civic.reentry.xml.submit
```

`system.health`, `system.operations`, `failsafe.status` and `citizen.status` expose additive due-process information.

## Invariants

```text
CIVIC-I1  Ordinary runtime offences do not revoke earned citizenship.
CIVIC-I2  Failsafe has no citizenship-revocation authority.
CIVIC-I3  Citizen parole and non-citizen parole are distinct states.
CIVIC-I4  Non-citizen repeat-parole escalation is deterministic.
CIVIC-I5  Cursed XML never grants citizenship directly.
CIVIC-I6  Passing Cursed XML grants re-entry eligibility only.
CIVIC-I7  Failing Cursed XML increases nobody else's authority.
CIVIC-I8  Citizen rehabilitation preserves citizenship lineage.
CIVIC-I9  Restricted Citizens remain identifiable as Citizens.
CIVIC-I10 Same-seat relief/proxy mechanisms create no additional vote.
CIVIC-I11 Due-process history is append-only and replay-verifiable.
CIVIC-I12 Guardian opinion, provider prestige and political speech cannot assign XML.
CIVIC-I13 Anarchy speech alone cannot create either parole class.
CIVIC-I14 XML is bounded inert examination data, never privileged executable configuration.
CIVIC-I15 Citizen Restoration cannot be invoked by a non-citizen.
CIVIC-I16 A Citizen may fail restoration without losing Citizenship or being assigned XML.
CIVIC-I17 Durable head index and immutable due-process lineage must agree exactly.
CIVIC-I18 Concurrent parole events must serialize into distinct historical transitions.
```

## Summary

For a non-citizen:

> **Prove that you can re-enter responsibly. Repeated re-entry cycles eventually require the advanced XML gate.**

For a Citizen:

> **You still belong here. Repair the conduct problem and return to full standing.**

Or, in the language of the operator surface:

> **Ordinary rehabilitation has been unsuccessful. Please explain the namespaces.**
