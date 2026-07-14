# Security and Privacy

QSOL NEXUS is designed for direct local execution. It has no production network client and does not transmit source data, results, audio, history, or telemetry.

## Content Security Policy

Both application and test pages use a restrictive policy based on:

```text
default-src 'self' blob: data:;
connect-src 'none';
img-src 'self' blob: data:;
media-src 'self' blob: data:;
script-src 'self';
style-src 'self';
object-src 'none';
frame-src 'none';
base-uri 'none';
form-action 'none';
```

`file://` origin behaviour differs between browsers. If a browser refuses a local capability such as IndexedDB, NEXUS fails visibly to session-only storage rather than weakening the CSP or creating a remote dependency.

## Allowed capabilities

- local File, Blob, ArrayBuffer, typed-array and object-URL APIs;
- Canvas 2D for non-identity-bearing visualization;
- IndexedDB for completed local experiments, with explicit in-memory fallback;
- native audio playback of already generated WAV bytes;
- user-initiated downloads;
- user-initiated clipboard writes for copy buttons, when permitted.

## Prohibited production features

- `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, or `sendBeacon`;
- remote fonts, scripts, styles, images, audio, analytics, or telemetry;
- service workers or background synchronization;
- hidden clipboard reads;
- `eval`, `new Function`, arbitrary code execution, or dynamic script injection;
- HTML execution from imported data;
- remote model or plugin loading.

Source text and imported metadata are rendered with text nodes or escaped JSON, never inserted as executable markup.

## Threat model

NEXUS protects experiment identity against accidental mutation and ordinary artifact tampering. Replay recomputes source, recipe, result, observation, audio, contract, manifest, and required runtime identities. It is not a digital-signature system and does not protect against a hostile party who can replace both the application code and every artifact. Sign or archive release files separately when an authenticated publisher identity is required.

ZIP import is bounded by entry count and size and rejects traversal paths, duplicate names, unsupported compression, and malformed records. CSV and JSON input is size-bounded by the UI/runtime. Numeric parsers reject non-finite values and invalid units.

## Static release audit

From the directory containing `QSOL-NEXUS`:

```bash
rg -n --pcre2 -g '*.js' -g '*.html' \
  '\bfetch\s*\(|new\s+XMLHttpRequest|new\s+WebSocket|EventSource\s*\(|sendBeacon\s*\(' \
  QSOL-NEXUS

rg -n --pcre2 -g '*.html' -g '*.css' \
  '(?i)(src|href)\s*=\s*["'"'](?:https?:)?//' \
  QSOL-NEXUS

rg -n --pcre2 -g '*.js' '\beval\s*\(|new\s+Function\s*\(' QSOL-NEXUS

find QSOL-NEXUS -type f \
  \( -name package.json -o -name package-lock.json -o -name yarn.lock -o -name pnpm-lock.yaml \)
```

Expected result: no production network client, no remote asset, no dynamic code evaluator, and no package-manager file. Documentation may contain ordinary repository links; exclude Markdown when auditing executable resources.

## Reporting

Do not attach private source datasets or experiment bundles to a public issue. Report the minimum reproducible description, affected NEXUS version, browser/runtime fingerprint when relevant, and a synthetic fixture if possible.
