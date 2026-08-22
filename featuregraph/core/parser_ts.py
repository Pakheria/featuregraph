import re
from pathlib import Path
from typing import Dict, List, Any

FEATURE_TAG_REGEX = re.compile(r"@feature\s+\[([A-Za-z0-9_\-]+)\](?:\s+(.*))?", re.IGNORECASE)
DEPENDS_TAG_REGEX = re.compile(r"@depends\s+\[([A-Za-z0-9_\-,\s]+)\]", re.IGNORECASE)
COMPONENT_EXPORT_REGEX = re.compile(r"export\s+(?:const|function|class)\s+([A-Za-z0-9_]+)", re.MULTILINE)
TS_END_LINE_LOOKAHEAD = 35  # max lines scanned forward as component end estimate

class TypeScriptFeatureParser:
    """Parses TypeScript/React files to extract UI components, features, and line positions."""

    @staticmethod
    def parse_file(file_path: Path) -> List[Dict[str, Any]]:
        if not file_path.exists() or not file_path.is_file():
            return []

        results = []
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines()

            # Find feature tags
            for idx, line in enumerate(lines, 1):
                match = FEATURE_TAG_REGEX.search(line)
                if match:
                    feat_id = match.group(1).upper()
                    desc = match.group(2) or "UI Feature Component"
                    
                    # Look ahead for component export
                    symbol_name = file_path.stem
                    end_line = min(idx + TS_END_LINE_LOOKAHEAD, len(lines))
                    
                    # Check next 5 lines for export statement
                    for sub_idx in range(idx, min(idx + 6, len(lines))):
                        exp_match = COMPONENT_EXPORT_REGEX.search(lines[sub_idx])
                        if exp_match:
                            symbol_name = exp_match.group(1)
                            break
                            
                    dep_match = DEPENDS_TAG_REGEX.search("\n".join(lines[max(0, idx - 2):min(len(lines), idx + 3)]))
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

        return results
