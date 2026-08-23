import unittest
import tempfile
from pathlib import Path
from featuregraph.core.annotator import collect_suggestions, apply_suggestions

class TestAnnotator(unittest.TestCase):
    def test_collect_and_apply_suggestions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            py_file = tmp_path / "calc.py"
            py_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

            suggestions = collect_suggestions(tmp_path)
            self.assertEqual(len(suggestions), 1)
            self.assertEqual(suggestions[0].feature_id, "CALC-01")

            written = apply_suggestions(suggestions)
            self.assertEqual(len(written), 1)
            self.assertIn("# @feature [CALC-01] Add", py_file.read_text())

if __name__ == "__main__":
    unittest.main()
