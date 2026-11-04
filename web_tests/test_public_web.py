"""Checks the read-only public web observatory without third-party packages."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "index.html"
SCRIPT = ROOT / "docs" / "portal.js"

EXPECTED = {
    "QSOL-SUBSTRATE", "QSOL-ARK", "QSOL-INT", "QSOL-ORACLE",
    "QSOL-NEXUS", "QSOL-FED", "LATTICE", "QSOL-CONTROL",
}

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.scripts = []
        self.systems = 0
        self.csp = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article" and "data-system" in attrs:
            self.systems += 1
        if tag == "script":
            self.scripts.append(attrs.get("src"))
        if tag == "a" and attrs.get("href", "").startswith("https://"):
            self.links.append(attrs)
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs.get("content")


class TestPublicWeb(unittest.TestCase):
    def test_static_source_inventory_and_csp(self):
        parser = PageParser()
        parser.feed(PAGE.read_text(encoding="utf-8"))
        self.assertEqual(parser.systems, 8)
        self.assertEqual(parser.scripts, ["./portal.js"])
        self.assertIsNotNone(parser.csp)
        for directive in ("default-src 'none'", "connect-src 'none'", "script-src 'self'"):
            self.assertIn(directive, parser.csp)
        urls = {a["href"] for a in parser.links}
        for repo in EXPECTED:
            self.assertIn("https://github.com/QSOLKCB/" + repo, urls)
        for link in parser.links:
            self.assertEqual(link.get("target"), "_blank")
            self.assertEqual(link.get("rel"), "noopener noreferrer")

    def test_no_outbound_browser_control_plane(self):
        script = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("fetch(", "xmlhttprequest", "websocket(", "sendbeacon",
                          "localstorage", "sessionstorage", "innerhtml", "eval("):
            self.assertNotIn(forbidden, script)
        page = PAGE.read_text(encoding="utf-8")
        self.assertIn("PAGES: STATIC / NO RUNTIME API CONNECTION", page)
        self.assertIn("Internet-facing", (ROOT / "docs" / "PUBLIC_WEB.md").read_text(encoding="utf-8"))

    def test_gateway_is_external_navigation_not_an_embedded_api(self):
        html = PAGE.read_text(encoding="utf-8")
        self.assertIn('href="https://qsol-control-edge.onrender.com/"', html)
        self.assertIn("DEPLOYED / SEPARATE LOGIN", html)
        self.assertNotIn("NOT CONNECTED</strong>", html)
        self.assertIn("GitHub Pages does not access its API", html)
        parser = PageParser()
        parser.feed(html)
        self.assertIn("connect-src 'none'", parser.csp)
        script = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("fetch(", "xmlhttprequest", "websocket("):
            self.assertNotIn(forbidden, script)

    def test_lattice_mapping_and_phi_coverage(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("const PHI_STRIDE = 17;", script)
        self.assertIn("const CELL_COUNT = 27;", script)
        self.assertIn("const index = x * 9 + y * 3 + z;", script)
        cells = [(x, y, z) for x in range(3) for y in range(3) for z in range(3)]
        self.assertEqual(len(set(cells)), 27)
        self.assertEqual(len({(i * 17) % 27 for i in range(27)}), 27)
        self.assertEqual((17 * 8) % 27, 1)

    def test_branch_and_root_publication_entries(self):
        root = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="0;url=docs/"', root)
        self.assertTrue(PAGE.is_file())
        self.assertTrue((ROOT / "docs" / "portal.css").is_file())


if __name__ == "__main__":
    unittest.main()
