import unittest
import warnings
import tempfile
from pathlib import Path
from featuregraph.core.scanner import WorkspaceScanner


class TestScannerWarnings(unittest.TestCase):
    def test_warns_on_syntax_error_file(self):
        """Scanner warns when a file has a Python syntax error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # A file with invalid Python syntax
            (tmp_path / "broken.py").write_text("def foo(\n    return\n")
            # A valid file
            (tmp_path / "good.py").write_text("# @feature [GOOD-01] Good file\ndef ok(): pass\n")

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                scanner = WorkspaceScanner(tmp_path)
                graph = scanner.scan()

            # Should have warned about the broken file
            self.assertGreaterEqual(len(w), 1)
            self.assertTrue(any("broken.py" in str(warning.message) for warning in w))
            # But the good file should still be in the graph
            self.assertIn("GOOD-01", graph.nodes)

    def test_warns_on_unparseable_file(self):
        """Scanner warns when a non-Python file has no parseable features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # A .ts file with no @feature tags
            (tmp_path / "nothing.ts").write_text("const x = 1;\n")

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                scanner = WorkspaceScanner(tmp_path)
                graph = scanner.scan()

            self.assertGreaterEqual(len(w), 1)
            self.assertTrue(any("nothing.ts" in str(warning.message) for warning in w))

    def test_no_warn_when_features_found(self):
        """Scanner does not warn when all files have features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "app.py").write_text("# @feature [APP-01] App\ndef main(): pass\n")

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                scanner = WorkspaceScanner(tmp_path)
                graph = scanner.scan()

            # No warnings expected
            self.assertEqual(len(w), 0)
            self.assertIn("APP-01", graph.nodes)


if __name__ == "__main__":
    unittest.main()
