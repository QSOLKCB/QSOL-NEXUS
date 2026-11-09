"""Standard-library regression tests for private-to-public Notion projection."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import notion_public_export as export


def f(kind, value):
    return {"type": kind, kind: value}


def record(*, visibility="PUBLIC", approved=True, title="Example"):
    sha = "6c068b32070df4ee86c806b2c38cb124aa77f22b"
    return {"object": "page", "properties": {
        "Name": f("title", [{"plain_text": title}]),
        "System": f("select", {"name": "QSOL-NEXUS"}),
        "Record Type": f("select", {"name": "Integration"}),
        "Status": f("select", {"name": "Completed"}),
        "Visibility": f("select", {"name": visibility}),
        "Publish Approved": f("checkbox", approved),
        "Source Ref": f("rich_text", []),
        "Source Commit": f("rich_text", [{"plain_text": sha}]),
        "Source URL": f("url", "https://github.com/QSOLKCB/QSOL-NEXUS/pull/66"),
        "Summary": f("rich_text", [{"plain_text": "Reviewed source, not live runtime."}]),
        "Last Verified": f("date", None),
    }}


class TestNotionResearch(unittest.TestCase):
    def test_internal_and_unapproved_rows_cannot_publish(self):
        snapshot = export.make_snapshot([record(visibility="INTERNAL"),
                                         record(approved=False), record()])
        self.assertEqual(len(snapshot["records"]), 1)

    def test_deterministic_order_and_digest(self):
        a, b = record(title="A"), record(title="B")
        self.assertEqual(export.make_snapshot([a, b]), export.make_snapshot([b, a]))

    def test_reject_untrusted_source_or_missing_provenance(self):
        r = record()
        r["properties"]["Source URL"] = f("url", "https://attacker.example/path")
        with self.assertRaises(export.ExportError):
            export.make_snapshot([r])
        r = record()
        r["properties"]["Source Commit"] = f("rich_text", [])
        with self.assertRaises(export.ExportError):
            export.make_snapshot([r])

    def test_html_escaped_and_atomic_write(self):
        js = export.make_script(export.make_snapshot([record(title="<script>alert(1)</script>")]))
        self.assertNotIn("<script>", js)
        self.assertIn(r"\u003cscript", js)
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "data.js"
            export.atomic_write(dest, js)
            self.assertEqual(dest.read_text("utf-8"), js)
            link = Path(root) / "link.js"
            link.symlink_to(dest)
            with self.assertRaises(export.ExportError):
                export.atomic_write(link, "unsafe")

    def test_offline_export(self):
        with tempfile.TemporaryDirectory() as root:
            fixture = Path(root) / "fixture.json"
            output = Path(root) / "out.js"
            fixture.write_text(json.dumps({"results": [record()]}), "utf-8")
            self.assertEqual(export.main(["--input-json", str(fixture), "--output", str(output)]), 0)
            self.assertIn("Example", output.read_text("utf-8"))

    def test_no_browser_network_or_script_injection(self):
        html = (ROOT / "docs" / "research.html").read_text("utf-8")
        script = (ROOT / "docs" / "research.js").read_text("utf-8").lower()
        self.assertIn("connect-src 'none'", html)
        self.assertIn("./research-data.js", html)
        for unsafe in ("fetch(", "xmlhttprequest", "websocket(",
                       "innerhtml", "localstorage", "sessionstorage", "eval("):
            self.assertNotIn(unsafe, script)
        self.assertIn("textcontent", script)
        self.assertIn('"records":[]', (ROOT / "docs" / "research-data.js").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
