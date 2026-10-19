import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from featuregraph.cli import main


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


class TestFreshnessGuard(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        src = root / "app.py"
        src.write_text("# @feature [AUTH-01] Auth gate\ndef auth(): pass\n")
        code, _, err = _run(["scan", "--dir", str(root), "--quiet"])
        self.assertEqual(code, 0, err)
        self.assertFalse((root / ".git").exists())
        return src

    def test_query_ok_after_scan_without_git(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._project(root)
            code, out, err = _run(["query", "AUTH-01", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("AUTH-01", out)

    def test_edit_refuses_until_rescan_and_force_bypasses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = self._project(root)

            src.write_text(
                "# @feature [AUTH-01] Auth gate\n"
                "def auth(): pass\n"
                "def changed_size(): pass\n"
            )

            code, out, err = _run(["query", "AUTH-01", "--dir", str(root)])
            self.assertNotEqual(code, 0)
            self.assertIn("index is stale (tree changed since scan); run: featuregraph scan", err)
            self.assertNotIn("AUTH-01", out)

            code, out, err = _run(["search", "auth", "--dir", str(root)])
            self.assertNotEqual(code, 0)
            self.assertIn("index is stale", err)

            code, out, err = _run(["query", "AUTH-01", "--dir", str(root), "--force"])
            self.assertEqual(code, 0, err)
            self.assertIn("AUTH-01", out)

            code, _, err = _run(["scan", "--dir", str(root), "--quiet"])
            self.assertEqual(code, 0, err)
            code, out, err = _run(["query", "AUTH-01", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("AUTH-01", out)

    def test_ignored_tree_does_not_trip_guard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._project(root)

            ignored = root / "node_modules" / "phantom.py"
            ignored.parent.mkdir()
            ignored.write_text("# @feature [PHANTOM-01] Nope\ndef p(): pass\n")

            code, out, err = _run(["query", "AUTH-01", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("AUTH-01", out)


class TestTruthfulManifest(unittest.TestCase):
    def _scan(self, root: Path):
        return _run(["scan", "--dir", str(root)])

    def _meta(self, root: Path) -> dict:
        return json.loads((root / ".featuregraph" / "manifest.json").read_text())["_meta"]

    def test_empty_repo_indexes_file_level_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("def untagged(): pass\n")
            code, out, err = self._scan(root)
            self.assertEqual(code, 0)
            self.assertNotIn("⚠ No features found", out)
            self.assertIn("app.py", err)
            meta = self._meta(root)
            self.assertEqual(meta["status"], "partial")
            self.assertEqual(meta["total_features"], 1)
            self.assertEqual(meta["total_files"], 1)
            self.assertEqual(meta["indexed_files"], 1)
            self.assertEqual(meta["unindexed_files"], 0)
            self.assertEqual(meta["file_level_files"], 1)
            unindexed = json.loads((root / ".featuregraph" / "unindexed.json").read_text())
            self.assertEqual(unindexed, [])
            feature_id, feature = next(iter(json.loads(
                (root / ".featuregraph" / "index.json").read_text()
            )["features"].items()))
            self.assertEqual(feature["locations"][0]["file"], "app.py")
            self.assertTrue(feature_id.startswith("FILE-"))

    def test_mixed_repo_is_partial_with_matching_unindexed_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tagged.py").write_text("# @feature [OK-01] Ok\ndef ok(): pass\n")
            (root / "untagged.py").write_text("def nope(): pass\n")
            code, out, err = self._scan(root)
            self.assertEqual(code, 0)
            self.assertNotIn("⚠ No features found", out)
            self.assertIn("untagged.py", err)

            meta = self._meta(root)
            self.assertEqual(meta["status"], "partial")
            self.assertEqual(meta["total_files"], 2)
            self.assertEqual(meta["indexed_files"], 2)
            self.assertEqual(meta["unindexed_files"], 0)
            self.assertEqual(meta["file_level_files"], 1)
            unindexed = json.loads((root / ".featuregraph" / "unindexed.json").read_text())
            self.assertEqual(unindexed, [])

    def test_fully_tagged_repo_is_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tagged.py").write_text("# @feature [OK-01] Ok\ndef ok(): pass\n")
            code, _, err = self._scan(root)
            self.assertEqual(code, 0, err)
            meta = self._meta(root)
            self.assertEqual(meta["status"], "ok")
            self.assertEqual(meta["total_files"], 1)
            self.assertEqual(meta["indexed_files"], 1)
            self.assertEqual(meta["unindexed_files"], 0)
            unindexed = json.loads((root / ".featuregraph" / "unindexed.json").read_text())
            self.assertEqual(unindexed, [])

    def test_rescan_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "tagged.py").write_text("# @feature [OK-01] Ok\ndef ok(): pass\n")
            (root / "untagged.py").write_text("def nope(): pass\n")
            self._scan(root)
            first = _tree(root)
            self._scan(root)
            self.assertEqual(_tree(root), first)

    def test_rescan_removes_stale_category(self):
        """A category with no remaining features must not survive as a ghost search hit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            src = root / "auth.py"
            src.write_text("# @feature [AUTH-01] Auth\ndef auth(): pass\n")
            self._scan(root)
            self.assertTrue((root / ".featuregraph" / "categories" / "auth.json").exists())

            src.write_text("def auth(): pass\n")
            self._scan(root)
            self.assertFalse((root / ".featuregraph" / "categories" / "auth.json").exists())

            code, out, err = _run(["search", "auth", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertNotIn("AUTH-01", out)

    def test_scan_json_also_updates_canonical_index(self):
        """--json is an extra copy; the canonical manifest/categories must still be written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("# @feature [A-01] A\ndef a(): pass\n")

            code, out, err = _run(["scan", "--dir", str(root), "--json", "custom.json"])
            self.assertEqual(code, 0, err)
            self.assertTrue((root / "custom.json").exists())
            self.assertTrue((root / ".featuregraph" / "manifest.json").exists())
            self.assertTrue((root / ".featuregraph" / "categories" / "a.json").exists())

            code, out, err = _run(["query", "A-01", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("A-01", out)


if __name__ == "__main__":
    unittest.main()
