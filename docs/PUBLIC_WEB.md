# Public web deployment — architecture and release gate

## Scope

The \`docs/index.html\` GitHub Pages entry point is a **public, static, read-only observatory**, not a live NEXUS, FED, CONTROL, or ORACLE instance. The companion JavaScript creates only an in-browser, deterministic LATTICE address traversal. It performs no network fetches, credential storage, model inference, remote health polling, or write operations.

The eight source links are **repository references**, not discovered peers, running service health assertions, or endorsements of semantic truth.

## GitHub Pages configuration

Preferred, simplest deployment (no build system or package manager):

1. Review, test and merge the portal PR under the existing repository approval policy.
2. Repository **Settings → Pages → Build and deployment → Deploy from a branch**.
3. Select **main** and **/docs**, then save.
4. Inspect \`https://qsolkcb.github.io/QSOL-NEXUS/\` and the Pages deployment workflow result.

The repository root \`index.html\` is only a redirect for deployments configured to publish \`main / (root)\`, so that configuration also reaches the portal. If Pages is configured for GitHub Actions, switch to the branch source above; this PR intentionally adds no additional GitHub Actions deployment workflow.

Source assets: \`docs/index.html\`, \`docs/portal.css\`, \`docs/portal.js\`.
No Node.js, Docker, frontend framework, external stylesheet, remote script, API key or Render resource is needed.

## Verified LATTICE subset

The interactive viewer uses the published \`qsol-3x3x3-sierpinski-derived-memory/1\` top-level mapping. Its canonical lexicographic cell order is nested \`x\`, then \`y\`, then \`z\`; index \`9*x + 3*y + z\`. The optional phi traversal uses \`(step * 17) mod 27\`. Since \`gcd(17,27) == 1\`, each top-level cell is visited exactly once. The viewer does not implement recursive addressing, cross-language fingerprint generation, or a certified conformance claim.

Canonical implementation: \`QSOLKCB/LATTICE\`, \`lattice/core.py\`.

## Internet-facing runtime gate — NOT SATISFIED

- NEXUS 2.x is a **Python JSONL/stdio** control plane and Rust local operator shell, not an authenticated HTTP public service.
- CONTROL's WebUI is **loopback-only**, with explicitly deferred multi-user authentication and remote deployment.
- ORACLE's FED transport is a **local stdio** reference boundary.
- FED's published claim boundary does **not** establish deployed production networking.

Do not put a public reverse proxy in front of those services or make unrestricted JSONL operations available from this portal.

Before any future interactive cloud upgrade, separately implement/review: explicit public operation allowlist; strong operator authentication; per-record authorization and classification; CSRF/CORS/Origin policy; input/output bounds and rate limits; secret isolation; persistent-store retention/backup; request audit; canonical receipt provenance; and adversarial regression proving that remote requests cannot bypass Council, witness, federation or recovery governance.

No code in this PR configures or triggers a Render deploy, manipulates the existing game service or changes persistent storage. Render instance retirement is a separate operation, with disk preservation/export considered before deletion.

## Local validation

From repository root:

\`\`\`sh
python3 -m unittest discover -s web_tests -p 'test_public_web.py' -v
\`\`\`

Optional manual browser smoke test: open \`docs/index.html\`, filter eight cards, switch traversals, click cell \`L[2,0,1]\`, and verify the coordinate roles. Repeat on a mobile viewport and without external network access.

## Claim boundary

\`\`\`text
PUBLIC_PAGE != LIVE_NEXUS
MODULE_LIST != LIVE_FEDERATION
LATTICE_ADDRESS != EVIDENCE
DETERMINISTIC_DEMO != RUNTIME_CONFORMANCE
RENDER_DEPLOY != RELEASE_AUTHORITY
\`\`\`
