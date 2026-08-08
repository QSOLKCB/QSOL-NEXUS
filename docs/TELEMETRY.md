# Council Information Telemetry

NEXUS 2.0-alpha6 adds deterministic observation channels for how a Council converges or diverges.

> **Telemetry observes the Council. It does not govern the Council.**

Telemetry never changes vote weight, consensus thresholds, evidence state, verification state, or the Equality Guard.

## Implemented metrics

### Ballot Shannon entropy

For sealed ballot categories with probabilities `p_i`:

```text
H = -sum(p_i * log2(p_i))
```

A unanimous ballot has `H = 0` bits. Three equally represented ballot categories have `H = log2(3) ~= 1.585` bits.

This is Shannon entropy because the random variable is explicit: the categorical distribution of sealed ballot choices.

### Per-hat exact-response entropy

For each White/Red/Black/Yellow/Green/Blue phase, responses are normalized by Unicode NFKC, case-folding, and whitespace collapse, then grouped by exact SHA-256 fingerprint. Shannon entropy is computed over those exact categories.

This is **not semantic entropy**. Paraphrases may fall into different exact categories even when they mean nearly the same thing.

### Per-hat lexical divergence

NEXUS also records mean pairwise Jaccard distance over normalized token sets. This gives a deterministic near-overlap signal in `[0, 1]` without mislabelling it Shannon entropy.

It is not a truth score, quality score, confidence score, or authority score.

### Minority snapshot

The ballot telemetry records the number and fraction of current minority reports. Longitudinal *minority-branch persistence* across sessions remains deferred until persistent-world lineage semantics are mature enough to define it precisely.

## Reproducibility

Telemetry is stored inside the content-addressed `council_session` payload and is derived entirely from captured phase submissions, revealed ballots, and the Council result.

The additive JSONL operation:

```text
telemetry.verify
```

recomputes the telemetry from the stored Council artifact and checks that it matches the captured telemetry block.

## Claim boundaries

High entropy is not automatically good. Low entropy is not automatically truth. Diversity can reflect useful independent hypotheses, noise, ambiguity, prompt sensitivity, or model failure. Convergence can reflect genuine constraint, shared priors, common training data, anchoring, or a trivial question.

No telemetry field is permitted to affect `vote_weight = 1` or any other Council authority mechanism.

## Deferred metrics

Alpha6 deliberately defers metrics that need stronger measurement rules:

- semantic response entropy;
- hypothesis branching multiplicity;
- controlled perturbation recovery;
- loop/repeated-motif indicators;
- mode-transition cost;
- minority-branch persistence across sessions;
- geometric labels such as `bottlenecked` or `shattered`.

Those names will not enter runtime state until NEXUS has an explicit operational definition for them.
