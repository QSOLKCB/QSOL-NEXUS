# NEXUS Claim and Evidence Boundaries

## Core rule

NEXUS distinguishes **collective judgment** from **verification**.

A Council may agree strongly and still be wrong. A deterministic instrument may verify an observation without verifying the interpretation placed on that observation.

## Council status

Council status describes what the participating members currently judge.

Suggested states:

```text
UNANIMOUS
STRONG_CONSENSUS
CONSENSUS
MAJORITY_NO_CONSENSUS
NO_CONSENSUS
```

The ballot disposition is separate:

```text
ACCEPT
ACCEPT_WITH_CHANGES
TEST_FURTHER
REJECT
UNDERDETERMINED
```

## Evidence status

Evidence status describes what has happened to a claim or observation outside the vote.

Provisional vocabulary:

```text
OPERATOR_SUPPLIED
UNTESTED
SUPPORTED
REPLAY_VERIFIED
CONTESTED
FALSIFIED
FAILED_VERIFICATION
NON_REPRODUCIBLE
```

These terms will be tightened when the executable protocol is implemented.

## Consensus does not certify truth

Examples:

```text
Council: UNANIMOUS ACCEPT
Evidence: UNTESTED
Meaning: every member agrees, but the claim has not been tested.
```

```text
Council: STRONG CONSENSUS TEST_FURTHER
Evidence: REPLAY_VERIFIED observation
Meaning: the observation reproduces; its interpretation remains unsettled.
```

```text
Council: UNANIMOUS ACCEPT
Evidence: FAILED_VERIFICATION
Meaning: the Council was collectively wrong under the declared test.
```

NEXUS must display both axes rather than collapsing them into a single confidence score.

## Observation versus interpretation

This boundary is constitutional.

Example:

```text
Observation:
A frozen sonification recipe produced ~431 Hz from a supplied dataset.

Interpretation:
432 Hz is a privileged universal physical frequency.
```

Replay of the first claim does not establish the second.

## Model output boundary

A model response is not evidence merely because:

- the model is large;
- the model is commercial;
- the model is open;
- the provider is famous;
- several models repeat the same statement;
- the prose sounds confident;
- the Council votes for it.

Model outputs may become useful hypotheses, critiques, syntheses, experiment proposals, or interpretations.

## Instrument boundary

A NEXUS instrument verifies only what its contract says it verifies.

A replay receipt may establish that a computation reproduced under its declared inputs and runtime constraints. It does not automatically establish physical truth, causal interpretation, originality, safety, or scientific consensus.

## Sonification and visualization

Sonification and visualization are representations/observation mappings unless an explicit domain contract establishes something stronger.

They may:

- expose patterns;
- support comparison;
- aid accessibility;
- suggest hypotheses;
- produce creative artifacts.

They do not gain evidentiary force merely by being perceptually compelling.

## Minority reports

A minority objection remains part of the evidence/history graph. It should not be rewritten as an error merely because it lost a vote.

Later experiments may support either the majority or minority branch.

## Equality boundary

Open versus closed status is descriptive metadata only. It cannot be used as a scientific claim, confidence multiplier, or vote weight.

See [`GUARD.md`](GUARD.md).
