# Assumptions and Non-Claims

The formal project is intentionally narrower than a claim that NEXUS produces truth or intelligence.

## Explicit scope

The Lean model does **not** assume:

- that AGI exists;
- that any participant is generally intelligent;
- that model outputs are correct;
- that Council consensus is truth;
- that provider, model identity, parameter count, popularity, or price grants authority;
- that Six Hats empirically improves answer quality.

`Nexus.Assumptions` contains machine-checkable scope markers showing that AGI, consensus-as-truth, and identity-as-authority are not premises of the abstract protocol model.

## What the proofs mean

A theorem such as `one_member_one_vote` means:

> Given the formal NEXUS definitions in this project, every represented participant has vote weight 1.

A theorem such as `consensus_does_not_promote_evidence` means:

> In the formal transition model, a Council outcome by itself leaves evidence state unchanged.

These are protocol properties. They are not empirical claims about answer quality.

## What requires testing rather than theorem proving

Claims such as these remain empirical/scientific questions:

- whether Six Hats improves model reasoning;
- whether a heterogeneous Council improves accuracy;
- whether particular model combinations are useful;
- whether NEXUS produces better decisions than a baseline;
- whether any model or system should be described as generally intelligent.

The intended division of labor is:

```text
formal invariant -> Lean proof
runtime correspondence -> source audit + regression test
behavioral/effectiveness claim -> experiment
```
