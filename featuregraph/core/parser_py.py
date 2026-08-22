import ast
import re
from pathlib import Path
from typing import Dict, List, Any

FEATURE_TAG_REGEX = re.compile(r"@feature\s+\[([A-Za-z0-9_\-]+)\](?:\s+(.*))?", re.IGNORECASE)
DEPENDS_TAG_REGEX = re.compile(r"@depends\s+\[([A-Za-z0-9_\-,\s]+)\]", re.IGNORECASE)

class PythonFeatureParser:
    """Parses Python source code with AST to extract feature tags, routes, classes, and exact line spans."""

    @staticmethod
    def parse_file(file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            return []

        results = []
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
            lines = source.splitlines()

            # 1. AST Node Traversal
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue

                docstring = ast.get_docstring(node) or ""
                
                # Check for explicit feature comments above node
                start_line = node.lineno
                end_line = node.end_lineno
                
                # Look in preceding 5 lines for comment tags
                preceding_text = "\n".join(lines[max(0, start_line - 6):start_line])
                
                feat_match = FEATURE_TAG_REGEX.search(preceding_text) or FEATURE_TAG_REGEX.search(docstring)
                dep_match = DEPENDS_TAG_REGEX.search(preceding_text) or DEPENDS_TAG_REGEX.search(docstring)

                node_name = getattr(node, "name", "")
                deps = []
                if dep_match:
                    raw_deps = dep_match.group(1).split(",")
                    deps = [d.strip().strip("[]") for d in raw_deps if d.strip()]

                # If tagged explicitly
                if feat_match:
                    feat_id = feat_match.group(1).upper()
                    desc = feat_match.group(2) or (docstring.split("\n")[0] if docstring else node_name)
                    results.append({
                        "feature_id": feat_id,
                        "name": desc,
                        "symbol": node_name,
                        "type": "class" if isinstance(node, ast.ClassDef) else "function",
                        "start_line": start_line,
                        "end_line": end_line,
                        "depends_on": deps,
                        "file": str(file_path)
                    })
                # Also discover FastAPI / Flask route handlers automatically
                elif hasattr(node, "decorator_list") and node.decorator_list:
                    for dec in node.decorator_list:
                        dec_src = ast.unparse(dec) if hasattr(ast, "unparse") else ""
                        if any(r in dec_src for r in ["router.", "app.", "get(", "post(", "put(", "delete(", "patch("]):
                            results.append({
                                "feature_id": f"ROUTE-{node_name.upper()}",
                                "name": f"API Endpoint `{node_name}` ({dec_src})",
                                "symbol": node_name,
                                "type": "endpoint",
                                "start_line": start_line,
                                "end_line": end_line,
                                "depends_on": [],
                                "file": str(file_path)
                            })
                            break

        except (SyntaxError, UnicodeDecodeError, ValueError):
            pass

        return results
