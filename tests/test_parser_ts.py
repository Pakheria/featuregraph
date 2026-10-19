import tempfile
import unittest
from pathlib import Path

from featuregraph.core.parser_ts import TypeScriptFeatureParser


class TestTaggedComponentSpans(unittest.TestCase):
    def test_block_component_span_covers_full_body(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "page.tsx"
            body = "\n".join(f"  const v{i} = {i};" for i in range(80))
            src.write_text(
                "// @feature [PAGE-01] Page\n"
                "export default function Home() {\n"
                f"{body}\n"
                '  const brace = "}";\n'
                "  return null;\n"
                "}\n"
                "const after = 1;\n"
            )
            item = TypeScriptFeatureParser.parse_file(src)[0]
            self.assertEqual(item["symbol"], "Home")
            self.assertEqual(item["start_line"], 1)
            self.assertEqual(item["end_line"], 85)

    def test_concise_body_keeps_window_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "widget.tsx"
            src.write_text(
                "// @feature [WIDGET-01] Widget\n"
                "export const Widget = () => (\n"
                "  <div>\n"
                "    {title}\n"
                "  </div>\n"
                ");\n"
            )
            item = TypeScriptFeatureParser.parse_file(src)[0]
            self.assertEqual(item["end_line"], 6)


if __name__ == "__main__":
    unittest.main()
