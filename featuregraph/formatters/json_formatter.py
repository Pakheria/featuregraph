import json
from pathlib import Path
from typing import Dict, Any

class JSONFormatter:
    """Formats feature graph into an ultra-compact, token-efficient JSON index for AI assistants."""

    @staticmethod
    def format(graph_dict: Dict[str, Any], root_dir: Path) -> str:
        data = {
            "_meta": {
                "generator": "featuregraph",
                "version": "0.1.0",
                "total_features": len(graph_dict),
                "instruction": "Inspect [locations] for exact #Lstart-Lend before reading source code. Check [depends_on] to preserve cross-cutting invariants."
            },
            "features": graph_dict
        }
        return json.dumps(data, indent=2)

    @staticmethod
    def write_to_file(graph_dict: Dict[str, Any], output_path: Path, root_dir: Path):
        content = JSONFormatter.format(graph_dict, root_dir)
        output_path.write_text(content, encoding="utf-8")
