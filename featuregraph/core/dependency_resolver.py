from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any

from . import lexmask

# Common keywords/builtins to ignore during dependency resolution
IGNORED_SYMBOLS = {
    # Python builtins & common keywords
    "str", "int", "float", "bool", "list", "dict", "set", "tuple", "len",
    "print", "range", "enumerate", "isinstance", "issubclass", "getattr",
    "setattr", "hasattr", "open", "super", "min", "max", "sum", "any", "all",
    "filter", "map", "sorted", "reversed", "zip", "type", "id", "self", "cls",
    "None", "True", "False", "Exception", "ValueError", "TypeError", "KeyError",
    "router", "app", "get", "post", "put", "delete", "patch", "response", "request",
    # JS/TS builtins
    "console", "log", "error", "warn", "info", "window", "document", "React",
    "useState", "useEffect", "useCallback", "useMemo", "useRef", "useContext",
    # Go / Rust / Java / C#
    "fmt", "println", "printf", "err", "ctx", "nil", "ok", "Vec", "String",
    "Option", "Result", "System", "out", "Console", "WriteLine", "Task",
}


# @feature [DEP_RESOLVER-01] Dependency Resolver
class DependencyResolver:
    """Analyzes AST call-sites and token references to automatically infer cross-feature dependencies."""

    def __init__(self):
        # symbol_name -> feature_id (unique names only)
        self.symbol_to_feature: Dict[str, str] = {}
        # "Class.method" -> feature_id (unique qualified names only)
        self.qualname_to_feature: Dict[str, str] = {}
        # Names defined by more than one feature — edges on bare names are skipped for these
        self.ambiguous_symbols: Set[str] = set()

    # @feature [DEP_RESOLVER-02] Register symbols
    def register_feature_symbols(self, features_data: List[Dict[str, Any]]):
        """Registers defined symbols to their corresponding feature IDs."""
        for feat in features_data:
            feat_id = feat.get("feature_id", "").upper()
            symbol = feat.get("symbol", "").strip()
            if not feat_id or not symbol or symbol in IGNORED_SYMBOLS:
                continue
            qual = feat.get("qualname") or symbol
            self._register(self.symbol_to_feature, symbol, feat_id)
            self._register(self.qualname_to_feature, qual, feat_id)

    def _register(self, table: Dict[str, str], name: str, feat_id: str):
        """Adds name -> feat_id; competing definitions make the name ambiguous (never guessed)."""
        if name in table:
            if table[name] != feat_id:
                self.ambiguous_symbols.add(name)
                del table[name]
        elif name not in self.ambiguous_symbols:
            table[name] = feat_id

    @staticmethod
    def _dotted(node: ast.AST) -> str:
        """Builds the dotted name of an Attribute chain, e.g. Outer.Inner.method."""
        parts: List[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if not isinstance(node, ast.Name):
            return ""
        parts.append(node.id)
        return ".".join(reversed(parts))

    # @feature [DEP_RESOLVER-03] Resolve dependencies for file
    def resolve_file_dependencies(
        self, file_path: Path, features_in_file: List[Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        Infers dependencies for each feature in the given file.
        Returns: {feature_id: set(dependent_feature_ids)}
        """
        if not features_in_file:
            return {}

        results: Dict[str, Set[str]] = {f["feature_id"]: set() for f in features_in_file}
        ext = file_path.suffix.lower()

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (UnicodeDecodeError, OSError):
            return results

        if ext == ".py":
            self._resolve_python(content, features_in_file, results)
        else:
            self._resolve_tokens(content, features_in_file, results, lexmask.lang_for_suffix(ext))

        return results

    def _resolve_python(
        self, content: str, features_in_file: List[Dict[str, Any]], results: Dict[str, Set[str]]
    ):
        """Uses Python AST to extract exact call-sites and class references in a single pass."""
        try:
            tree = ast.parse(content)
        except Exception:
            # Fallback to token matching on syntax error
            self._resolve_tokens(content, features_in_file, results, "python")
            return

        # Single AST walk per file: (lineno, bare symbol, qualified symbol or "")
        line_symbols: List[Tuple[int, str, str]] = []
        for node in ast.walk(tree):
            lineno = getattr(node, "lineno", None)
            if lineno is not None:
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        line_symbols.append((lineno, node.func.id, node.func.id))
                    elif isinstance(node.func, ast.Attribute):
                        line_symbols.append((lineno, node.func.attr, self._dotted(node.func)))
                elif isinstance(node, ast.Name):
                    line_symbols.append((lineno, node.id, node.id))
                elif isinstance(node, ast.Attribute):
                    line_symbols.append((lineno, node.attr, self._dotted(node)))

        for feat in features_in_file:
            feat_id = feat["feature_id"]
            start_line = feat["start_line"]
            end_line = feat["end_line"]

            for lineno, sym, qual in line_symbols:
                if start_line <= lineno <= end_line:
                    target_feat = self.qualname_to_feature.get(qual) if qual else None
                    if target_feat is None:
                        target_feat = self.symbol_to_feature.get(sym)
                    if target_feat and target_feat != feat_id:
                        results[feat_id].add(target_feat)

    def _resolve_tokens(
        self,
        content: str,
        features_in_file: List[Dict[str, Any]],
        results: Dict[str, Set[str]],
        lang: str = "other",
    ):
        """Extracts identifier calls and references across TS/JS, Go, Rust, Java, C#, etc."""
        lines = lexmask.code_only(content, lang).splitlines()

        for feat in features_in_file:
            feat_id = feat["feature_id"]
            start_idx = max(0, feat["start_line"] - 1)
            end_idx = min(len(lines), feat["end_line"])

            chunk = "\n".join(lines[start_idx:end_idx])
            # Find all identifier tokens
            tokens = set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", chunk))

            for tok in tokens:
                if tok in self.symbol_to_feature:
                    target_feat = self.symbol_to_feature[tok]
                    if target_feat != feat_id:
                        results[feat_id].add(target_feat)
