import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from featuregraph.core.scanner import WorkspaceScanner
from featuregraph.core.annotator import collect_suggestions


@unittest.skipUnless(shutil.which("git"), "git not available")
class TestGitignoreAwareScanning(unittest.TestCase):
    def test_gitignored_trees_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("vendor/\n")
            (root / "vendor").mkdir()
            (root / "vendor" / "vendored.py").write_text(
                "# @feature [VENDOR-01] Vendored\ndef v(): pass\n"
            )
            (root / "app.py").write_text("# @feature [APP-01] App\ndef main(): pass\n")

            data = WorkspaceScanner(root).scan().to_dict()
            self.assertIn("APP-01", data)
            self.assertNotIn("VENDOR-01", data)


class TestFeatureignore(unittest.TestCase):
    def test_featureignore_excluded_from_scan_and_annotate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".featureignore").write_text("skipme\n")
            (root / "skipme").mkdir()
            (root / "skipme" / "x.py").write_text("# @feature [SKIP-01] Skip\ndef s(): pass\n")
            (root / "keep.py").write_text("# @feature [KEEP-01] Keep\ndef k(): pass\n")

            data = WorkspaceScanner(root).scan().to_dict()
            self.assertIn("KEEP-01", data)
            self.assertNotIn("SKIP-01", data)

            (root / "skipme" / "untagged.py").write_text("def nope(): pass\n")
            (root / "keep_untagged.py").write_text("def yep(): pass\n")
            files = {s.file.name for s in collect_suggestions(root)}
            self.assertIn("keep_untagged.py", files)
            self.assertNotIn("untagged.py", files)


if __name__ == "__main__":
    unittest.main()
