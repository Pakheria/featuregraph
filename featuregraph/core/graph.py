from __future__ import annotations

class FeatureGraph:
    """Manages the directed acyclic feature dependency graph, detects cycles and orphaned features."""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Set[str]] = {} # node -> set(dependencies)
        self.reverse_edges: Dict[str, Set[str]] = {} # node -> set(dependents)

    def add_feature(self, feature_id: str, data: Dict[str, Any]):
        feat_id = feature_id.upper()
        if feat_id not in self.nodes:
            self.nodes[feat_id] = data
            self.edges[feat_id] = set()
            self.reverse_edges[feat_id] = set()
        else:
            # Merge locations
            existing_locs = self.nodes[feat_id].get("locations", [])
            new_locs = data.get("locations", [])
            self.nodes[feat_id]["locations"] = existing_locs + new_locs
            if not self.nodes[feat_id].get("name") and data.get("name"):
                self.nodes[feat_id]["name"] = data.get("name")

        for dep in data.get("depends_on", []):
            dep_clean = dep.strip().upper()
            if dep_clean:
                self.edges[feat_id].add(dep_clean)
                if dep_clean not in self.reverse_edges:
                    self.reverse_edges[dep_clean] = set()
                self.reverse_edges[dep_clean].add(feat_id)

    def get_orphans(self) -> List[str]:
        """Returns features that have no callers/dependents and are not root features."""
        orphans = []
        for feat_id in self.nodes:
            if not self.edges.get(feat_id) and not self.reverse_edges.get(feat_id):
                orphans.append(feat_id)
        return orphans

    def to_dict(self) -> Dict[str, Any]:
        output = {}
        for feat_id, data in self.nodes.items():
            output[feat_id] = {
                "name": data.get("name", feat_id),
                "category": data.get("category", "General"),
                "description": data.get("description", ""),
                "depends_on": sorted(list(self.edges.get(feat_id, set()))),
                "called_by": sorted(list(self.reverse_edges.get(feat_id, set()))),
                "locations": data.get("locations", [])
            }
        return output
