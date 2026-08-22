import os
from pathlib import Path
from typing import List, Dict, Any, Generator

from .parser_py import PythonFeatureParser
from .parser_ts import TypeScriptFeatureParser
from .graph import FeatureGraph

DEFAULT_IGNORE = {
    "venv", "node_modules", "dist", "build",
    "__pycache__", "logs", "coverage"
}

class WorkspaceScanner:
    """Recursively scans codebase directories and parses feature tags into a FeatureGraph."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.ignore_patterns = set(DEFAULT_IGNORE)
        self._load_ignore_file()

    def detect_subprojects(self) -> List[str]:
        """Detects if current root is a multi-project workspace containing multiple repositories."""
        subprojects = []
        try:
            for child in self.root_dir.iterdir():
                if child.is_dir() and not self._should_ignore_dir(child.name):
                    if (child / ".git").exists() or (child / "pyproject.toml").exists() or (child / "package.json").exists():
                        subprojects.append(child.name)
        except (PermissionError, OSError):
            pass
        return sorted(subprojects)

    def _load_ignore_file(self):
        ignore_file = self.root_dir / ".featureignore"
        if ignore_file.exists():
            for line in ignore_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.ignore_patterns.add(line.rstrip("/"))

    def _should_ignore_dir(self, dir_name: str) -> bool:
        if dir_name.startswith(".") and dir_name not in [".", ".."]:
            return True
        return dir_name in self.ignore_patterns

    def scan(self) -> FeatureGraph:
        graph = FeatureGraph()

        for root, dirs, files in os.walk(self.root_dir, topdown=True):
            # Prune ignored directories in-place so os.walk never enters them
            dirs[:] = [d for d in dirs if not self._should_ignore_dir(d)]

            for file in files:
                if file.startswith(".") and file != ".featureignore":
                    continue

                path = Path(root) / file
                rel_path = path.relative_to(self.root_dir)

                if path.suffix == ".py":
                    parsed = PythonFeatureParser.parse_file(path)
                elif path.suffix in [".ts", ".tsx", ".js", ".jsx"]:
                    parsed = TypeScriptFeatureParser.parse_file(path)
                else:
                    continue

                for item in parsed:
                    item_loc = [{
                        "file": str(rel_path),
                        "symbol": item["symbol"],
                        "type": item["type"],
                        "start_line": item["start_line"],
                        "end_line": item["end_line"],
                        "ref": f"{rel_path}#L{item['start_line']}-L{item['end_line']}"
                    }]
                    graph.add_feature(item["feature_id"], {
                        "name": item["name"],
                        "depends_on": item["depends_on"],
                        "locations": item_loc
                    })

        return graph

