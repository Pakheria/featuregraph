import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from featuregraph.cli import main
from featuregraph.core.scanner import WorkspaceScanner


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", ["featuregraph", *argv]), \
            redirect_stdout(out), redirect_stderr(err):
        try:
            main()
            code = 0
        except SystemExit as exc:
            code = exc.code or 0
    return code, out.getvalue(), err.getvalue()


def _tree(root: Path) -> dict:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted((root / ".featuregraph").rglob("*"))
        if p.is_file()
    }


class TestSymbolIds(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        files = {
            "web/app/layout.py": "# @feature [LAYOUT-ROOT] Root layout\ndef layout():\n    return 'root'\n",
            "web/app/page.py": "# @feature [PAGE-ROOT] Root page\ndef page():\n    return layout()\n",
            "web/app/docs/layout.py": "# @feature [LAYOUT-DOCS] Docs layout\ndef layout():\n    return 'docs'\n",
            "web/app/docs/page.py": "# @feature [PAGE-DOCS] Docs page\ndef page():\n    return layout()\n",
        }
        for rel, content in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        code, _, err = _run(["scan", "--dir", str(self.root), "--quiet"])
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self._tmp.cleanup()

    def test_ids_are_qualified_and_edges_resolve_by_path(self):
        data = WorkspaceScanner(self.root).scan().to_dict()
        self.assertEqual(data["PAGE-ROOT"]["depends_on"], ["LAYOUT-ROOT"])
        self.assertEqual(data["PAGE-DOCS"]["depends_on"], ["LAYOUT-DOCS"])
        self.assertEqual(data["LAYOUT-ROOT"]["locations"][0]["symbol_id"], "web.app.layout")
        self.assertEqual(data["LAYOUT-DOCS"]["locations"][0]["symbol_id"], "web.app.docs.layout")

        index = json.loads((self.root / ".featuregraph" / "index.json").read_text())
        self.assertEqual(
            index["features"]["LAYOUT-DOCS"]["locations"][0]["symbol_id"],
            "web.app.docs.layout",
        )

    def test_query_ambiguous_bare_name_lists_qualified_ids(self):
        code, out, _ = _run(["query", "layout", "--dir", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("web.app.layout", out)
        self.assertIn("web.app.docs.layout", out)
        self.assertIn("LAYOUT-ROOT", out)
        self.assertIn("LAYOUT-DOCS", out)

    def test_query_qualified_symbol_id_resolves(self):
        code, out, err = _run(["query", "web.app.docs.layout", "--dir", str(self.root)])
        self.assertEqual(code, 0, err)
        self.assertIn("LAYOUT-DOCS", out)

        code, out, err = _run(["query", "web.app.page", "--dir", str(self.root)])
        self.assertEqual(code, 0, err)
        self.assertIn("PAGE-ROOT", out)

    def test_search_ambiguous_bare_name_errors(self):
        code, out, _ = _run(["search", "page", "--dir", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("web.app.page", out)
        self.assertIn("web.app.docs.page", out)

        code, out, err = _run(["search", "web.app.docs.page", "--dir", str(self.root)])
        self.assertEqual(code, 0, err)
        self.assertIn("PAGE-DOCS", out)

    def test_collision_ids_stable_across_rescans(self):
        first = _tree(self.root)
        code, _, err = _run(["scan", "--dir", str(self.root), "--quiet"])
        self.assertEqual(code, 0, err)
        self.assertEqual(_tree(self.root), first)


if __name__ == "__main__":
    unittest.main()
