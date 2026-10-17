import io
import sys
import unittest
from pathlib import Path
from featuregraph.core.parser_py import PythonFeatureParser
from featuregraph.core.parser_ts import TypeScriptFeatureParser
from featuregraph.core.graph import FeatureGraph

class TestFeatureGraph(unittest.TestCase):
    # @feature [TEST_SCANNER-01] Test graph dependencies
    def test_graph_dependencies(self):
        g = FeatureGraph()
        g.add_feature("AUTH-01", {"name": "Auth", "depends_on": ["SEC-01"]})
        g.add_feature("SEC-01", {"name": "Firewall", "depends_on": []})
        
        d = g.to_dict()
        self.assertIn("AUTH-01", d)
        self.assertIn("SEC-01", d["AUTH-01"]["depends_on"])
        self.assertIn("AUTH-01", d["SEC-01"]["called_by"])

    # @feature [TEST_SCANNER-02] Test orphan detection
    def test_orphan_detection(self):
        g = FeatureGraph()
        g.add_feature("ORPHAN-01", {"name": "Dead Feature", "depends_on": []})
        self.assertIn("ORPHAN-01", g.get_orphans())

    # @feature [TEST_SCANNER-03] Test duplicate ID warning
    def test_same_id_across_files_warns_and_merges(self):
        g = FeatureGraph()
        g.add_feature("DUP-01", {
            "name": "One", "depends_on": [],
            "locations": [{"file": "a.py", "lines": [1, 2], "symbol": "one"}],
        })
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            g.add_feature("DUP-01", {
                "name": "Two", "depends_on": [],
                "locations": [{"file": "b.py", "lines": [3, 4], "symbol": "two"}],
            })
        finally:
            sys.stderr = old_stderr

        self.assertIn("DUP-01", captured.getvalue())
        self.assertIn("b.py", captured.getvalue())
        self.assertEqual(len(g.nodes["DUP-01"]["locations"]), 2)

    def test_identical_location_merge_is_silent(self):
        g = FeatureGraph()
        g.add_feature("ONE-01", {"name": "One", "locations": [{"file": "a.py", "lines": [1, 2], "symbol": "one"}]})
        captured = io.StringIO()
        old_stderr = sys.stderr
        sys.stderr = captured
        try:
            g.add_feature("ONE-01", {"name": "One", "locations": [{"file": "a.py", "lines": [1, 2], "symbol": "one"}]})
        finally:
            sys.stderr = old_stderr
        self.assertEqual(captured.getvalue(), "")

if __name__ == "__main__":
    unittest.main()
