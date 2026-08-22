import pytest
from pathlib import Path
from featuregraph.core.parser_py import PythonFeatureParser
from featuregraph.core.parser_ts import TypeScriptFeatureParser
from featuregraph.core.graph import FeatureGraph

def test_graph_dependencies():
    g = FeatureGraph()
    g.add_feature("AUTH-01", {"name": "Auth", "depends_on": ["SEC-01"]})
    g.add_feature("SEC-01", {"name": "Firewall", "depends_on": []})
    
    d = g.to_dict()
    assert "AUTH-01" in d
    assert "SEC-01" in d["AUTH-01"]["depends_on"]
    assert "AUTH-01" in d["SEC-01"]["called_by"]

def test_orphan_detection():
    g = FeatureGraph()
    g.add_feature("ORPHAN-01", {"name": "Dead Feature", "depends_on": []})
    assert "ORPHAN-01" in g.get_orphans()
