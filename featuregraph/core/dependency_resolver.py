from __future__ import annotations

import ast
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

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


def _clean(part: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", part)


def _scope(feat: Dict[str, Any], include_filename: bool = False) -> str:
    raw = str(feat.get("rel_path") or feat.get("file") or "")
    if not raw:
        return ""
    path = Path(raw)
    path = path.with_suffix("") if include_filename else path.parent
    parts = [p for p in path.as_posix().split("/") if p not in ("", ".")]
    return ".".join(_clean(p) for p in parts)


def assign_symbol_ids(features_data: List[Dict[str, Any]]):
    """Bare symbol when unique; deterministic path qualification on collision."""
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for feat in features_data:
        symbol = str(feat.get("symbol", "")).strip()
        if symbol:
            groups[symbol.casefold()].append(feat)

    for group in groups.values():
        symbol = min(_clean(str(feat.get("symbol", ""))) for feat in group)
        if len(group) == 1:
            group[0]["symbol_id"] = symbol
            continue

        for feat in group:
            scope = _scope(feat)
            feat["_symbol_id"] = f"{scope}.{symbol}" if scope else symbol

        counts = Counter(f["_symbol_id"] for f in group)
        for feat in group:
            if counts[feat["_symbol_id"]] > 1:
                scope = _scope(feat, include_filename=True)
                feat["_symbol_id"] = f"{scope}.{symbol}" if scope else symbol

        counts = Counter(f["_symbol_id"] for f in group)
        for feat in group:
            if counts[feat["_symbol_id"]] > 1:
                fid = _clean(str(feat.get("feature_id", ""))).lower() or "feature"
                feat["_symbol_id"] = f"{feat['_symbol_id']}.{fid}"

        counts = Counter(f["_symbol_id"] for f in group)
        for feat in group:
            if counts[feat["_symbol_id"]] > 1:
                start = feat.get("start_line") or (feat.get("lines") or [0])[0]
                feat["_symbol_id"] = f"{feat['_symbol_id']}.{start}"

        for feat in group:
            feat["symbol_id"] = feat.pop("_symbol_id")

    used: Set[str] = set()
    for feat in features_data:
        symbol_id = feat.get("symbol_id")
        if not symbol_id:
            continue
        base = symbol_id
        n = 2
        while symbol_id.casefold() in used:
            symbol_id = f"{base}_{n}"
            n += 1
        feat["symbol_id"] = symbol_id
        used.add(symbol_id.casefold())


def build_symbol_aliases(
    features: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, str], Dict[str, List[Tuple[str, str, str]]]]:
    """Map persisted locations to symbol-id and bare-symbol aliases for CLI lookup."""
    records: List[Dict[str, Any]] = []
    for feat_id, feat in features.items():
        for loc in feat.get("locations", []):
            lines = loc.get("lines") or [loc.get("start_line", 1), loc.get("end_line", 1)]
            records.append({
                "feature_id": feat_id,
                "symbol": loc.get("symbol", ""),
                "symbol_id": loc.get("symbol_id"),
                "rel_path": loc.get("file", ""),
                "start_line": lines[0] if lines else 1,
            })

    if not all(rec.get("symbol_id") for rec in records):
        assign_symbol_ids(records)
    by_id: Dict[str, str] = {}
    by_symbol: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)
    seen: Set[Tuple[str, str]] = set()
    for rec in records:
        symbol_id = rec.get("symbol_id")
        if not symbol_id:
            continue
        feat_id = rec["feature_id"]
        by_id[symbol_id.casefold()] = feat_id
        key = (symbol_id, feat_id)
        if key not in seen:
            seen.add(key)
            by_symbol[str(rec.get("symbol", "")).casefold()].append(
                (symbol_id, feat_id, rec["rel_path"])
            )

    for candidates in by_symbol.values():
        candidates.sort()
    return by_id, by_symbol


# @feature [DEP_RESOLVER-01] Dependency Resolver
class DependencyResolver:
    """Analyzes AST call-sites and token references to automatically infer cross-feature dependencies."""

    def __init__(self):
        # symbol_name -> feature_id (unique names only)
        self.symbol_to_feature: Dict[str, str] = {}
        # "Class.method" -> feature_id (unique qualified names only)
        self.qualname_to_feature: Dict[str, str] = {}
        # symbol_name -> [{symbol_id, feature_id, file}] for collision-aware resolution
        self.symbol_candidates: Dict[str, List[Dict[str, str]]] = {}
        self._qual_seen: Dict[str, str] = {}

    # @feature [DEP_RESOLVER-02] Register symbols
    def register_feature_symbols(self, features_data: List[Dict[str, Any]]):
        """Registers all definitions after parsing so collisions can be qualified globally."""
        assign_symbol_ids(features_data)
        for feat in features_data:
            feat_id = feat.get("feature_id", "").upper()
            symbol = feat.get("symbol", "").strip()
            if not feat_id or not symbol or symbol in IGNORED_SYMBOLS:
                continue
            qual = feat.get("qualname") or symbol
            self.symbol_candidates.setdefault(symbol, []).append({
                "symbol_id": feat.get("symbol_id") or symbol,
                "feature_id": feat_id,
                "file": str(feat.get("file") or feat.get("rel_path") or ""),
            })
            self._register_qualname(qual, feat_id)

        for symbol, candidates in self.symbol_candidates.items():
            feature_ids = {c["feature_id"] for c in candidates}
            if len(feature_ids) == 1:
                self.symbol_to_feature[symbol] = next(iter(feature_ids))

    def _register_qualname(self, name: str, feat_id: str):
        """Qualified names stay unique; competing definitions resolve only by exact name."""
        if name in self._qual_seen:
            if self._qual_seen[name] != feat_id:
                self.qualname_to_feature.pop(name, None)
        else:
            self._qual_seen[name] = feat_id
            self.qualname_to_feature[name] = feat_id

    def _resolve_bare(self, symbol: str, caller_file: str) -> Optional[str]:
        """Resolve a bare name by path affinity; ties are left unresolved, not guessed."""
        target = self.symbol_to_feature.get(symbol)
        if target:
            return target
        candidates = self.symbol_candidates.get(symbol)
        if not candidates:
            return None

        caller = Path(caller_file)

        def rank(candidate: Dict[str, str]) -> Tuple[int, int]:
            candidate_file = Path(candidate["file"])
            if candidate_file == caller:
                return (2, 0)
            if candidate_file.parent == caller.parent:
                return (1, 0)
            common = 0
            for a, b in zip(candidate_file.parent.parts, caller.parent.parts):
                if a != b:
                    break
                common += 1
            return (0, common)

        by_feature: Dict[str, Tuple[Tuple[int, int], Dict[str, str]]] = {}
        for candidate in candidates:
            feat_id = candidate["feature_id"]
            score = rank(candidate)
            existing = by_feature.get(feat_id)
            if existing is None or (score, candidate["symbol_id"]) > (existing[0], existing[1]["symbol_id"]):
                by_feature[feat_id] = (score, candidate)

        ranked = sorted(
            by_feature.values(),
            key=lambda item: (item[0], item[1]["symbol_id"]),
            reverse=True,
        )
        best_score, best = ranked[0]
        if len(ranked) > 1 and ranked[1][0] == best_score:
            return None
        if best_score == (0, 0):
            return None
        return best["feature_id"]

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
            self._resolve_python(content, features_in_file, results, file_path)
        else:
            self._resolve_tokens(content, features_in_file, results, file_path, lexmask.lang_for_suffix(ext))

        return results

    def _resolve_python(
        self, content: str, features_in_file: List[Dict[str, Any]], results: Dict[str, Set[str]],
        file_path: Path,
    ):
        """Uses Python AST to extract exact call-sites in a single pass."""
        try:
            tree = ast.parse(content)
        except Exception:
            # Fallback to token matching on syntax error
            self._resolve_tokens(content, features_in_file, results, Path(""), "python")
            return

        # Single AST walk per file: (lineno, bare symbol, qualified symbol or "")
        line_symbols: List[Tuple[int, str, str]] = []
        # ponytail: calls only — bare Name references created false edges from local variables;
        # add scope-aware resolution if type-only references need to count.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            lineno = getattr(node, "lineno", None)
            if lineno is None:
                continue
            if isinstance(node.func, ast.Name):
                line_symbols.append((lineno, node.func.id, node.func.id))
            elif isinstance(node.func, ast.Attribute):
                line_symbols.append((lineno, node.func.attr, self._dotted(node.func)))
                root = node.func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name) and root.id not in IGNORED_SYMBOLS:
                    line_symbols.append((lineno, root.id, root.id))

        for feat in features_in_file:
            feat_id = feat["feature_id"]
            start_line = feat["start_line"]
            end_line = feat["end_line"]

            for lineno, sym, qual in line_symbols:
                if start_line <= lineno <= end_line:
                    target_feat = self.qualname_to_feature.get(qual) if qual else None
                    if target_feat is None:
                        target_feat = self._resolve_bare(sym, str(file_path))
                    if target_feat and target_feat != feat_id:
                        results[feat_id].add(target_feat)

    def _resolve_tokens(
        self,
        content: str,
        features_in_file: List[Dict[str, Any]],
        results: Dict[str, Set[str]],
        file_path: Path,
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
                target_feat = self._resolve_bare(tok, str(file_path))
                if target_feat and target_feat != feat_id:
                    results[feat_id].add(target_feat)
