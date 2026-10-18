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

ID generation (deterministic)
    Derives from file path + symbol name, NOT sequence order.
    Two runs on the same codebase produce identical IDs.

    Python:
        path: featuregraph/core/scanner.py  symbol: WorkspaceScanner
        -> category "SCANNER"  slug "SCANNER_WorkspaceScanner"  -> SCANNER_WORKSPACESCANNER-1

    TypeScript/JS:
        path: src/components/AuthButton.tsx  symbol: AuthButton
        -> category "AUTHBUTTON"  slug "AUTHBUTTON"  -> AUTHBUTTON-1

    Per-category dedup counter (SCHEMA-1, SCHEMA-2) increments only when the
    same slug appears multiple times in the same category (same file, two
    functions with identical names — rare but possible).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from . import lexmask
from .scanner import WorkspaceScanner

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


def _has_tag_above(comment_lines: List[str], lineno: int, lookahead: int = 6) -> bool:
    """True if any of the `lookahead` comment lines above lineno contain a @feature tag."""
    start = max(0, lineno - 1 - lookahead)
    chunk = "\n".join(comment_lines[start : lineno - 1])
    return bool(FEATURE_TAG_RE.search(chunk))


def _lexer_lang(lang: str) -> str:
    """Map annotator language names onto lexmask lexers."""
    return "js" if lang == "typescript" else lang


# @feature [ANNOTATOR-02] Suggest python
def _next_feat_id(used: Dict[str, int], cat: str, slug: str) -> str:
    """Return a deterministic feature ID, incrementing a dedup counter if needed."""
    counter = used.setdefault(f"{cat}:{slug}", 0) + 1
    used[f"{cat}:{slug}"] = counter
    if counter == 1:
        return f"{cat.upper()}-{slug.upper()}"
    return f"{cat.upper()}-{slug.upper()}-{counter - 1:02d}"


def suggest_python(file_path: Path, root: Path, used_ids: Dict[str, int]) -> List[Suggestion]:
    """Return Suggestion objects for un-annotated Python symbols."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree   = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, ValueError):
        return []

    lines   = source.splitlines()
    comment_lines = lexmask.comment_only(source, "python").splitlines()
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

        if _has_tag_above(comment_lines, node.lineno):
            continue  # already tagged

        cat = _category_from_path(rel)
        slug = f"{cat}_{_to_slug(name)}"
        feat_id = _next_feat_id(used_ids, cat, slug)
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
    r"^(?P<indent>[ \t]*)export[ \t]+(?:default[ \t]+)?(?:const|function|class|async[ \t]+function)[ \t]+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


# @feature [ANNOTATOR-03] Suggest typescript
def suggest_typescript(file_path: Path, root: Path, used_ids: Dict[str, int]) -> List[Suggestion]:
    """Return Suggestion objects for un-annotated TypeScript/JS exports."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    lines   = content.splitlines()
    code    = lexmask.code_only(content, "js")
    comment_lines = lexmask.comment_only(content, "js").splitlines()
    rel     = file_path.relative_to(root)
    results = []

    for match in _TS_EXPORT_RE.finditer(code):
        # Compute 1-indexed line number of this match
        lineno = code[: match.start()].count("\n") + 1
        name   = match.group("name")
        indent = match.group("indent")

        if _has_tag_above(comment_lines, lineno, lookahead=4):
            continue

        cat = _category_from_path(rel)
        slug = f"{cat}_{_to_slug(name)}"
        feat_id = _next_feat_id(used_ids, cat, slug)
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
    r"^(?P<indent>[ \t]*)(?:(?:public|private|protected|static|async|fn|func|function|def|class|struct|interface|impl|enum|type)[ \t]+)+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def suggest_generic(file_path: Path, root: Path, used_ids: Dict[str, int]) -> List[Suggestion]:
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
    code = lexmask.code_only(content, lang)
    comment_lines = lexmask.comment_only(content, lang).splitlines()

    for match in _GENERIC_DECL_RE.finditer(code):
        lineno = code[: match.start()].count("\n") + 1
        name = match.group("name")
        indent = match.group("indent")

        if _has_tag_above(comment_lines, lineno, lookahead=4):
            continue

        cat = _category_from_path(rel)
        slug = f"{cat}_{_to_slug(name)}"
        feat_id = _next_feat_id(used_ids, cat, slug)
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


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _atomic_write(file_path: Path, text: str) -> None:
    """Replace *file_path* through a same-directory temp file so a crash cannot truncate it."""
    tmp = file_path.with_name(f".{file_path.name}.fg-tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.chmod(tmp, file_path.stat().st_mode)
        os.replace(tmp, file_path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _feature_ids(file_path: Path) -> set:
    """Return the feature IDs the scanner would see in this file right now."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".py":
            from .parser_py import PythonFeatureParser
            parsed = PythonFeatureParser.parse_file(file_path)
        elif suffix in {".ts", ".tsx", ".js", ".jsx"}:
            from .parser_ts import TypeScriptFeatureParser
            parsed = TypeScriptFeatureParser.parse_file(file_path)
        else:
            from .parser_generic import GenericFeatureParser
            parsed = GenericFeatureParser.parse_file(file_path)
    except Exception:
        return set()
    return {f["feature_id"] for f in parsed}


# @feature [ANNOTATOR-04] Apply suggestions
def apply_suggestions(suggestions: List[Suggestion]) -> Dict[Path, int]:
    """
    Write `# @feature` / `// @feature` tags into source files.

    Inserts one line immediately before each suggested symbol.  Suggestions
    whose insertion point is not code are skipped, files are replaced
    atomically, and every write is re-parsed: if a tag does not survive the
    round trip the original file is restored.

    Returns mapping of {file: count_written}.
    """
    # Group by file
    by_file: Dict[Path, List[Suggestion]] = {}
    for s in suggestions:
        by_file.setdefault(s.file, []).append(s)

    written: Dict[Path, int] = {}

    for file_path, file_suggestions in by_file.items():
        try:
            original = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = original.splitlines(keepends=True)
        starts = [0]
        for line in lines:
            starts.append(starts[-1] + len(line))
        cls = lexmask.classify(original, _lexer_lang(file_suggestions[0].lang))

        # Sort descending by line so we insert from bottom; avoids offset drift
        file_suggestions.sort(key=lambda s: s.line, reverse=True)

        count = 0
        inserted = set()
        for sg in file_suggestions:
            insert_at = sg.line - 1  # 0-indexed
            if not 0 <= insert_at < len(lines):
                _warn(f"{file_path}:{sg.line}: skipped {sg.feature_id} (line out of range)")
                continue
            line = lines[insert_at]
            lead = len(line) - len(line.lstrip())
            pos = starts[insert_at] + lead
            if line.strip() and (pos >= len(cls) or cls[pos] != lexmask.CODE):
                _warn(f"{file_path}:{sg.line}: skipped {sg.feature_id} (insertion point is not code)")
                continue
            prefix  = _comment_prefix(sg.lang)
            tag_line = f"{sg.indent}{prefix} @feature [{sg.feature_id}] {sg.name}\n"
            lines.insert(insert_at, tag_line)
            inserted.add(sg.feature_id)
            count += 1

        if not count:
            continue

        before = _feature_ids(file_path)
        try:
            _atomic_write(file_path, "".join(lines))
        except OSError as exc:
            _warn(f"{file_path}: write failed ({exc}); file left unchanged")
            continue

        got = _feature_ids(file_path)
        if not (inserted <= got <= before | inserted):
            _atomic_write(file_path, original)
            _warn(f"{file_path}: re-parse verification failed; restored original")
            continue

        written[file_path] = count

    return written


# ──────────────────────────────────────────────────────────────────────────────
# Public API — orchestrator used by CLI
# ──────────────────────────────────────────────────────────────────────────────

# @feature [ANNOTATOR-05] Collect suggestions
def collect_suggestions(
    root: Path,
    extra_ignore: Optional[set] = None,
) -> List[Suggestion]:
    """
    Walk *root*, find all un-annotated Python/TS/JS symbols, return Suggestions.

    File selection matches WorkspaceScanner: git repo file lists are used when
    available (so .gitignore'd trees are skipped), and .featureignore is honoured.

    IDs are derived deterministically from file path + symbol name so that two
    runs on the same codebase produce the same IDs.  Per-category dedup counters
    increment only when identical slugs collide.

    The returned list is ordered: Python files first, then TS/JS, both groups
    sorted by (file, line) ascending — ready for pretty printing.
    """
    scanner = WorkspaceScanner(root)
    scanner.ignore_patterns |= set(extra_ignore or set())
    used_ids: Dict[str, int] = {}  # "cat:slug" -> count
    all_suggestions: List[Suggestion] = []

    for path_obj in scanner.iter_files():
        if path_obj.suffix == ".py":
            sug = suggest_python(path_obj, root, used_ids)
            sug.sort(key=lambda s: s.line)
            all_suggestions.extend(sug)
        elif path_obj.suffix in {".ts", ".tsx", ".js", ".jsx"}:
            sug = suggest_typescript(path_obj, root, used_ids)
            sug.sort(key=lambda s: s.line)
            all_suggestions.extend(sug)
        else:
            from .parser_generic import GenericFeatureParser
            if GenericFeatureParser.is_supported(path_obj):
                sug = suggest_generic(path_obj, root, used_ids)
                sug.sort(key=lambda s: s.line)
                all_suggestions.extend(sug)

    return all_suggestions
