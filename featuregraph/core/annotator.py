"""
featuregraph.core.annotator
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Auto-suggest and optionally write `# @feature` tags for un-annotated
Python and TypeScript/JS symbols.

Strategy
--------
1. Walk the workspace (same ignore rules as WorkspaceScanner).
2. For each file, parse symbols that are NOT already tagged.
3. Derive a stable feature ID from the file path + symbol name.
4. Optionally write the tag as the line immediately before the def/class/export.

ID generation (Python)
    path: featuregraph/core/scanner.py  symbol: WorkspaceScanner
    -> category "SCANNER"  seq 01  -> SCANNER-01

ID generation (TS/JS)
    path: src/components/AuthButton.tsx  symbol: AuthButton
    -> AUTHBUTTON-01   (truncated to 20 chars)

Sequence numbers are assigned per-category, monotonically incrementing
across all files processed in one annotate run.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# Types
# ──────────────────────────────────────────────────────────────────────────────

# @feature [ANNOTATOR-01] Suggestion
class Suggestion(NamedTuple):
    file: Path
    line: int          # 1-indexed line *before which* the tag will be inserted
    indent: str        # leading whitespace of the decorated symbol
    feature_id: str
    name: str
    symbol: str
    lang: str          # "python" | "typescript"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

FEATURE_TAG_RE = re.compile(r"@feature\s+\[", re.IGNORECASE)
_SAFE_ID_RE    = re.compile(r"[^A-Z0-9_]")


def _to_slug(text: str, max_len: int = 16) -> str:
    """Convert arbitrary text to an UPPER_ALPHA_NUM slug."""
    upper = text.upper()
    slug  = _SAFE_ID_RE.sub("_", upper).strip("_")
    slug  = re.sub(r"_+", "_", slug)
    return slug[:max_len].strip("_")


def _category_from_path(rel_path: Path) -> str:
    """Derive a feature category token from the file's module path."""
    parts = rel_path.with_suffix("").parts  # drop extension
    # Ignore common top-level noise folders
    skip = {"src", "app", "lib", "components", "pages", "views",
            "featuregraph", "tests", "test", "__init__"}
    meaningful = [p for p in parts if p.lower() not in skip]
    token = meaningful[-1] if meaningful else parts[-1]
    return _to_slug(token, 12)


def _human_name(symbol: str, rel_path: Path) -> str:
    """Make a readable feature name from a camelCase/snake_case symbol."""
    # CamelCase → words
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", symbol)
    # snake_case → words
    name = name.replace("_", " ").strip()
    # Capitalise first word only
    return name.capitalize() or rel_path.stem.capitalize()


# ──────────────────────────────────────────────────────────────────────────────
# Python
# ──────────────────────────────────────────────────────────────────────────────

def _leading_indent(source_lines: List[str], lineno: int) -> str:
    """Return the leading whitespace of the line at 1-indexed lineno."""
    if 1 <= lineno <= len(source_lines):
        line = source_lines[lineno - 1]
        return line[: len(line) - len(line.lstrip())]
    return ""


def _has_tag_above(lines: List[str], lineno: int, lookahead: int = 6) -> bool:
    """True if any of the `lookahead` lines above lineno contain a @feature tag."""
    start = max(0, lineno - 1 - lookahead)
    chunk = "\n".join(lines[start : lineno - 1])
    return bool(FEATURE_TAG_RE.search(chunk))


# @feature [ANNOTATOR-02] Suggest python
def suggest_python(file_path: Path, root: Path, seq_map: Dict[str, int]) -> List[Suggestion]:
    """Return Suggestion objects for un-annotated Python symbols."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree   = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return []

    lines   = source.splitlines()
    rel     = file_path.relative_to(root)
    results = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        # Skip private / dunder helpers
        name = getattr(node, "name", "")
        if name.startswith("_") and not name.startswith("__") or name == "":
            continue
        if name.startswith("__") and name.endswith("__"):
            continue  # dunder methods

        if _has_tag_above(lines, node.lineno):
            continue  # already tagged

        cat = _category_from_path(rel)
        seq_map[cat] = seq_map.get(cat, 0) + 1
        feat_id = f"{cat}-{seq_map[cat]:02d}"
        human   = _human_name(name, rel)
        indent  = _leading_indent(lines, node.lineno)

        results.append(Suggestion(
            file=file_path,
            line=node.lineno,
            indent=indent,
            feature_id=feat_id,
            name=human,
            symbol=name,
            lang="python",
        ))

    # Sort so we insert from bottom to top (keeps line numbers valid)
    results.sort(key=lambda s: s.line, reverse=True)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# TypeScript / JavaScript
# ──────────────────────────────────────────────────────────────────────────────

# Matches: export const/function/class Foo  OR  export default function Foo
_TS_EXPORT_RE = re.compile(
    r"^(?P<indent>\s*)export\s+(?:default\s+)?(?:const|function|class|async\s+function)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


# @feature [ANNOTATOR-03] Suggest typescript
def suggest_typescript(file_path: Path, root: Path, seq_map: Dict[str, int]) -> List[Suggestion]:
    """Return Suggestion objects for un-annotated TypeScript/JS exports."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    lines   = content.splitlines()
    rel     = file_path.relative_to(root)
    results = []

    for match in _TS_EXPORT_RE.finditer(content):
        # Compute 1-indexed line number of this match
        lineno = content[: match.start()].count("\n") + 1
        name   = match.group("name")
        indent = match.group("indent")

        if _has_tag_above(lines, lineno, lookahead=4):
            continue

        cat = _category_from_path(rel)
        seq_map[cat] = seq_map.get(cat, 0) + 1
        feat_id = f"{cat}-{seq_map[cat]:02d}"
        human   = _human_name(name, rel)

        results.append(Suggestion(
            file=file_path,
            line=lineno,
            indent=indent,
            feature_id=feat_id,
            name=human,
            symbol=name,
            lang="typescript",
        ))

    results.sort(key=lambda s: s.line, reverse=True)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Generic Multi-Language (Go, Rust, Java, C#, PHP, Ruby, Swift, Dart, Shell)
# ──────────────────────────────────────────────────────────────────────────────

_GENERIC_DECL_RE = re.compile(
    r"^(?P<indent>\s*)(?:(?:public|private|protected|static|async|fn|func|function|def|class|struct|interface|impl|enum|type)\s+)+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def suggest_generic(file_path: Path, root: Path, seq_map: Dict[str, int]) -> List[Suggestion]:
    """Return Suggestion objects for un-annotated Go, Rust, Java, C#, PHP, Ruby, etc. symbols."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (UnicodeDecodeError, OSError):
        return []

    lines = content.splitlines()
    rel = file_path.relative_to(root)
    results = []

    ext = file_path.suffix.lower()
    from .parser_generic import SUPPORTED_EXTENSIONS
    lang = SUPPORTED_EXTENSIONS.get(ext, "generic")

    for match in _GENERIC_DECL_RE.finditer(content):
        lineno = content[: match.start()].count("\n") + 1
        name = match.group("name")
        indent = match.group("indent")

        if _has_tag_above(lines, lineno, lookahead=4):
            continue

        cat = _category_from_path(rel)
        seq_map[cat] = seq_map.get(cat, 0) + 1
        feat_id = f"{cat}-{seq_map[cat]:02d}"
        human = _human_name(name, rel)

        results.append(Suggestion(
            file=file_path,
            line=lineno,
            indent=indent,
            feature_id=feat_id,
            name=human,
            symbol=name,
            lang=lang,
        ))

    results.sort(key=lambda s: s.line, reverse=True)
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Writer
# ──────────────────────────────────────────────────────────────────────────────

def _comment_prefix(lang: str) -> str:
    if lang in {"python", "ruby", "shell"}:
        return "#"
    return "//"


# @feature [ANNOTATOR-04] Apply suggestions
def apply_suggestions(suggestions: List[Suggestion]) -> Dict[Path, int]:
    """
    Write `# @feature` / `// @feature` tags into source files.

    Inserts one line before each suggested symbol.  Processes each file's
    suggestions from bottom to top so line numbers stay accurate.

    Returns mapping of {file: count_written}.
    """
    # Group by file
    by_file: Dict[Path, List[Suggestion]] = {}
    for s in suggestions:
        by_file.setdefault(s.file, []).append(s)

    written: Dict[Path, int] = {}

    for file_path, file_suggestions in by_file.items():
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except (OSError, UnicodeDecodeError):
            continue

        # Sort descending by line so we insert from bottom; avoids offset drift
        file_suggestions.sort(key=lambda s: s.line, reverse=True)

        count = 0
        for sg in file_suggestions:
            prefix  = _comment_prefix(sg.lang)
            tag_line = f"{sg.indent}{prefix} @feature [{sg.feature_id}] {sg.name}\n"
            insert_at = sg.line - 1  # 0-indexed
            lines.insert(insert_at, tag_line)
            count += 1

        file_path.write_text("".join(lines), encoding="utf-8")
        written[file_path] = count

    return written


# ──────────────────────────────────────────────────────────────────────────────
# Public API — orchestrator used by CLI
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_IGNORE = {
    "venv", "node_modules", "dist", "build",
    "__pycache__", "logs", "coverage", ".git",
}


# @feature [ANNOTATOR-05] Collect suggestions
def collect_suggestions(
    root: Path,
    extra_ignore: Optional[set] = None,
) -> List[Suggestion]:
    """
    Walk *root*, find all un-annotated Python/TS/JS symbols, return Suggestions.

    The returned list is ordered: Python files first, then TS/JS, both groups
    sorted by (file, line) ascending — ready for pretty printing.
    """
    ignore = DEFAULT_IGNORE | (extra_ignore or set())
    seq_map: Dict[str, int] = {}
    all_suggestions: List[Suggestion] = []

    for path_obj in sorted(root.rglob("*")):
        if not path_obj.is_file():
            continue
        # Check if any ancestor is ignored
        rel_parts = set(path_obj.relative_to(root).parts[:-1])
        if rel_parts & ignore:
            continue
        if any(p.startswith(".") for p in path_obj.relative_to(root).parts):
            continue

        if path_obj.suffix == ".py":
            sug = suggest_python(path_obj, root, seq_map)
            sug.sort(key=lambda s: s.line)
            all_suggestions.extend(sug)
        elif path_obj.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            sug = suggest_typescript(path_obj, root, seq_map)
            sug.sort(key=lambda s: s.line)
            all_suggestions.extend(sug)
        else:
            from .parser_generic import GenericFeatureParser
            if GenericFeatureParser.is_supported(path_obj):
                sug = suggest_generic(path_obj, root, seq_map)
                sug.sort(key=lambda s: s.line)
                all_suggestions.extend(sug)

    return all_suggestions
