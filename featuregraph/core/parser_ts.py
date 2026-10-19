import re
from pathlib import Path
from typing import Dict, List, Any

from . import lexmask

FEATURE_TAG_REGEX = re.compile(r"@feature\s+\[([A-Za-z0-9_\-]+)\](?:\s+(.*))?", re.IGNORECASE)
DEPENDS_TAG_REGEX = re.compile(r"@depends(?:_on)?\s+\[([A-Za-z0-9_\-,\s]+)\]", re.IGNORECASE)
# Tags are only honoured on comment lines; the comment mask rejects string/template text
COMMENT_LINE_REGEX = re.compile(r"^[ \t]*(?://|/\*|\*|#)")
COMPONENT_EXPORT_REGEX = re.compile(r"export\s+(?:default\s+)?(?:const|function|class)\s+([A-Za-z0-9_]+)", re.MULTILINE)
# End estimate: when the symbol's opening brace closes its (masked) line, brace depth runs
# to the real close — strings, comments and template literals cannot close the block early.
# Everything else (single-line bodies, JSX-paren arrows) keeps the fixed lookahead window.
# ponytail: exact JSX ranges need tree-sitter; the window is the honest ceiling until then.
TS_END_LINE_LOOKAHEAD = 35  # fallback max-lines window when no block brace is found


def _ts_symbol_end(code_lines: List[str], start_idx: int, fallback_end: int) -> int:
    """1-based inclusive end of the block opening in the symbol's header lines.

    The opener must end its masked line; depth then runs to the matching close.
    Returns fallback_end when no opener is found or the block never closes.
    """
    opener = None
    for i in range(start_idx, min(start_idx + 4, len(code_lines))):
        if code_lines[i].rstrip().endswith("{"):
            opener = i
            break
    if opener is None:
        return fallback_end
    depth = 0
    for i in range(opener, len(code_lines)):
        depth += code_lines[i].count("{") - code_lines[i].count("}")
        if depth <= 0:
            return i + 1
    return fallback_end

# CommonJS extractor. Untagged .js files get synthetic feature IDs for their
# declarations/exports; explicit @feature tags keep the existing tag-only path above.
CJS_CLASS_REGEX = re.compile(r"(?m)^[ \t]*(?:module\.exports\s*=\s*)?class\s+([A-Za-z_$][\w$]*)")
CJS_FUNCTION_REGEX = re.compile(r"(?m)^[ \t]*(?:module\.exports\s*=\s*)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")
CJS_ARROW_REGEX = re.compile(
    r"(?m)^[ \t]*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)"
)
CJS_PROTOTYPE_REGEX = re.compile(
    r"(?m)^[ \t]*([A-Za-z_$][\w$]*)\.prototype\.([A-Za-z_$][\w$]*)\s*="
)
CJS_EXPORT_MEMBER_REGEX = re.compile(
    r"(?m)^[ \t]*(?:module\.)?exports\.([A-Za-z_$][\w$]*)\s*="
)
CJS_EXPORT_OBJECT_REGEX = re.compile(r"module\.exports\s*=\s*\{")
CJS_CLASS_MEMBER_REGEX = re.compile(
    r"^[ \t]*(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?"
    r"([A-Za-z_$][\w$]*)\s*\("
)
CJS_CLASS_FIELD_REGEX = re.compile(
    r"^[ \t]*(?:static\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?"
    r"(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
)
CJS_OBJECT_PROPERTY_REGEX = re.compile(
    r"^[ \t]*(?:async\s+)?(?:get\s+|set\s+)?([A-Za-z_$][\w$]*)\s*(?:\(|:|,|$)"
)
CJS_SKIP_MEMBER_NAMES = {
    "if", "for", "while", "switch", "catch", "function", "return", "new",
    "constructor", "do", "else", "try", "with",
}


def _cjs_brace_end(code_lines: List[str], start_idx: int) -> int:
    """Line after the block that opens at/after start_idx (0-indexed)."""
    depth = 0
    opened = False
    for i in range(start_idx, len(code_lines)):
        line = code_lines[i]
        opens = line.count("{")
        closes = line.count("}")
        if opens:
            opened = True
        depth += opens - closes
        if opened and depth <= 0:
            return i + 1
    return min(start_idx + 40, len(code_lines))


def _cjs_value_end(code_lines: List[str], start_idx: int) -> int:
    """End line for an assignment whose value may be a block or concise expression."""
    line = code_lines[start_idx]
    if "{" in line or re.search(r"\b(?:function|class)\b", line):
        return _cjs_brace_end(code_lines, start_idx)
    if "=>" in line:
        for i in range(start_idx, min(start_idx + 10, len(code_lines))):
            if ";" in code_lines[i] or code_lines[i].rstrip().endswith(","):
                return i + 1
        return start_idx + 1
    return start_idx + 1


def _cjs_human(name: str) -> str:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ")
    return name[:1].upper() + name[1:]


def _cjs_auto_symbols(file_path: Path, code: str) -> List[Dict[str, Any]]:
    """Extract classes/functions/methods/export names from masked CommonJS code."""
    lines = code.splitlines()
    found: List[Dict[str, Any]] = []

    def add(name: str, kind: str, start: int, end: int, qualname: str = ""):
        found.append({
            "feature_id": "",
            "name": _cjs_human(name),
            "symbol": name,
            "qualname": qualname or name,
            "type": kind,
            "start_line": start,
            "end_line": end,
            "depends_on": [],
            "auto": True,
        })

    class_ranges = []
    for match in CJS_CLASS_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        end = _cjs_brace_end(lines, start)
        class_ranges.append((match.group(1), start, end))
        add(match.group(1), "class", start + 1, end, match.group(1))

    for class_name, start, end in class_ranges:
        depth = 0
        opened = False
        for i in range(start, end):
            line = lines[i]
            if not opened:
                depth += line.count("{") - line.count("}")
                opened = "{" in line
                continue
            if depth == 1:
                match = CJS_CLASS_MEMBER_REGEX.match(line)
                if not match:
                    match = CJS_CLASS_FIELD_REGEX.match(line)
                if match:
                    name = match.group(1)
                    if name not in CJS_SKIP_MEMBER_NAMES:
                        add(name, "method", i + 1, _cjs_value_end(lines, i), f"{class_name}.{name}")
            depth += line.count("{") - line.count("}")

    for match in CJS_FUNCTION_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        add(match.group(1), "function", start + 1, _cjs_value_end(lines, start), match.group(1))

    for match in CJS_ARROW_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        add(match.group(1), "function", start + 1, _cjs_value_end(lines, start), match.group(1))

    for match in CJS_PROTOTYPE_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        add(match.group(2), "method", start + 1, _cjs_value_end(lines, start), f"{match.group(1)}.{match.group(2)}")

    for match in CJS_EXPORT_MEMBER_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        add(match.group(1), "export", start + 1, _cjs_value_end(lines, start), match.group(1))

    for match in CJS_EXPORT_OBJECT_REGEX.finditer(code):
        start = code[: match.start()].count("\n")
        end = _cjs_brace_end(lines, start)
        depth = 0
        for i in range(start, end):
            line = lines[i]
            if i != start and depth == 1:
                prop = CJS_OBJECT_PROPERTY_REGEX.match(line)
                if prop and prop.group(1) not in CJS_SKIP_MEMBER_NAMES:
                    end_line = _cjs_value_end(lines, i)
                    add(prop.group(1), "export", i + 1, end_line, prop.group(1))
            depth += line.count("{") - line.count("}")

    # Export aliases point at an already-extracted function/class; keep one feature per symbol.
    seen = {item["symbol"] for item in found if item["type"] != "export"}
    unique = []
    seen_locations = set()
    for item in found:
        if item["type"] == "export" and item["symbol"] in seen:
            continue
        key = (item["symbol"], item["start_line"], item["qualname"])
        if key not in seen_locations:
            seen_locations.add(key)
            unique.append(item)

    for item in unique:
        item["file"] = str(file_path)
    return unique


# @feature [PARSER_TS-01] Type script feature parser
class TypeScriptFeatureParser:
    """Parses TypeScript/React files to extract UI components, features, and line positions."""

    @staticmethod
    # @feature [PARSER_TS-02] Parse file
    def parse_file(file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            return []

        results = []
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()
            code_lines = lexmask.code_only(content, "js").splitlines()
            comment_lines = lexmask.comment_only(content, "js").splitlines()

            # Find feature tags (comment lines only; template/string text is masked)
            for idx in range(1, len(lines) + 1):
                if not COMMENT_LINE_REGEX.match(lines[idx - 1]):
                    continue
                match = FEATURE_TAG_REGEX.search(comment_lines[idx - 1])
                if match:
                    feat_id = match.group(1).upper()
                    desc = match.group(2) or "UI Feature Component"
                    
                    # Look ahead for component export
                    symbol_name = file_path.stem
                    sym_idx = idx - 1
                    
                    # Check next 6 lines for export statement
                    for sub_idx in range(idx, min(idx + 6, len(lines))):
                        exp_match = COMPONENT_EXPORT_REGEX.search(code_lines[sub_idx])
                        if exp_match:
                            symbol_name = exp_match.group(1)
                            sym_idx = sub_idx
                            break
                    end_line = _ts_symbol_end(
                        code_lines, sym_idx, min(idx + TS_END_LINE_LOOKAHEAD, len(lines))
                    )
                            
                    dep_match = DEPENDS_TAG_REGEX.search("\n".join(comment_lines[max(0, idx - 2):min(len(lines), idx + 3)]))
                    deps = []
                    if dep_match:
                        deps = [d.strip().strip("[]") for d in dep_match.group(1).split(",") if d.strip()]

                    results.append({
                        "feature_id": feat_id,
                        "name": desc.strip(),
                        "symbol": symbol_name,
                        "type": "component",
                        "start_line": idx,
                        "end_line": end_line,
                        "depends_on": deps,
                        "file": str(file_path)
                    })

        except (UnicodeDecodeError, OSError):
            pass

        if not results and file_path.suffix.lower() == ".js":
            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                return []
            masked = lexmask.code_only(content, "js")
            # ponytail: brace-balance gate — syntactically broken JS must not mint features;
            # real syntax validation needs node/tree-sitter.
            if masked.count("{") != masked.count("}"):
                return []
            return _cjs_auto_symbols(file_path, masked)
        return results
