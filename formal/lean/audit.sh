#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

REPORT="${1:-formal-verification-report.txt}"
STABLE_RUNTIME_COMMIT="${NEXUS_STABLE_RUNTIME_COMMIT:-unbound}"
STABLE_RUNTIME_TAG_EXPECTED="${NEXUS_STABLE_RUNTIME_TAG:-unbound}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() {
  printf 'formal audit failed: %s\n' "$1" >&2
  exit 1
}

# Proof holes are rejected textually before Lean is invoked. Project source may
# also not introduce bare axiom/constant declarations as substitutes for proofs.
if grep -R -nE '(^|[^[:alnum:]_])(sorry|admit)([^[:alnum:]_]|$)' Nexus --include='*.lean'; then
  fail 'proof hole token found'
fi
if grep -R -nE '^[[:space:]]*(axiom|constant)[[:space:]]' Nexus --include='*.lean'; then
  fail 'project-defined axiom or constant declaration found'
fi

ACTUAL="$TMP/actual.tsv"
EXPECTED="$TMP/expected.tsv"
: > "$ACTUAL"

for file in Nexus/*.lean; do
  module="Nexus.$(basename "$file" .lean)"
  sed -nE "s/^[[:space:]]*(theorem|lemma)[[:space:]]+([A-Za-z0-9_']+).*/\\1\t${module}\t\\2/p" "$file" >> "$ACTUAL"
done
sort -o "$ACTUAL" "$ACTUAL"

awk -F '\t' '
  NR > 1 && ($1 == "A" || $1 == "A/R") && ($2 == "theorem" || $2 == "lemma") {
    print $2 "\t" $3 "\t" $4
  }
' AUDIT_MANIFEST.tsv | sort > "$EXPECTED"

if ! diff -u "$EXPECTED" "$ACTUAL"; then
  fail 'AUDIT_MANIFEST.tsv does not exactly match Lean theorem/lemma declarations'
fi

THEOREMS="$(awk -F '\t' '$1 == "theorem" { n += 1 } END { print n + 0 }' "$ACTUAL")"
LEMMAS="$(awk -F '\t' '$1 == "lemma" { n += 1 } END { print n + 0 }' "$ACTUAL")"

BUILD_LOG="$TMP/lake-build.log"
MAIN_LOG="$TMP/main.log"
AXIOM_LOG="$TMP/axioms.log"

if ! lake build >"$BUILD_LOG" 2>&1; then
  cat "$BUILD_LOG" >&2
  fail 'lake build failed'
fi

if ! lake env lean Nexus/Main.lean >"$MAIN_LOG" 2>&1; then
  cat "$MAIN_LOG" >&2
  fail 'aggregate theorem module failed to compile'
fi

if ! lake env lean Nexus/AxiomAudit.lean >"$AXIOM_LOG" 2>&1; then
  cat "$AXIOM_LOG" >&2
  fail 'axiom dependency audit failed to compile'
fi

if grep -q 'sorryAx' "$AXIOM_LOG"; then
  cat "$AXIOM_LOG" >&2
  fail 'sorryAx dependency detected'
fi

# For this compact constitutional layer, only Lean's standard logical axioms
# are admitted as imported dependencies. Empty dependency sets are expected for
# many definitional theorems.
UNEXPECTED="$TMP/unexpected-axioms.txt"
sed -nE 's/.*depends on axioms: \[(.*)\].*/\1/p' "$AXIOM_LOG" \
  | tr ',' '\n' \
  | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' \
  | grep -vE '^(|propext|Classical\.choice|Quot\.sound)$' \
  | sort -u > "$UNEXPECTED" || true

if [[ -s "$UNEXPECTED" ]]; then
  cat "$AXIOM_LOG" >&2
  printf 'unexpected imported axiom dependencies:\n' >&2
  cat "$UNEXPECTED" >&2
  fail 'axiom allowlist exceeded'
fi

COMMIT="unbound-archive"
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  COMMIT="$(git rev-parse HEAD)"
fi

{
  printf 'NEXUS FORMAL VERIFICATION REPORT\n'
  printf '================================\n'
  printf 'formalization_commit: %s\n' "$COMMIT"
  printf 'stable_runtime_commit_expected: %s\n' "$STABLE_RUNTIME_COMMIT"
  printf 'stable_runtime_tag_expected: %s\n' "$STABLE_RUNTIME_TAG_EXPECTED"
  printf 'toolchain: %s\n' "$(cat lean-toolchain)"
  printf 'lean: %s\n' "$(lean --version | head -n 1)"
  printf 'lake: %s\n' "$(lake --version | head -n 1)"
  printf 'theorems: %s\n' "$THEOREMS"
  printf 'lemmas: %s\n' "$LEMMAS"
  printf 'manifest_sync: PASS\n'
  printf 'proof_holes: 0\n'
  printf 'project_defined_axiom_or_constant_declarations: 0\n'
  printf 'lake_build: PASS\n'
  printf 'aggregate_module: PASS\n'
  printf 'axiom_dependency_audit: PASS\n'
  printf '\nAXIOM DEPENDENCY OUTPUT\n'
  printf '%s\n' '-----------------------'
  cat "$AXIOM_LOG"
} > "$REPORT"

cat "$REPORT"
