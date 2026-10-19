import unittest
import tempfile
from pathlib import Path
from featuregraph.core.annotator import collect_suggestions, apply_suggestions, _next_feat_id

class TestAnnotator(unittest.TestCase):
    def test_collect_and_apply_suggestions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            py_file = tmp_path / "calc.py"
            py_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

            suggestions = collect_suggestions(tmp_path)
            self.assertEqual(len(suggestions), 1)
            # Deterministic ID: category=calc, slug=calc_add → CALC-CALC_ADD
            self.assertTrue(suggestions[0].feature_id.startswith("CALC-"))

            written = apply_suggestions(suggestions)
            self.assertEqual(len(written), 1)
            self.assertIn("# @feature [CALC-CALC_ADD] Add", py_file.read_text())

    def test_deterministic_ids_same_output(self):
        """Two runs on identical code produce the same feature IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            py_file = tmp_path / "calc.py"
            py_file.write_text("def add(a, b):\n    return a + b\n")

            sug1 = collect_suggestions(tmp_path)
            sug2 = collect_suggestions(tmp_path)

            self.assertEqual(len(sug1), len(sug2))
            for s1, s2 in zip(sug1, sug2):
                self.assertEqual(s1.feature_id, s2.feature_id)
                self.assertEqual(s1.name, s2.name)

    def test_deterministic_ids_multi_file(self):
        """Multiple files produce stable IDs across runs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "a.py").write_text("def foo(): pass\n")
            (tmp_path / "b.py").write_text("def bar(): pass\n")

            sug1 = collect_suggestions(tmp_path)
            sug2 = collect_suggestions(tmp_path)

            ids1 = sorted(s.feature_id for s in sug1)
            ids2 = sorted(s.feature_id for s in sug2)
            self.assertEqual(ids1, ids2)

    def test_dedup_id_counter(self):
        """Same symbol name in same category increments dedup counter."""
        used: dict = {}
        self.assertEqual(_next_feat_id(used, "mycat", "Foo"), "MYCAT-FOO")
        self.assertEqual(_next_feat_id(used, "mycat", "Foo"), "MYCAT-FOO-01")
        self.assertEqual(_next_feat_id(used, "mycat", "Foo"), "MYCAT-FOO-02")

    def test_different_slugs_no_collision(self):
        """Different symbols get different IDs even in same category."""
        used: dict = {}
        self.assertEqual(_next_feat_id(used, "mycat", "Foo"), "MYCAT-FOO")
        self.assertEqual(_next_feat_id(used, "mycat", "Bar"), "MYCAT-BAR")

    def test_no_suggestions_for_empty_dir(self):
        """Empty directory yields no suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            suggestions = collect_suggestions(Path(tmpdir))
            self.assertEqual(len(suggestions), 0)

    def test_no_suggestions_already_annotated(self):
        """Already-annotated symbols produce no suggestions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            py_file = tmp_path / "calc.py"
            py_file.write_text("# @feature [CALC-01] Add\ndef add(a, b):\n    return a + b\n")

            suggestions = collect_suggestions(tmp_path)
            self.assertEqual(len(suggestions), 0)

    def test_tag_above_previous_symbol_does_not_cover_next(self):
        """A tag above one symbol must not hide the next unannotated symbol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "calc.py").write_text(
                "# @feature [CALC-ADD] Add\n"
                "def add(a, b):\n"
                "    return a + b\n"
                "def sub(a, b):\n"
                "    return a - b\n"
            )

            suggestions = collect_suggestions(root)
            self.assertEqual([s.symbol for s in suggestions], ["sub"])

    def test_tag_above_decorator_still_counts(self):
        """Tags above decorators still cover the decorated symbol."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "calc.py").write_text(
                "# @feature [CALC-ADD] Add\n"
                "@staticmethod\n"
                "def add(a, b):\n"
                "    return a + b\n"
            )

            self.assertEqual(collect_suggestions(root), [])


if __name__ == "__main__":
    unittest.main()
