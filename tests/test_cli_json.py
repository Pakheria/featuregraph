import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from featuregraph.cli import main
from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.formatters.json_formatter import JSONFormatter


class TestCliJson(unittest.TestCase):
    def _make_project(self, root: Path):
        (root / "a.py").write_text("# @feature [AUTH-01] Auth gate\ndef auth(): pass\n")
        fg_dir = root / ".featuregraph"
        fg_dir.mkdir()
        JSONFormatter.write_all(WorkspaceScanner(root).scan().to_dict(), fg_dir, root)

    def test_query_json_from_outside_project_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_project(root)

            out = io.StringIO()
            argv = ["featuregraph", "query", "AUTH-01", "--dir", str(root), "--json"]
            with patch.object(sys, "argv", argv), redirect_stdout(out):
                main()

            data = json.loads(out.getvalue())
            self.assertEqual(data["id"], "AUTH-01")
            self.assertEqual(data["name"], "Auth gate")

    def test_search_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._make_project(root)

            out = io.StringIO()
            argv = ["featuregraph", "search", "auth", "--dir", str(root), "--json"]
            with patch.object(sys, "argv", argv), redirect_stdout(out):
                main()

            results = json.loads(out.getvalue())
            self.assertTrue(any(r["id"] == "AUTH-01" for r in results))


if __name__ == "__main__":
    unittest.main()
