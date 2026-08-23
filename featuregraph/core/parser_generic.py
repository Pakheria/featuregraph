from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Any, Optional

FEATURE_TAG_REGEX = re.compile(r"@feature\s+\[([A-Za-z0-9_\-]+)\](?:\s+(.*))?", re.IGNORECASE)
DEPENDS_TAG_REGEX = re.compile(r"@depends\s+\[([A-Za-z0-9_\-,\s]+)\]", re.IGNORECASE)

# Declarations for symbol extraction
C_STYLE_DECL_REGEX = re.compile(
    r"(?:(?:public|private|protected|static|async|fn|func|function|def|class|struct|interface|impl|enum|type)\s+)+([A-Za-z0-9_]+)",
    re.IGNORECASE
)

# Route patterns across frameworks
GENERIC_ROUTE_REGEX = re.compile(
    r"(?:@(?:Get|Post|Put|Delete|Patch|Request)Mapping|"
    r"\[(?:Http|Route)[A-Za-z0-9_\(\)\"\s/]+\]|"
    r"#\[(?:get|post|put|delete|patch|route)\(|"
    r"(?:Route|router|r|e|http)\.(?:get|post|put|delete|patch|HandleFunc|Handle)\(|"
    r"(?:get|post|put|delete|patch)\s+['\"]/)",
    re.IGNORECASE
)

SUPPORTED_EXTENSIONS = {
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # Java / Kotlin
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    # C# / .NET
    ".cs": "csharp",
    # C / C++
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c_header",
    ".hpp": "cpp_header",
    # PHP
    ".php": "php",
    # Ruby
    ".rb": "ruby",
    # Swift / Dart
    ".swift": "swift",
    ".dart": "dart",
    # Shell
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}


# @feature [PARSER_GENERIC-01] Generic Feature Parser
class GenericFeatureParser:
    """Universal parser for Go, Rust, Java, C#, C/C++, PHP, Ruby, Swift, Dart, and Shell."""

    @staticmethod
    def is_supported(file_path: Path) -> bool:
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS

    @staticmethod
    def parse_file(file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            return []

        results: List[Dict[str, Any]] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except (UnicodeDecodeError, OSError):
            return []

        ext = file_path.suffix.lower()
        lang = SUPPORTED_EXTENSIONS.get(ext, "generic")

        for idx, line in enumerate(lines, 1):
            feat_match = FEATURE_TAG_REGEX.search(line)
            if not feat_match:
                # Also check for web framework route annotations/decorators
                route_match = GENERIC_ROUTE_REGEX.search(line)
                if route_match:
                    # Look forward 1-3 lines for function declaration
                    symbol_name = ""
                    start_line = idx
                    end_line = idx + 15
                    for forward_i in range(idx - 1, min(len(lines), idx + 3)):
                        decl_match = C_STYLE_DECL_REGEX.search(lines[forward_i])
                        if decl_match:
                            symbol_name = decl_match.group(1)
                            start_line = forward_i + 1
                            end_line = GenericFeatureParser._find_block_end(lines, forward_i, lang)
                            break
                    if symbol_name:
                        results.append({
                            "feature_id": f"ROUTE-{symbol_name.upper()}",
                            "name": f"API Endpoint `{symbol_name}` ({route_match.group(0)})",
                            "symbol": symbol_name,
                            "type": "endpoint",
                            "start_line": start_line,
                            "end_line": end_line,
                            "depends_on": [],
                            "file": str(file_path),
                        })
                continue

            feat_id = feat_match.group(1).upper()
            desc = (feat_match.group(2) or "").strip() or f"{lang.capitalize()} Feature"

            # Check surrounding lines for @depends
            context_chunk = "\n".join(lines[max(0, idx - 3): min(len(lines), idx + 3)])
            dep_match = DEPENDS_TAG_REGEX.search(context_chunk)
            deps = []
            if dep_match:
                deps = [d.strip().strip("[]") for d in dep_match.group(1).split(",") if d.strip()]

            # Look forward up to 6 lines to find symbol and block end
            symbol_name = file_path.stem
            symbol_type = "module"
            start_line = idx
            end_line = min(idx + 25, len(lines))

            for forward_i in range(idx, min(len(lines), idx + 6)):
                decl_match = C_STYLE_DECL_REGEX.search(lines[forward_i])
                if decl_match:
                    symbol_name = decl_match.group(1)
                    decl_line_str = lines[forward_i].lower()
                    if any(kw in decl_line_str for kw in ["class", "struct", "interface", "type", "impl"]):
                        symbol_type = "class"
                    else:
                        symbol_type = "function"
                    start_line = forward_i + 1
                    end_line = GenericFeatureParser._find_block_end(lines, forward_i, lang)
                    break

            results.append({
                "feature_id": feat_id,
                "name": desc,
                "symbol": symbol_name,
                "type": symbol_type,
                "start_line": start_line,
                "end_line": end_line,
                "depends_on": deps,
                "file": str(file_path),
            })

        return results

    @staticmethod
    def _find_block_end(lines: List[str], start_idx: int, lang: str) -> int:
        """Finds the ending line number (1-indexed) of a block."""
        total_lines = len(lines)
        if start_idx >= total_lines:
            return total_lines

        # Ruby block tracking (def/class/module ... end)
        if lang == "ruby":
            open_count = 0
            found_start = False
            for i in range(start_idx, total_lines):
                line = lines[i].strip()
                if not line or line.startswith("#"):
                    continue
                if re.match(r"^(?:def|class|module|if|unless|do)\b", line):
                    open_count += 1
                    found_start = True
                if line == "end" or line.endswith(" end"):
                    open_count -= 1
                    if found_start and open_count <= 0:
                        return i + 1
            return min(start_idx + 30, total_lines)

        # Brace matching for C-family languages (Go, Rust, Java, C#, C/C++, PHP, Swift, Dart, Shell)
        brace_count = 0
        found_open = False

        for i in range(start_idx, total_lines):
            line = lines[i]
            # Strip string literals and line comments
            clean_line = re.sub(r"\"[^\"]*\"|'[^']*'|//.*$|#.*$", "", line)
            open_braces = clean_line.count("{")
            close_braces = clean_line.count("}")

            if open_braces > 0:
                found_open = True

            brace_count += open_braces - close_braces

            if found_open and brace_count <= 0:
                return i + 1

        return min(start_idx + 30, total_lines)
