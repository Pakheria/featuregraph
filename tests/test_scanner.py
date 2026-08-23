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

if __name__ == "__main__":
    unittest.main()
