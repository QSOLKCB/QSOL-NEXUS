# Notion research dashboard: privacy and export contract

## Separation of authority

NEXUS WorldStore is the canonical immutable history. SQLite may index it locally. Notion is an editable research / editorial projection, not a Council command channel, source of governance authority, or substitute for receipts. GitHub Pages is a static, read-only publication.

This phase adds a dashboard at docs/research.html. There is no live API connection between the browser and Notion, NEXUS, or CONTROL. The existing Render read-only edge is unchanged.

## Notion staging

The companion private database has these exact properties:
- Name (title), System (select), Record Type (select), Status (select)
- Visibility (select: INTERNAL/PUBLIC), Publish Approved (checkbox)
- Source Ref (rich text), Source Commit (rich text), Source URL (URL)
- Summary (rich text), Last Verified (date)

The publication exporter only includes a row if Visibility is PUBLIC and Publish Approved is true. Both requirements are checked in the server-side Notion query and again in local Python, but they are editorial controls, not authorization for someone to read the full Notion database. Keep the Notion database private.

A public row must also have a bounded summary, an allowlisted QSOL system, an exact source ref or 40-character SHA-1 commit hash, and a source URL under the QSOLKCB GitHub organization. An invalid approved record rejects the whole export.

Do not place secrets, private research, personal records, provider credentials, or model private reasoning in a public Summary. The exporter never emits user IDs, Notion page IDs, tokens, internal record bodies, or arbitrary Notion fields. Approved entries still require review of the generated diff.

## Local operator procedure

The connected ChatGPT Notion plugin does not grant the repository a reusable Notion API token. Create a separate Notion API integration with read-only access to this database, share the database with that integration, and keep its token in an owner-only secret store, outside Git.

The exporter uses only Python's standard library, Notion API version 2025-09-03 and POST /v1/data_sources/{id}/query. Supply environment variables NOTION_TOKEN and NOTION_DATA_SOURCE_ID from a trusted local process. Do not copy the token into this repository, GitHub Pages, or a command argument.

From the repository root, execute:

    uv run --no-project python -I -B tools/notion_public_export.py --dry-run

After verifying the candidate publication rows, generate the file:

    uv run --no-project python -I -B tools/notion_public_export.py

Review the diff of docs/research-data.js and commit it only after publication approval. This operation is manual, not an automatic release or a background Notion synchronization.

For offline test fixtures, use --input-json PATH. The fixture must contain a Notion query response object with a results array. All public-row guards remain active in offline mode.

## Dashboard contents

- docs/research.html: static research dashboard, search, system/status filtering, source links and absence state
- docs/research.js: DOM text-only rendering; no fetch, WebSocket, eval, or local storage
- docs/research.css: layout using the existing portal design tokens
- docs/research-data.js: reviewed snapshot, initially empty
- tools/notion_public_export.py: allowlisted local-only API reader and deterministic static generator
- web_tests/test_research_dashboard.py: security, determinism and fail-closed regression tests

Both public HTML pages retain connect-src 'none'. The exporter fingerprints sorted approved records with SHA-256. The digest detects byte changes; it does not prove scientific truth or semantic validity.

To validate without an API key or internet:

    python3 -B -m unittest discover -s web_tests -p 'test_*.py' -v

## Deferred work

Live Council operations, private authenticated read access, Notion write-back, real-time status, and SQLite runtime indexes are separate engineering/review phases. Do not widen the existing public gateway or Pages CSP while delivering this dashboard.

PUBLIC_SNAPSHOT != LIVE_COUNCIL
NOTION_RECORD != WORLDSTORE_AUTHORITY
EDITORIAL_APPROVAL != SCIENTIFIC_VERIFICATION
SOURCE_SHA != SEMANTIC_TRUTH
