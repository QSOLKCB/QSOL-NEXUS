#!/usr/bin/env python3
"""Publish only explicitly approved Notion research rows as a static JS snapshot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VERSION = "2025-09-03"
SCHEMA = "qsol-nexus-public-observatory/1"
SYSTEMS = frozenset({
    "QSOL-SUBSTRATE", "QSOL-ARK", "QSOL-INT", "QSOL-ORACLE",
    "QSOL-NEXUS", "QSOL-FED", "LATTICE", "QSOL-CONTROL",
})
TYPES = frozenset({"Council", "Experiment", "Hypothesis", "Release", "Integration", "Evidence"})
STATUSES = frozenset({"Proposed", "Running", "Completed", "Challenged", "Rejected", "Unresolved"})
COMMIT = re.compile(r"^(?:[0-9a-f]{40})?$")
REF = re.compile(r"^[A-Za-z0-9._:-]{1,180}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BYTES = 1048576
MAX_PAGES = 10
MAX_RECORDS = 200


class ExportError(ValueError):
    pass


def field(props: dict, name: str, kind: str):
    value = props.get(name)
    if not isinstance(value, dict) or value.get("type") != kind:
        raise ExportError("missing or unexpected property: " + name)
    return value.get(kind)


def selection(props: dict, name: str) -> str:
    value = field(props, name, "select")
    return value.get("name", "") if isinstance(value, dict) else ""


def text(props: dict, name: str, kind: str, maximum: int) -> str:
    value = field(props, name, kind)
    if not isinstance(value, list) or any(
        not isinstance(p, dict) or not isinstance(p.get("plain_text"), str) for p in value
    ):
        raise ExportError("invalid Notion text field: " + name)
    result = "".join(part["plain_text"] for part in value).strip()
    if len(result) > maximum:
        raise ExportError("field too long: " + name)
    return result


def source_url(props: dict) -> str:
    value = field(props, "Source URL", "url")
    if not isinstance(value, str) or len(value) > 500:
        raise ExportError("source URL missing or too long")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or
        not parsed.path.startswith("/QSOLKCB/") or
        not re.fullmatch(r"/QSOLKCB/[A-Za-z0-9._/-]+", parsed.path) or
        parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ExportError("unapproved public source URL")
    return value


def verify_date(props: dict) -> str:
    value = field(props, "Last Verified", "date")
    if value is None:
        return ""
    if not isinstance(value, dict) or not isinstance(value.get("start"), str):
        raise ExportError("invalid Last Verified")
    result = value["start"][:10]
    if not DATE.fullmatch(result):
        raise ExportError("invalid Last Verified date")
    return result


def project(page: dict) -> dict | None:
    if not isinstance(page, dict):
        raise ExportError("invalid page")
    if page.get("archived") or page.get("in_trash"):
        return None
    props = page.get("properties")
    if not isinstance(props, dict):
        raise ExportError("missing page properties")
    # Do not trust the remote filter or any Notion view as an authorization gate.
    if selection(props, "Visibility") != "PUBLIC":
        return None
    if field(props, "Publish Approved", "checkbox") is not True:
        return None
    name = text(props, "Name", "title", 180)
    system = selection(props, "System")
    record_type = selection(props, "Record Type")
    status = selection(props, "Status")
    summary = text(props, "Summary", "rich_text", 360)
    source_ref = text(props, "Source Ref", "rich_text", 180)
    source_commit = text(props, "Source Commit", "rich_text", 40)
    if (not name or not summary or system not in SYSTEMS or
        record_type not in TYPES or status not in STATUSES):
        raise ExportError("approved record has incomplete fields")
    if not COMMIT.fullmatch(source_commit) or (source_ref and not REF.fullmatch(source_ref)):
        raise ExportError("invalid source identity")
    if not source_ref and not source_commit:
        raise ExportError("approved record needs a source reference or commit")
    return {
        "name": name, "system": system, "record_type": record_type,
        "status": status, "summary": summary, "source_ref": source_ref,
        "source_commit": source_commit, "source_url": source_url(props),
        "last_verified": verify_date(props),
    }


def make_snapshot(pages: list) -> dict:
    if len(pages) > MAX_PAGES * 100:
        raise ExportError("too many candidate pages")
    records = [record for page in pages if (record := project(page)) is not None]
    if len(records) > MAX_RECORDS:
        raise ExportError("too many public records")
    records.sort(key=lambda x: (x["source_url"], x["name"], x["source_ref"]))
    keys = [(x["source_url"], x["name"], x["source_ref"]) for x in records]
    if len(keys) != len(set(keys)):
        raise ExportError("duplicate public record identity")
    canonical = json.dumps(records, sort_keys=True, ensure_ascii=True,
                           separators=(",", ":"), allow_nan=False).encode("ascii")
    return {"schema": SCHEMA,
            "digest": "sha256:" + hashlib.sha256(canonical).hexdigest(),
            "records": records}


def query_notion(token: str, data_source_id: str) -> list:
    if not token:
        raise ExportError("NOTION_TOKEN is not set")
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", data_source_id):
        raise ExportError("NOTION_DATA_SOURCE_ID invalid or missing")
    endpoint = "https://api.notion.com/v1/data_sources/" + data_source_id + "/query"
    pages, cursor, seen = [], None, set()
    for _ in range(MAX_PAGES):
        payload = {
            "page_size": 100,
            "filter": {"and": [
                {"property": "Visibility", "select": {"equals": "PUBLIC"}},
                {"property": "Publish Approved", "checkbox": {"equals": True}},
            ]},
        }
        if cursor:
            payload["start_cursor"] = cursor
        req = Request(endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Authorization": "Bearer " + token,
                     "Notion-Version": VERSION, "Content-Type": "application/json"},
            method="POST")
        try:
            with urlopen(req, timeout=15) as response:
                raw = response.read(MAX_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            code = getattr(exc, "code", None)
            raise ExportError("Notion query failed" + (": HTTP " + str(code) if code else "")) from None
        if len(raw) > MAX_BYTES:
            raise ExportError("Notion response too large")
        try:
            result = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        except (ValueError, UnicodeDecodeError):
            raise ExportError("invalid Notion JSON response") from None
        if (not isinstance(result, dict) or not isinstance(result.get("results"), list)
            or type(result.get("has_more")) is not bool):
            raise ExportError("malformed Notion pagination response")
        pages.extend(result["results"])
        if len(pages) > MAX_PAGES * 100:
            raise ExportError("too many candidate pages")
        if not result["has_more"]:
            return pages
        cursor = result.get("next_cursor")
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise ExportError("invalid Notion cursor")
        seen.add(cursor)
    raise ExportError("pagination limit exceeded")


def make_script(snapshot: dict) -> str:
    # JSON literal, not executable user content; additionally escape HTML delimiters.
    payload = json.dumps(snapshot, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
    return ("/* Reviewed, static export; no credentials or private records. */\n"
            "window.QSOL_RESEARCH_SNAPSHOT = " + payload + ";\n")


def atomic_write(path: Path, contents: str) -> None:
    if path.is_symlink():
        raise ExportError("symlink output refused")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
              dir=path.parent, prefix=".research-", suffix=".tmp", delete=False) as f:
            temp = f.name
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, help="offline query-response fixture")
    parser.add_argument("--output", type=Path, default=Path("docs/research-data.js"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.input_json:
            response = json.loads(args.input_json.read_text("utf-8"))
            if not isinstance(response, dict) or not isinstance(response.get("results"), list):
                raise ExportError("offline fixture must contain a results list")
            pages = response["results"]
        else:
            pages = query_notion(os.environ.get("NOTION_TOKEN", ""),
                                 os.environ.get("NOTION_DATA_SOURCE_ID", ""))
        snapshot = make_snapshot(pages)
        if not args.dry_run:
            atomic_write(args.output, make_script(snapshot))
        print("approved records:", len(snapshot["records"]))
        print("digest:", snapshot["digest"])
        print("output:", "dry run; unchanged" if args.dry_run else str(args.output))
        return 0
    except (ExportError, OSError, ValueError, TypeError) as exc:
        print("export refused:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
