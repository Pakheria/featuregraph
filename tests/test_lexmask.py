import tempfile
import unittest
from pathlib import Path

from featuregraph.core import lexmask
from featuregraph.core.annotator import (
    Suggestion,
    apply_suggestions,
    collect_suggestions,
)
from featuregraph.core.scanner import WorkspaceScanner


def _scan(root: Path) -> dict:
    return WorkspaceScanner(root).scan().to_dict()


class TestLexmaskViews(unittest.TestCase):
    def test_template_literal_and_interpolation_are_masked(self):
        source = "const m = `outer ${`inner ${x}`} done`;\nexport const Kept = 1;\n"
        code = lexmask.code_only(source, "js")
        self.assertIn("export const Kept", code)
        self.assertNotIn("outer", code)
        self.assertNotIn("inner", code)
        self.assertEqual(code.count("\n"), source.count("\n"))

    def test_python_triple_quoted_string_is_not_comment(self):
        source = 'NOTE = """\n# @feature [PHANTOM] Nope\n"""\ndef real(): pass\n'
        comments = lexmask.comment_only(source, "python")
        self.assertNotIn("@feature", comments)
        self.assertEqual(comments.count("\n"), source.count("\n"))

    def test_go_raw_string_is_masked(self):
        source = "var s = `\n// @feature [PHANTOM] Nope\n`\n"
        self.assertNotIn("@feature", lexmask.comment_only(source, "go"))

    def test_real_comments_survive(self):
        source = "// @feature [REAL] Yes\nconst x = 1;\n"
        self.assertIn("@feature [REAL]", lexmask.comment_only(source, "js"))
        self.assertIn("const x", lexmask.code_only(source, "js"))

    def test_regex_with_quotes_does_not_mask_following_code(self):
        source = "const re = /['\"]/;\nexport const After = 1;\n"
        code = lexmask.code_only(source, "js")
        self.assertIn("export const After", code)
        self.assertNotIn("'", code)
        self.assertNotIn('"', code)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(source)
            self.assertEqual({s.symbol for s in collect_suggestions(root)}, {"After"})

    def test_keyword_position_regex_does_not_mask_following_decls(self):
        source = (
            "const check = (s: string) => /['\"]/.test(s);\n"
            "function f() {\n"
            "  return /['\"]/;\n"
            "}\n"
            "export const After = 1;\n"
        )
        code = lexmask.code_only(source, "js")
        self.assertIn("export const After", code)
        self.assertNotIn("'", code)
        self.assertNotIn('"', code)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(source)
            self.assertEqual({s.symbol for s in collect_suggestions(root)}, {"After"})


class TestAnnotatorLexing(unittest.TestCase):
    def test_export_inside_template_is_not_suggested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(
                "const sql = `\n"
                "  // @feature [PHANTOM-01] Nope\n"
                "  export const Fake = 1;\n"
                "`;\n"
                "export const Real = () => null;\n"
            )
            names = {s.symbol for s in collect_suggestions(root)}
            self.assertEqual(names, {"Real"})

    def test_export_inside_block_comment_is_not_suggested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(
                "/*\n"
                "export const Hidden = 1;\n"
                "*/\n"
                "export const Shown = 2;\n"
            )
            names = {s.symbol for s in collect_suggestions(root)}
            self.assertEqual(names, {"Shown"})

    def test_phantom_tag_in_python_string_is_not_tagged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "note.py").write_text(
                'NOTE = """\n'
                "# @feature [PHANTOM-PY] Nope\n"
                '"""\n'
                "def real():\n"
                "    pass\n"
            )
            suggestions = collect_suggestions(root)
            self.assertEqual([s.symbol for s in suggestions], ["real"])

    def test_apply_leaves_masked_text_byte_identical(self):
        original = (
            "const sql = `\n"
            "  export const Fake = 1;\n"
            "`;\n"
            "/*\n"
            "export const Hidden = 2;\n"
            "*/\n"
            "export const Kept = () => null;\n"
        )
        expected = (
            "const sql = `\n"
            "  export const Fake = 1;\n"
            "`;\n"
            "/*\n"
            "export const Hidden = 2;\n"
            "*/\n"
            "// @feature [WIDGET-WIDGET_KEPT] Kept\n"
            "export const Kept = () => null;\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_file = root / "widget.ts"
            source_file.write_text(original)

            written = apply_suggestions(collect_suggestions(root))
            self.assertEqual(sum(written.values()), 1)
            self.assertEqual(source_file.read_text(), expected)

            self.assertEqual(collect_suggestions(root), [])

    def test_apply_refuses_insertion_inside_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_file = root / "widget.ts"
            original = "const sql = `\nexport const Fake = 1;\n`;\n"
            source_file.write_text(original)

            suggestion = Suggestion(
                file=source_file,
                line=2,
                indent="",
                feature_id="FAKE-01",
                name="Fake",
                symbol="Fake",
                lang="typescript",
            )
            written = apply_suggestions([suggestion])
            self.assertEqual(written, {})
            self.assertEqual(source_file.read_text(), original)


class TestParserAndResolverLexing(unittest.TestCase):
    def test_tag_inside_template_is_not_indexed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(
                "const sql = `\n"
                "// @feature [PHANTOM-02] Nope\n"
                "export const Fake = 1;\n"
                "`;\n"
                "// @feature [REAL-01] Real\n"
                "export const Real = 1;\n"
            )
            data = _scan(root)
            self.assertNotIn("PHANTOM-02", data)
            self.assertIn("REAL-01", data)

    def test_python_parser_ignores_hash_line_inside_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "mod.py").write_text(
                "# @feature [OUTER-01] Outer\n"
                "def outer():\n"
                '    text = """\n'
                "    # @feature [PHANTOM-PY-02] Nope\"\"\"\n"
                "    def inner():\n"
                "        return text\n"
            )
            data = _scan(root)
            self.assertIn("OUTER-01", data)
            self.assertNotIn("PHANTOM-PY-02", data)

    def test_dependency_resolver_ignores_strings_and_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "alpha.ts").write_text(
                "// @feature [ALPHA-01] Alpha\n"
                "export const Alpha = () => null;\n"
            )
            (root / "beta.ts").write_text(
                "// @feature [BETA-01] Beta\n"
                'const msg = "Alpha";\n'
                "// Alpha is mentioned only in this comment\n"
                "export const Beta = () => 1;\n"
            )
            (root / "gamma.ts").write_text(
                "// @feature [GAMMA-01] Gamma\n"
                "export const Gamma = () => Alpha();\n"
            )
            data = _scan(root)
            self.assertNotIn("ALPHA-01", data["BETA-01"].get("depends_on", []))
            self.assertIn("ALPHA-01", data["GAMMA-01"].get("depends_on", []))

    def test_php_attribute_is_code_not_comment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "api.php").write_text(
                "<?php\n"
                "#[Route('/users')]\n"
                "public function listUsers() {\n"
                "}\n"
            )
            self.assertIn("ROUTE-LISTUSERS", _scan(root))

    def test_regex_with_backtick_keeps_template_masked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(
                "const re = /`/;\n"
                "const t = `\n"
                "// @feature [PHANTOM-RE] Nope\n"
                "`;\n"
                "// @feature [REAL-RE] Real\n"
                "export const Real = 1;\n"
            )
            data = _scan(root)
            self.assertNotIn("PHANTOM-RE", data)
            self.assertIn("REAL-RE", data)

    def test_keyword_regex_with_backtick_keeps_template_masked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "widget.ts").write_text(
                "function f() {\n"
                "  return /`/;\n"
                "}\n"
                "const t = `\n"
                "// @feature [PHANTOM-KW] Nope\n"
                "`;\n"
                "// @feature [REAL-KW] Real\n"
                "export const Real = 1;\n"
            )
            data = _scan(root)
            self.assertNotIn("PHANTOM-KW", data)
            self.assertIn("REAL-KW", data)


if __name__ == "__main__":
    unittest.main()
