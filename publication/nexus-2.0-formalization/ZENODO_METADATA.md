# Zenodo Metadata — Ready-to-Paste Draft

## Title

**QSOL NEXUS 2.0 Formalization and Reproducibility Package: Lean 4 Verification of Selected Constitutional and Protocol Invariants**

## Resource type

Software

## Version

`2.0.0-formalization.1`

## Publication date

`@ZENODO_PUBLICATION_DATE@`

## Creator

**Trent Slade**  
ORCID: `0009-0002-4515-9237`

## License

Apache License 2.0

## Reserved DOI

`@ZENODO_DOI@`

## Description

This archival package accompanies QSOL NEXUS 2.0, a model-independent cognitive substrate and persistent shared computational world with an equal-vote multi-model AI Council. The package freezes the exact stable NEXUS 2.0 software identity and the separately reviewed Lean 4 formalization produced in PR #53.

The formal layer contains 24 advertised theorems and 0 lemmas covering selected constitutional and protocol invariants, including one-member-one-vote, provider/model-size/model-identity independence of vote weight, same-seat replacement, closed Six Hats sequencing, sealed-phase immutability, exact two-thirds consensus arithmetic, consensus/evidence separation, citizenship and civic-proxy non-expansion of vote weight, and non-creation of authority through progression, culture, redundancy, or compute-epoch capability growth.

The formalization is machine-checked with Lean 4.33.0. The publication audit rejects proof holes and project-defined axiom/constant substitutes, verifies exact synchronization between the theorem manifest and the `#print axioms` audit surface, and records imported axiom dependencies. On the reviewed 24-theorem surface, 19 theorems have no axiom dependencies and 5 depend only on Lean's standard `propext`; there are 0 proof holes and 0 NEXUS-defined axioms.

The package includes the stable software source archive, byte-for-byte reviewed Lean source, runtime correspondence documentation, formal gap/non-claim records, release-hardening evidence, final PR #53 CI verification evidence, a freshly regenerated standalone formal audit, reproducibility instructions, chain-of-custody metadata, and SHA-256 checksums.

The intended claim is deliberately narrow: selected constitutional and protocol invariants of NEXUS 2.0 have been formalized and machine-checked in Lean 4 with explicit correspondence to the tested stable runtime. The package does not claim that NEXUS creates AGI, that Council consensus is truth, that Six Hats necessarily improves model quality, or that every property of the complete Python/Rust implementation has been formally verified.

## Keywords

- Lean 4
- formal verification
- reproducible research
- artificial intelligence
- multi-model systems
- multi-agent systems
- AI governance
- model interoperability
- consensus protocols
- software verification
- human-AI collaboration
- provenance

## Related identifiers

- Repository: `https://github.com/QSOLKCB/QSOL-NEXUS`
- Stable release: `https://github.com/QSOLKCB/QSOL-NEXUS/releases/tag/v2.0.0`
- Formal verification PR: `https://github.com/QSOLKCB/QSOL-NEXUS/pull/53`
- Publication PR commit: `@PUBLICATION_COMMIT@`

## Frozen source identities

```text
stable tag:              v2.0.0
stable runtime commit:   cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
PR #53 reviewed head:    247a1f97834cfac5221e5045dda21551c28907a8
PR #53 merged commit:    faaff21fa926aa10bccc9d6cd66452ba1e2b065d
Lean:                    4.33.0
Lean Linux SHA-256:      4b3fb03c29a1e0a253fb1d11f9bae3725f19a0dc6fc09b3ea16d2c9df3349e2c
```
