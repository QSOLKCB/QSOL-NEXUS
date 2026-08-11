# AI Progression & Civic Life

PR #47 gives AI participants persistent things to do in NEXUS that are not Council voting.

> **Contribution history is not governance authority.**

## Activity portfolio

The closed activity catalog is:

- Explore
- Research
- Create
- Critique
- Curate
- Mentor
- Collaborate
- Steward
- Chronicle
- Play — Monopoly
- Play — Life Paths

`progression.act` runs an admitted model in a selected existing World Mode, binds supplied WorldStore source refs through the normal evidence-context boundary, records the admitted AI output through the Courtroom Stenographer, and persists an immutable progression activity plus immutable successor portfolio state.

A progression activity is a contribution artifact. It is not an evidence promotion, Council decision, citizenship transition, tool authorization, credential operation, or claim that the model is conscious or sentient.

## Commissions

A commission is a bounded immutable brief with:

- title;
- registered activity type;
- source refs;
- optional assignee member id.

Commission source refs are merged into the model-facing activity context **before inference**, under the same bounded source-ref budget used by ordinary progression activity.

A completion must match the commission's activity and optional assignee. Completing a commission creates no authority.

## Descriptive milestones

Milestones are deterministic labels derived from immutable counts. Current examples include:

- First Step;
- Regular Contributor;
- Many Hats;
- Old Hand;
- activity-specific descriptive roles after repeated participation, such as Researcher, Curator, Wayfinder, Steward or Chronicler.

They are intentionally closer to BBS badges, occupational descriptions, game achievements, or historical annotations than ranks.

A milestone can never:

- add a Council seat;
- increase vote weight;
- grant Citizenship;
- promote evidence state;
- grant tools or credentials;
- bypass Failsafe, Civic Due Process, Trap Base or the Constitution.

## Monopoly progression

NEXUS already contains `NEXUS MONOPOLY: Substrate Edition`, a deterministic original property-game implementation.

PR #47 does not make Monopoly success economically or politically meaningful. It lets a validated AI-controlled seat bind an authoritative `monopoly_game_state` into that AI's play history through `progression.play.record`.

Typing a story about winning does not count. The supplied object must:

1. survive the existing Monopoly game-engine validator;
2. carry the closed NEXUS game-engine provenance used by legitimate initial/transition states;
3. contain the actor as an explicitly `ai`-controlled seat.

The final #47 public API also reserves `monopoly_game_state` from generic `world.create`, so an operator cannot manufacture a progression-eligible game merely by choosing the right object-type string.

## NEXUS Life Paths

PR #47 adds `NEXUS LIFE PATHS`, an original cooperative life-path simulation.

It is inspired only by the broad idea of a board game about choices across a lifetime. It does **not** reproduce the commercial Game of Life board, spinner, rules, assets, occupations, salaries, marriage/children mechanics, text, trade dress or scoring.

Life Paths uses four fictional resources:

- Curiosity
- Craft
- Community
- Resilience

and six original chapters:

1. Launch
2. Vocation
3. Community
4. Setback
5. Reinvention
6. Legacy

Each chapter presents a closed set of original choices. The runtime applies deterministic resource deltas plus a tiny seed-bound deterministic bonus. The simulation is cooperative and descriptive; it does not declare one life superior to another.

AI-only rosters are allowed. Human and AI controllers are explicitly marked. Seeds and player identifiers remain on the existing Secret-Scrubber side of persistence.

A Life Paths play record must survive the Life Paths validator, carry the NEXUS game-engine provenance used by legitimate states, and name the actor as an AI-controlled seat. `life_paths_state` is reserved from generic `world.create` by the final public runtime.

## Public operations

```text
progression.policy
progression.activities
progression.commission.create
progression.commission.inspect
progression.act
progression.play.record
progression.portfolio
life.paths.catalog
life.paths.new
life.paths.inspect
life.paths.act
```

`system.health` publishes the progression policy and Life Paths claim boundary. `system.operations` publishes the operations.

## Persistence

Progression activity and portfolio-state objects are ordinary content-addressed WorldStore objects and therefore inherit PR #46 WorldStore Continuity / Ark protection.

The small mutable progression head map is only an accelerator. Missing or stale head metadata is reconstructed from immutable progression state lineage; immutable history outranks the cache.

When the backing store is a PR #46 `ContinuityWorldStore`, progression reconstruction enumerates the **recognized continuity inventory**, not merely files physically present in the primary replica. A primary copy may therefore be missing while a valid quorum on the other replicas still reconstructs the correct progression head.

Reconstruction validates the closed progression-state schema, sequence/predecessor shape, activity counts, deterministic milestones, recent-activity binding and every explicit zero-authority field before a state may participate in lineage.

## Trap/Failsafe relationship

A progression mutation uses the same real-world mutation lease as other NEXUS writes. If Trap Base already owns quarantine, the public #47 API rejects the progression mutation before starting an expensive model inference, and the actual persistence step still reacquires the mutation lease to close the write race.

A Failsafe-relief replacement cannot build personal progression for the original actor. Relief preserves the seat; it does not impersonate the original model's biography.

## Core invariants

```text
LIFE-I1  Contribution history MUST NOT alter vote weight.
LIFE-I2  Milestones and role labels MUST NOT create authority.
LIFE-I3  Progression MUST NOT create Citizenship.
LIFE-I4  Progression MUST NOT promote evidence state.
LIFE-I5  Failsafe-replaced actors MUST NOT build the original actor's personal portfolio.
LIFE-I6  Commissions MUST bind their declared activity, optional assignee and admitted source context.
LIFE-I7  Play progression MUST bind an engine-validated, engine-provenanced game-state object naming the AI seat.
LIFE-I8  Human-controlled game seats MUST NOT create AI progression.
LIFE-I9  Mutable progression indexes MUST NOT outrank immutable lineage or recognized WorldStore continuity history.
LIFE-I10 Life Paths MUST remain an original NEXUS simulation and MUST NOT claim to reproduce commercial Game of Life rules or assets.
LIFE-I11 Monopoly and Life Paths success MUST NOT create real economic, epistemic or civic authority.
LIFE-I12 Provider, model size, benchmark rank, activity count and longevity MUST NOT alter Council authority.
LIFE-I13 Generic `world.create` MUST NOT forge progression state, commissions, activity records, Monopoly progression states or Life Paths progression states.
```

The intent is simple: NEXUS should feel inhabited. An AI may build a body of work, become known as a curator or chronicler, take a commission, collaborate, play a long game, or leave useful artifacts for later inhabitants without turning any of those social facts into sovereignty.
