import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from featuregraph.cli import main
from featuregraph.core.parser_ts import TypeScriptFeatureParser


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


class TestCommonJSExtraction(unittest.TestCase):
    def test_untagged_js_extracts_members_and_exports(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "engine.js"
            src.write_text(
                "class Engine {\n"
                "  load(key) {\n"
                "    return key;\n"
                "  }\n"
                "}\n"
                "Engine.prototype.clear = function () { return 1; };\n"
                "function helper() { return 2; }\n"
                "const run = (x) => x;\n"
                "module.exports = { helper, run };\n"
                "exports.extra = function () {};\n"
                "module.exports = function named() {};\n"
                "module.exports = class Exported {};\n"
            )
            items = TypeScriptFeatureParser.parse_file(src)
            self.assertEqual(
                {item["symbol"] for item in items},
                {"Engine", "load", "clear", "helper", "run", "extra", "named", "Exported"},
            )
            self.assertTrue(all(item.get("auto") for item in items))
            load = next(item for item in items if item["symbol"] == "load")
            self.assertEqual(load["qualname"], "Engine.load")
            self.assertEqual(load["start_line"], 2)
            run = next(item for item in items if item["symbol"] == "run")
            self.assertEqual(run["end_line"], 8)

    def test_tagged_default_export_uses_component_symbol(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "page.tsx"
            src.write_text(
                "// @feature [PAGE-01] Page\n"
                "export default function Home() { return null; }\n"
            )
            item = TypeScriptFeatureParser.parse_file(src)[0]
            self.assertEqual(item["symbol"], "Home")

    def test_tagged_js_keeps_tag_only_behavior(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "legacy.js"
            src.write_text(
                "// @feature [LEGACY-01] Legacy\n"
                "function legacy() {}\n"
                "function untagged() {}\n"
            )
            items = TypeScriptFeatureParser.parse_file(src)
            self.assertEqual([item["feature_id"] for item in items], ["LEGACY-01"])
            self.assertNotIn("auto", items[0])


class TestBrokenJavaScript(unittest.TestCase):
    def test_syntactically_broken_js_falls_back_to_file_level(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "bad-broken.js").write_text("function broken( {\n  return 1\n")
            code, _, err = _run(["scan", "--dir", str(root), "--quiet"])
            self.assertEqual(code, 0, err)
            features = json.loads(
                (root / ".featuregraph" / "index.json").read_text()
            )["features"]
            keys = list(features)
            self.assertTrue(any(k.startswith("FILE-") for k in keys), keys)
            self.assertFalse(any(k.startswith("CJS-") for k in keys), keys)


class TestFileLevelFallback(unittest.TestCase):
    def test_unparseable_file_is_indexed_and_still_warned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "deploy.sh").write_text("#!/bin/sh\necho deploy\n")
            code, out, err = _run(["scan", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("deploy.sh", err)
            index = json.loads((root / ".featuregraph" / "index.json").read_text())
            feature_id, feature = next(iter(index["features"].items()))
            self.assertEqual(feature_id, "FILE-DEPLOY-SH")
            location = feature["locations"][0]
            self.assertEqual((location["file"], location["lines"]), ("deploy.sh", [1, 2]))
            meta = json.loads((root / ".featuregraph" / "manifest.json").read_text())["_meta"]
            self.assertEqual(meta["indexed_files"], 1)
            self.assertEqual(meta["unindexed_files"], 0)
            self.assertEqual(meta["file_level_files"], 1)

    def test_auto_features_do_not_create_inference_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "caller.py").write_text(
                "# @feature [CALLER-01] Caller\ndef caller(): target()\n"
            )
            (root / "target.js").write_text("function target() {}\n")
            code, _, err = _run(["scan", "--dir", str(root), "--quiet"])
            self.assertEqual(code, 0, err)
            features = json.loads(
                (root / ".featuregraph" / "index.json").read_text()
            )["features"]
            caller = features["CALLER-01"]
            self.assertFalse(caller.get("depends_on"))
            auto = next(v for k, v in features.items() if k.startswith("CJS-"))
            self.assertFalse(auto.get("depends_on"))

    def test_scan_query_by_file_symbol(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "deploy.sh").write_text("#!/bin/sh\necho deploy\n")
            code, _, err = _run(["scan", "--dir", str(root), "--quiet"])
            self.assertEqual(code, 0, err)
            code, out, err = _run(["query", "deploy.sh", "--dir", str(root)])
            self.assertEqual(code, 0, err)
            self.assertIn("FILE-DEPLOY-SH", out)


if __name__ == "__main__":
    unittest.main()
