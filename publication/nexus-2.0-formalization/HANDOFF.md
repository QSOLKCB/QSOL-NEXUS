# Independent Recipient Handoff

This is the short path for a recipient who wants to verify the package rather than read the entire repository history.

## Verify the archive

```bash
sha256sum -c NEXUS-2.0-FORMALIZATION.tar.gz.sha256
tar -xzf NEXUS-2.0-FORMALIZATION.tar.gz
cd NEXUS-2.0-FORMALIZATION
sha256sum -c SHA256SUMS
```

## Verify the formal layer

Install Lean 4.33.0, then:

```bash
cd LEAN4
lake build
bash audit.sh
```

Expected headline result:

```text
24 theorems
0 lemmas
0 proof holes
manifest_sync: PASS
axiom_query_manifest_sync: PASS
axiom_dependency_audit: PASS
```

## Verify what those proofs are tied to

Read:

```text
../CHAIN_OF_CUSTODY.json
RUNTIME_CORRESPONDENCE.md
FORMAL_GAP_RANKING.md
ASSUMPTIONS_AND_NONCLAIMS.md
```

The stable software being described is exactly:

```text
v2.0.0 -> cc6b4ffee26760e8d7c3bc88a2fcb877559e5d6a
```

The reviewed Lean formalization is exactly:

```text
247a1f97834cfac5221e5045dda21551c28907a8
```

and it entered `main` through merge commit:

```text
faaff21fa926aa10bccc9d6cd66452ba1e2b065d
```

That is the complete trust boundary: inspect the source, verify the hashes, run Lean, and check the documented runtime correspondence. No screenshot or authority claim is required.
