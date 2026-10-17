import unittest
import tempfile
from pathlib import Path

from featuregraph.core.scanner import WorkspaceScanner


def _scan(tmp_path: Path) -> dict:
    return WorkspaceScanner(tmp_path).scan().to_dict()


class TestCommentOnlyTags(unittest.TestCase):
    """@feature text inside string literals must never create features (phantom bug)."""

    def test_python_string_literal_is_not_a_feature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "t.py").write_text(
                "def one():\n"
                "    pass\n"
                "\n"
                "def two():\n"
                "    assert '# @feature [PHANTOM-01] Nope' in 'x'\n"
                "\n"
                "def three():\n"
                "    pass\n"
            )
            self.assertNotIn("PHANTOM-01", _scan(tmp_path))

    def test_python_comment_tag_still_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "t.py").write_text("# @feature [REAL-01] Real\ndef real(): pass\n")
            self.assertIn("REAL-01", _scan(tmp_path))

    def test_ts_string_literal_is_not_a_feature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "w.tsx").write_text(
                'const msg = "// @feature [PHANTOM-02] Nope";\n'
                "export const Widget = () => null;\n"
            )
            self.assertNotIn("PHANTOM-02", _scan(tmp_path))

    def test_ts_comment_tag_still_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "w.tsx").write_text(
                "// @feature [REAL-02] Real\nexport const Widget = () => null;\n"
            )
            self.assertIn("REAL-02", _scan(tmp_path))

    def test_go_string_literal_is_not_a_feature(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "m.go").write_text(
                'package main\n\nvar s = "// @feature [PHANTOM-03] Nope"\n\nfunc main() {}\n'
            )
            self.assertNotIn("PHANTOM-03", _scan(tmp_path))

    def test_go_comment_tag_still_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "m.go").write_text(
                "package main\n\n// @feature [REAL-03] Real\nfunc main() {}\n"
            )
            self.assertIn("REAL-03", _scan(tmp_path))


if __name__ == "__main__":
    unittest.main()
