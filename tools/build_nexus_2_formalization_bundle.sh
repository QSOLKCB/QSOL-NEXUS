#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
META_REL="publication/nexus-2.0-formalization"
PUBLICATION_COMMIT="${NEXUS_PUBLICATION_COMMIT:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
OUT_DIR="${1:-$REPO_ROOT/publication/dist}"

fail() {
  printf 'publication bundle failed: %s\n' "$1" >&2
  exit 1
}

for cmd in git tar gzip sha256sum sed diff find sort xargs cp mktemp; do
  command -v "$cmd" >/dev/null 2>&1 || fail "required command not found: $cmd"
done
command -v lean >/dev/null 2>&1 || fail 'Lean is not installed on PATH'
command -v lake >/dev/null 2>&1 || fail 'Lake is not installed on PATH'

cd "$REPO_ROOT"
git cat-file -e "${PUBLICATION_COMMIT}^{commit}" || fail 'publication commit is unavailable'

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Bind every publication metadata/input file to the recorded publication commit,
# never to a potentially dirty working tree. A local build with uncommitted
# metadata therefore packages the committed bytes named by PUBLICATION_COMMIT.
COMMITTED_META_ROOT="$TMP/publication-commit"
mkdir -p "$COMMITTED_META_ROOT"
git archive "$PUBLICATION_COMMIT" "$META_REL" | tar -xf - -C "$COMMITTED_META_ROOT"
META_DIR="$COMMITTED_META_ROOT/$META_REL"
# shellcheck disable=SC1091
source "$META_DIR/IDENTITY.env"

git cat-file -e "${NEXUS_STABLE_COMMIT}^{commit}" || fail 'stable commit is unavailable'
git cat-file -e "${PR52_REVIEWED_HEAD}^{commit}" || fail 'PR #52 reviewed head is unavailable'
git cat-file -e "${PR53_REVIEWED_HEAD}^{commit}" || fail 'PR #53 reviewed head is unavailable'
git cat-file -e "${PR53_MERGE_COMMIT}^{commit}" || fail 'PR #53 merge commit is unavailable'

if ! git show-ref --verify --quiet "refs/tags/${NEXUS_STABLE_TAG}"; then
  fail "required stable tag ${NEXUS_STABLE_TAG} is unavailable"
fi
TAG_COMMIT="$(git rev-list -n 1 "$NEXUS_STABLE_TAG")"
[[ "$TAG_COMMIT" == "$NEXUS_STABLE_COMMIT" ]] || \
  fail "${NEXUS_STABLE_TAG} resolves to ${TAG_COMMIT}, expected ${NEXUS_STABLE_COMMIT}"

# The stable release commit must be the actual merge of the reviewed PR #52
# head, not merely a descendant with a plausible-looking SHA in metadata.
STABLE_PARENTS=" $(git show -s --format=%P "$NEXUS_STABLE_COMMIT") "
[[ "$STABLE_PARENTS" == *" ${PR52_REVIEWED_HEAD} "* ]] || \
  fail 'stable runtime commit does not contain the reviewed PR #52 head as a direct parent'

PARENTS=" $(git show -s --format=%P "$PR53_MERGE_COMMIT") "
[[ "$PARENTS" == *" ${NEXUS_STABLE_COMMIT} "* ]] || \
  fail 'PR #53 merge commit does not contain the stable runtime parent'
[[ "$PARENTS" == *" ${PR53_REVIEWED_HEAD} "* ]] || \
  fail 'PR #53 merge commit does not contain the reviewed formalization parent'

# The reviewed formalization must reach main without any Lean-source mutation.
git diff --quiet "$PR53_REVIEWED_HEAD" "$PR53_MERGE_COMMIT" -- formal/lean \
  || fail 'merged PR #53 Lean files differ from the reviewed head'
# PR #54 is packaging only; theorem/proof files remain frozen.
git diff --quiet "$PR53_REVIEWED_HEAD" "$PUBLICATION_COMMIT" -- formal/lean \
  || fail 'PR #54 modified formal/lean; publication must package the reviewed PR #53 source unchanged'

[[ "$(git show "${PR53_REVIEWED_HEAD}:formal/lean/lean-toolchain")" == "leanprover/lean4:v${LEAN_VERSION}" ]] \
  || fail 'reviewed Lean toolchain does not match publication identity'

PKG="$TMP/$BUNDLE_NAME"
mkdir -p "$PKG/SOFTWARE" "$PKG/LEAN4" "$PKG/VALIDATION" "$OUT_DIR"

# Extract the reviewed Lean source directly from the immutable PR #53 head.
mkdir -p "$TMP/reviewed"
git archive "$PR53_REVIEWED_HEAD" formal/lean | tar -xf - -C "$TMP/reviewed"
cp -a "$TMP/reviewed/formal/lean/." "$PKG/LEAN4/"

# Run Lean on a disposable second copy. This is deliberate: the published
# LEAN4/ directory remains byte-for-byte tracked PR #53 source and never absorbs
# generated .lake build products from the verification run.
mkdir -p "$TMP/audit-copy"
cp -a "$TMP/reviewed/formal/lean/." "$TMP/audit-copy/"

# Archive stable software directly from the exact commit behind v2.0.0.
git archive --format=tar --prefix=QSOL-NEXUS-2.0.0/ "$NEXUS_STABLE_COMMIT" > "$TMP/stable-source.tar"
gzip -n -9 < "$TMP/stable-source.tar" > "$PKG/SOFTWARE/NEXUS-2.0-stable-source.tar.gz"
printf '%s\n' "$NEXUS_STABLE_TAG" > "$PKG/SOFTWARE/RELEASE_TAG.txt"
printf '%s\n' "$NEXUS_STABLE_COMMIT" > "$PKG/SOFTWARE/RELEASE_COMMIT.txt"
printf '%s\n' "$PR53_REVIEWED_HEAD" > "$PKG/SOFTWARE/FORMALIZATION_REVIEWED_HEAD.txt"
printf '%s\n' "$PR53_MERGE_COMMIT" > "$PKG/SOFTWARE/FORMALIZATION_MERGE_COMMIT.txt"

cp "$META_DIR/IDENTITY.env" "$PKG/IDENTITY.env"
cp "$META_DIR/README.md" "$PKG/README.md"
cp "$META_DIR/REPRODUCIBILITY.md" "$PKG/REPRODUCIBILITY.md"
cp "$META_DIR/HANDOFF.md" "$PKG/HANDOFF.md"
cp "$META_DIR/VALIDATION/release-hardening-report.json" "$PKG/VALIDATION/release-hardening-report.json"
cp "$META_DIR/VALIDATION/test-summary.txt" "$PKG/VALIDATION/test-summary.txt"
cp "$META_DIR/VALIDATION/pr53-ci-formal-verification-report.txt" "$PKG/VALIDATION/pr53-ci-formal-verification-report.txt"

sed \
  -e "s|@ZENODO_DOI@|${ZENODO_DOI}|g" \
  -e "s|@ZENODO_PUBLICATION_DATE@|${ZENODO_PUBLICATION_DATE}|g" \
  -e "s|@PUBLICATION_COMMIT@|${PUBLICATION_COMMIT}|g" \
  "$META_DIR/ZENODO_METADATA.md" > "$PKG/ZENODO_METADATA.md"

cat > "$PKG/CHAIN_OF_CUSTODY.json" <<EOF
{
  "schema": "nexus-publication-chain-v1",
  "bundle_name": "${BUNDLE_NAME}",
  "bundle_version": "${BUNDLE_VERSION}",
  "stable_tag": "${NEXUS_STABLE_TAG}",
  "stable_commit": "${NEXUS_STABLE_COMMIT}",
  "pr52_reviewed_head": "${PR52_REVIEWED_HEAD}",
  "pr53_reviewed_head": "${PR53_REVIEWED_HEAD}",
  "pr53_merge_commit": "${PR53_MERGE_COMMIT}",
  "publication_commit": "${PUBLICATION_COMMIT}",
  "lean_version": "${LEAN_VERSION}",
  "lean_linux_sha256": "${LEAN_LINUX_SHA256}",
  "theorems": ${THEOREM_COUNT},
  "lemmas": ${LEMMA_COUNT},
  "zenodo_doi": "${ZENODO_DOI}",
  "zenodo_publication_date": "${ZENODO_PUBLICATION_DATE}"
}
EOF

# Re-run the complete audit from the disposable copy, outside the Git worktree.
pushd "$TMP/audit-copy" >/dev/null
NEXUS_STABLE_RUNTIME_COMMIT="$NEXUS_STABLE_COMMIT" \
NEXUS_STABLE_RUNTIME_TAG="$NEXUS_STABLE_TAG" \
NEXUS_FORMALIZATION_COMMIT="$PR53_REVIEWED_HEAD" \
  bash audit.sh "$PKG/VALIDATION/formal-verification-report.txt"
popd >/dev/null

grep -Fx "formalization_commit: ${PR53_REVIEWED_HEAD}" "$PKG/VALIDATION/formal-verification-report.txt" >/dev/null \
  || fail 'fresh audit did not bind to the reviewed PR #53 head'
grep -Fx "stable_runtime_commit_expected: ${NEXUS_STABLE_COMMIT}" "$PKG/VALIDATION/formal-verification-report.txt" >/dev/null \
  || fail 'fresh audit stable runtime identity mismatch'
grep -Fx "theorems: ${THEOREM_COUNT}" "$PKG/VALIDATION/formal-verification-report.txt" >/dev/null \
  || fail 'fresh audit theorem count mismatch'
grep -Fx "lemmas: ${LEMMA_COUNT}" "$PKG/VALIDATION/formal-verification-report.txt" >/dev/null \
  || fail 'fresh audit lemma count mismatch'

# A standalone extracted copy has no Git checkout identity. Everything else must
# reproduce the final reviewed PR #53 CI report byte-for-byte.
sed '/^verification_checkout_commit:/d' "$PKG/VALIDATION/pr53-ci-formal-verification-report.txt" > "$TMP/ci-normalized.txt"
sed '/^verification_checkout_commit:/d' "$PKG/VALIDATION/formal-verification-report.txt" > "$TMP/fresh-normalized.txt"
diff -u "$TMP/ci-normalized.txt" "$TMP/fresh-normalized.txt" \
  || fail 'fresh archived Lean audit differs from final PR #53 CI evidence'

# Prove the published Lean tree still equals the immutable reviewed source after
# the verification run. In particular, generated .lake products must be absent.
diff -qr "$TMP/reviewed/formal/lean" "$PKG/LEAN4" >/dev/null \
  || fail 'published LEAN4 directory drifted from the reviewed PR #53 source'
[[ ! -e "$PKG/LEAN4/.lake" ]] || fail 'generated .lake directory leaked into publication source'

# Hash every payload file except the checksum inventory itself.
(
  cd "$PKG"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)

SOURCE_DATE_EPOCH="$(git show -s --format=%ct "$PR53_MERGE_COMMIT")"
ARCHIVE="$OUT_DIR/${BUNDLE_NAME}.tar.gz"
TARFILE="$TMP/${BUNDLE_NAME}.tar"

# Normalize archive permissions as well as names, ownership and timestamps.
# This makes the tarball byte-identical across caller umasks such as 022/077
# while preserving executable bits from Git-tracked executable source files.
tar --sort=name \
  --format=posix \
  --pax-option=delete=atime,delete=ctime \
  --mtime="@${SOURCE_DATE_EPOCH}" \
  --owner=0 --group=0 --numeric-owner \
  --mode='u+rwX,go+rX,go-w,a-s' \
  -cf "$TARFILE" -C "$TMP" "$BUNDLE_NAME"
gzip -n -9 < "$TARFILE" > "$ARCHIVE"
(
  cd "$OUT_DIR"
  sha256sum "${BUNDLE_NAME}.tar.gz" > "${BUNDLE_NAME}.tar.gz.sha256"
  sha256sum -c "${BUNDLE_NAME}.tar.gz.sha256"
)

printf 'publication bundle: %s\n' "$ARCHIVE"
printf 'archive checksum: %s\n' "$OUT_DIR/${BUNDLE_NAME}.tar.gz.sha256"
