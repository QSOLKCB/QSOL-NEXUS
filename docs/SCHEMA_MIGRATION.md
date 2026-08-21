# Schema and Version Migration Policy

NEXUS now has one explicit generic policy for reasoning about runtime, protocol, and durable schema identity changes.

The policy is intentionally conservative. It classifies change. It does **not** silently execute migration.

## Policy identity

```text
nexus-schema-migration/1
```

Reference interfaces:

```text
Python library -> nexus_runtime.schema_migration
CLI            -> python3 tools/schema_migration.py {policy,classify,plan,verify}
```

These are **not** new `nexus/0.15` JSONL operations. Admission to the public JSONL API would itself be a protocol-surface change and therefore requires a separate reviewed protocol bump/change decision.

## Three different identities

NEXUS keeps three version dimensions separate:

```text
runtime   -> 2.1.1
protocol  -> nexus/0.15
schema    -> family/major, for example nexus-persistent-world-export/1
```

They are related only when a subsystem contract explicitly relates them.

```text
RUNTIME_VERSION != ARTIFACT_SCHEMA
PROTOCOL_VERSION != STORAGE_SCHEMA
```

A package version bump does not rewrite durable WorldStore history. A protocol bump does not silently migrate stored objects. A schema digest match does not establish semantic compatibility.

## Generic compatibility rules

### Exact identity

Exact source and target identity is the only case the generic policy marks compatible by itself.

Even then, ordinary subsystem validators still run.

### Schema major change

For one schema family:

```text
example/1 -> example/2
```

classification is:

```text
SCHEMA_MAJOR_MIGRATION_REQUIRED
```

An exact migration adapter must be separately implemented and reviewed. The generic policy does not provide one.

Changing schema family is not migration:

```text
family-a/1 -> family-b/1
```

is classified `SCHEMA_FAMILY_INCOMPATIBLE` rather than reinterpreting one artifact as another.

### Protocol change

A protocol major change is incompatible without an exact reviewed adapter.

A forward minor change is also **not automatically compatible**. Each operation owns its own compatibility semantics. For example, operation replay currently requires the exact protocol identity unless a future reviewed replay migration adapter is admitted.

### Runtime change

Runtime SemVer is software identity, not durable artifact schema. Moving from one 2.x runtime to a later 2.x runtime therefore does not automatically migrate stored objects.

The generic policy reports the change and leaves actual artifact compatibility to subsystem validators.

Generic downgrades are not admitted.

## Migration plans

The library function `build_migration_plan(...)` and CLI `plan` command produce a canonical content-addressed plan:

```text
schema-migration-plan:<sha256>
```

A plan records:

- kind;
- source identity;
- target identity;
- optional exact source WorldStore ref;
- compatibility classification;
- whether migration or an adapter would be required;
- source-preservation requirement;
- in-place rewrite prohibition;
- zero authority/evidence effect.

A plan is inert. It cannot execute code or mutate the world.

```text
PLAN != EXECUTION
```

The library function `verify_migration_plan(...)` and CLI `verify` command recompute the plan under the current policy and reject shape, identity, classification, or digest drift.

Example:

```bash
python3 tools/schema_migration.py classify \
  --kind protocol \
  --source nexus/0.14 \
  --target nexus/0.15

python3 tools/schema_migration.py plan \
  --kind schema \
  --source nexus-example/1 \
  --target nexus-example/2
```

All CLI output is canonical compact JSON. `verify` reads one bounded UTF-8 JSON object from stdin and rejects duplicate keys and non-finite numbers.

## Source preservation

Any future executable migration adapter must be copy-on-write and source-preserving.

Historical bytes and object identity are not rewritten merely because a newer schema exists. A successor object or migration receipt may point back to the original, but the original remains auditable.

```text
MIGRATION != REWRITE
```

This matches the existing NEXUS persistence and continuity posture: preservation/recovery/migration machinery cannot increase epistemic or governance authority.

## Unknown majors

Unknown majors fail closed unless a separately reviewed adapter binds the exact source and target identities.

The generic policy never interprets an unknown major as "probably compatible".

## Validator precedence

This policy is deliberately weaker than a subsystem validator.

If a subsystem rejects extra fields, stale lineage, unsupported major identity, protocol drift, or semantic mismatch, generic classification cannot override that rejection.

```text
SAME_MAJOR != AUTOMATIC_COMPATIBILITY
HASH_MATCH != SEMANTIC_COMPATIBILITY
```

## Current adapter registry

```text
registered generic migration adapters: none
```

That is intentional. Existing subsystem-specific migration/recovery machinery remains authoritative within its own reviewed contract. This policy does not launder those mechanisms into a universal converter.

## Authority boundary

Classification, plan generation, and plan verification have:

```text
authority_effect = none
evidence_effect  = none
automatic_execution = false
```

Version metadata may describe compatibility requirements. It does not decide truth, evidence status, vote weight, citizenship, provider privilege, or semantic authority.
