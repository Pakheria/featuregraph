import ast
import re
from pathlib import Path
from typing import Dict, List, Any

from . import lexmask

FEATURE_TAG_REGEX = re.compile(r"@feature\s+\[([A-Za-z0-9_\-]+)\](?:\s+(.*))?", re.IGNORECASE)
DEPENDS_TAG_REGEX = re.compile(r"@depends(?:_on)?\s+\[([A-Za-z0-9_\-,\s]+)\]", re.IGNORECASE)

# @feature [PARSER_PY-01] Python feature parser
class PythonFeatureParser:
    """Parses Python source code with AST to extract feature tags, routes, classes, and exact line spans."""

    @staticmethod
    # @feature [PARSER_PY-02] Parse file
    def parse_file(file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            return []

        results = []
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
            lines = source.splitlines()
            comment_lines = lexmask.comment_only(source, "python").splitlines()

            # Map method nodes to their enclosing class path (for qualified symbol resolution)
            parent_class: Dict[int, str] = {}

            def visit(node, prefix: str):
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.ClassDef):
                        visit(child, f"{prefix}{child.name}.")
                    elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if prefix:
                            parent_class[id(child)] = prefix.rstrip(".")
                        visit(child, "")  # nested defs inside methods are not methods
                    else:
                        visit(child, prefix)

            visit(tree, "")

            # 1. AST Node Traversal
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue

                docstring = ast.get_docstring(node) or ""
                
                # Check for explicit feature comments above node
                start_line = node.lineno
                end_line = node.end_lineno
                
                # Look upwards in preceding lines for comment tags (closest first)
                feat_match = None
                dep_match = None

                for i in range(start_line - 2, max(-1, start_line - 8), -1):
                    if i < len(lines):
                        line_str = lines[i].strip()
                        comment_line = comment_lines[i].strip()
                        # Only real comment lines count — string literals must not create features
                        if comment_line.startswith("#") and line_str.startswith("#"):
                            if not feat_match:
                                feat_match = FEATURE_TAG_REGEX.search(comment_line)
                            if not dep_match:
                                dep_match = DEPENDS_TAG_REGEX.search(comment_line)
                        if line_str and not line_str.startswith("#") and not line_str.startswith("@"):
                            break

                if not feat_match and docstring:
                    feat_match = FEATURE_TAG_REGEX.search(docstring)
                if not dep_match and docstring:
                    dep_match = DEPENDS_TAG_REGEX.search(docstring)

                node_name = getattr(node, "name", "")
                node_qual = f"{parent_class[id(node)]}.{node_name}" if id(node) in parent_class else node_name
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
                        "qualname": node_qual,
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
                                "qualname": node_qual,
                                "type": "endpoint",
                                "start_line": start_line,
                                "end_line": end_line,
                                "depends_on": [],
                                "file": str(file_path)
                            })
                            break

        except (SyntaxError, UnicodeDecodeError, ValueError, OSError):
            pass

        return results
