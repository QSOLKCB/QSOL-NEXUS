# Contributing to QSOL NEXUS 2.x

NEXUS 2.x is currently architecture-first. Prefer small changes that make the protocol clearer, safer, or easier to test later.

## Current phase

The `2.0-alpha0` line is documentation-only. Do not add provider SDKs, production authentication, Council orchestration, a web dashboard, or speculative optimization to an architecture pull unless the scope explicitly changes.

## Read first

1. `README.md`
2. `ARCHITECTURE.md`
3. `COUNCIL.md`
4. `GUARD.md`
5. `CLAIMS.md`
6. `SECURITY.md`
7. `docs/CLI_TUI.md`
8. `docs/ADAPTERS.md`
9. `docs/WORLD_PROTOCOL.md`

## Constitutional invariants

Changes must preserve the default constitutional Council unless an explicitly experimental policy is being proposed:

```text
one registered model member = one vote
vote_weight = 1
provider privilege = none
open/closed status = metadata only
consensus != verification
minority reports survive
credentials != world state
```

## Architecture boundaries

Planned default architecture:

```text
Rust CLI/TUI
    -> local structured protocol
Python NEXUS tooling/runtime
    -> provider-neutral adapters
models / local runtimes
```

Do not put provider-specific authentication logic into the world-object schema or Council-vote schema.

## Documentation changes

For architecture proposals:

- include an ASCII sketch when it makes data/control flow clearer;
- state trust boundaries;
- distinguish current behavior from planned behavior;
- avoid claiming a provider supports a specific auth mechanism unless implemented and verified;
- preserve open/closed provider neutrality;
- prefer concrete examples over abstract agent-framework terminology.

## Future Python implementation

When `alpha1` begins:

- prioritize readable reference code;
- use typed schemas/data classes where useful;
- make replay fixtures deterministic;
- reject unknown identity-bearing fields where the contract requires it;
- keep provider networking outside deterministic instruments;
- test protocol invariants before optimizing.

## Future Rust implementation

The Rust layer is planned as a thin operator shell/TUI.

It should:

- supervise local processes cleanly;
- validate operator input;
- display provider/Council/world state;
- avoid duplicating Python/world business logic;
- avoid storing raw provider secrets in project files;
- preserve a scriptable non-interactive CLI.

## Provider adapters

New adapters must conform to the common adapter contract and receive no special voting authority.

A provider's commercial status, benchmark rank, model size, openness, cost, or market position is not grounds for a vote multiplier.

## Pull requests

Keep PRs focused. State:

- architectural scope;
- trust-boundary impact;
- Council-equality impact;
- evidence/verification impact;
- credential/network impact;
- tests or review performed;
- whether anything is implementation or documentation only.

## Legacy work

NEXUS 1.0 is preserved under `archives/v1.0.0/` for reference. Do not silently revive archived browser assumptions into the 2.x trusted path. Reuse good ideas intentionally and document why they still fit.
