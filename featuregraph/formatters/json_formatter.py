import json
import re
from pathlib import Path
from typing import Dict, Any

try:
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("featuregraph")
except Exception:
    _VERSION = "unknown"

# @feature [JSON_FORMATT-01] Jsonformatter
class JSONFormatter:
    """Formats feature graph into a 2-Tier Hierarchical (Manifest + Categories) token-efficient index."""

    @staticmethod
    def _extract_category(feat_id: str, data: Dict[str, Any]) -> str:
        """Derives a clean lowercase category slug from category field, ID prefix, or file path."""
        cat = data.get("category")
        if cat and cat != "General":
            slug = re.sub(r"[^a-zA-Z0-9_]", "_", cat.lower()).strip("_")
            if slug:
                return slug

        # Extract from prefix before '-' (e.g. AUTH-01 -> auth, ROUTE-LOGIN -> api_routes)
        if "-" in feat_id:
            prefix = feat_id.split("-")[0].lower()
            if prefix == "route":
                # Check file location if available
                locs = data.get("locations", [])
                if locs:
                    f = locs[0].get("file", "")
                    parts = Path(f).parts
                    if len(parts) > 1:
                        return re.sub(r"[^a-zA-Z0-9_]", "_", parts[-2].lower()).strip("_")
                return "routes"
            return prefix

        return "general"

    @staticmethod
    def split_by_category(graph_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Splits the full feature graph dictionary into domain categories."""
        categories: Dict[str, Dict[str, Any]] = {}
        for feat_id, data in graph_dict.items():
            cat = JSONFormatter._extract_category(feat_id, data)
            categories.setdefault(cat, {})[feat_id] = data
        return categories

    @staticmethod
    def format_manifest(graph_dict: Dict[str, Any]) -> str:
        """
        Generates an ultra-compact Tier-1 manifest (< 100 tokens for small repos, < 500 for enterprise).
        Only lists categories and their feature IDs -> summary names.
        """
        categories = JSONFormatter.split_by_category(graph_dict)
        manifest_data = {
            "_meta": {
                "generator": "featuregraph",
                "version": _VERSION,
                "total_features": len(graph_dict),
                "total_categories": len(categories),
                "instruction": "Read this manifest (<100 tokens) to find the category, then read only .featuregraph/categories/<category>.json for exact lines (#Lstart-Lend)."
            },
            "categories": {
                cat: {fid: fdata.get("name", fid) for fid, fdata in sorted(features.items())}
                for cat, features in sorted(categories.items())
            }
        }
        return json.dumps(manifest_data, indent=2)

    @staticmethod
    # @feature [JSON_FORMATT-02] Format
    def format(graph_dict: Dict[str, Any], root_dir: Path) -> str:
        data = {
            "_meta": {
                "generator": "featuregraph",
                "version": _VERSION,
                "total_features": len(graph_dict),
                "instruction": "Inspect [locations] for exact #Lstart-Lend before reading source code. Check [depends_on] to preserve cross-cutting invariants."
            },
            "features": graph_dict
        }
        return json.dumps(data, indent=2)

    @staticmethod
    # @feature [JSON_FORMATT-03] Write to file
    def write_to_file(graph_dict: Dict[str, Any], output_path: Path, root_dir: Path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = JSONFormatter.format(graph_dict, root_dir)
        output_path.write_text(content, encoding="utf-8")

    @staticmethod
    def write_all(graph_dict: Dict[str, Any], fg_dir: Path, root_dir: Path):
        """Writes manifest.json, unified index.json, and all category files."""
        fg_dir.mkdir(parents=True, exist_ok=True)

        # 1. Tier-1 Manifest
        manifest_content = JSONFormatter.format_manifest(graph_dict)
        (fg_dir / "manifest.json").write_text(manifest_content, encoding="utf-8")

        # 2. Unified index.json
        unified_content = JSONFormatter.format(graph_dict, root_dir)
        (fg_dir / "index.json").write_text(unified_content, encoding="utf-8")

        # 3. Tier-2 Category Chunks
        cat_dir = fg_dir / "categories"
        cat_dir.mkdir(parents=True, exist_ok=True)
        categories = JSONFormatter.split_by_category(graph_dict)

        for cat_name, cat_features in categories.items():
            cat_file = cat_dir / f"{cat_name}.json"
            cat_file.write_text(json.dumps(cat_features, indent=2), encoding="utf-8")
