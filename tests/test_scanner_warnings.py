import io
import sys
import unittest
import tempfile
from pathlib import Path
from featuregraph.core.scanner import WorkspaceScanner


class TestScannerWarnings(unittest.TestCase):
    def test_warns_on_syntax_error_file(self):
        """Scanner warns to stderr when a file has a Python syntax error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "broken.py").write_text("def foo(\n    return\n")
            (tmp_path / "good.py").write_text("# @feature [GOOD-01] Good file\ndef ok(): pass\n")

            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = stderr_capture

            try:
                scanner = WorkspaceScanner(tmp_path)
                graph = scanner.scan()
            finally:
                sys.stderr = old_stderr

            stderr_output = stderr_capture.getvalue()
            self.assertIn("broken.py", stderr_output)
            self.assertIn("GOOD-01", graph.nodes)

    def test_warns_on_unparseable_file(self):
        """Scanner warns to stderr when a file has no parseable features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "nothing.ts").write_text("const x = 1;\n")

            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = stderr_capture

            try:
                scanner = WorkspaceScanner(tmp_path)
                scanner.scan()
            finally:
                sys.stderr = old_stderr

            stderr_output = stderr_capture.getvalue()
            self.assertIn("nothing.ts", stderr_output)

    def test_no_warn_when_features_found(self):
        """Scanner does not warn to stderr when all files have features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "app.py").write_text("# @feature [APP-01] App\ndef main(): pass\n")

            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = stderr_capture

            try:
                scanner = WorkspaceScanner(tmp_path)
                graph = scanner.scan()
            finally:
                sys.stderr = old_stderr

            stderr_output = stderr_capture.getvalue()
            self.assertNotIn("⚠ Skipped", stderr_output)
            self.assertIn("APP-01", graph.nodes)

    def test_warnings_are_aggregated_into_one_line(self):
        """Many untagged files produce a single summary warning, not one line per file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for i in range(5):
                (tmp_path / f"f{i}.py").write_text(f"def helper_{i}(): pass\n")
            (tmp_path / "empty.py").write_text("")

            stderr_capture = io.StringIO()
            old_stderr = sys.stderr
            sys.stderr = stderr_capture

            try:
                WorkspaceScanner(tmp_path).scan()
            finally:
                sys.stderr = old_stderr

            stderr_output = stderr_capture.getvalue()
            self.assertEqual(stderr_output.count("⚠"), 1)
            self.assertIn("5 file(s)", stderr_output)
            self.assertIn("(+2 more)", stderr_output)


if __name__ == "__main__":
    unittest.main()
