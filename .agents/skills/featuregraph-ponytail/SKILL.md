---
name: featuregraph-ponytail
description: >-
  Ponytail review skill for the featuregraph codebase. Knows the project's
  specific anti-patterns, past fixes, and rules for keeping the codebase lean.
  Activate when reviewing new PRs, refactors, or additions to featuregraph.
---

# FeatureGraph Ponytail Review Skill

Review new code in this repo for over-engineering only — not correctness.
One line per finding: `L<line>: <tag> <what to cut>. <replacement>.`

Tags: `delete` (dead code), `stdlib` (reinvented stdlib), `native` (dep doing what platform does), `yagni` (abstraction with one impl), `shrink` (same logic, fewer lines).

End with **net lines removable**. If nothing to cut: *Lean already. Ship.*

---

## Project-Specific Rules

These patterns were found and fixed in featuregraph. Flag them immediately if they reappear.

### Parsers (`parser_py.py`, `parser_ts.py`)

| Pattern | Rule |
|---|---|
| `except Exception: pass` | **Never.** Use `(SyntaxError, UnicodeDecodeError, ValueError)` for py parser; `(UnicodeDecodeError, OSError)` for ts parser. |
| `getattr(node, "lineno", 1)` after `isinstance` guard | Dead fallback — `FunctionDef/AsyncFunctionDef/ClassDef` always have `lineno`/`end_lineno` in Python 3.8+. Use direct attribute access. |
| `Path(file_path).stem` when `file_path: Path` | Re-wrap is redundant. Use `file_path.stem`. |
| Magic number lookahead (e.g. `idx + 35`) | Extract as module-level named constant with comment. |
| Unused imports (`Optional`, `Generator`, etc.) | Only import what's actually used in type hints. |

### Scanner (`scanner.py`)

| Pattern | Rule |
|---|---|
| Dot-dirs in `DEFAULT_IGNORE` | `_should_ignore_dir` hard-blocks all dot-dirs via `startswith(".")`. Any `.xxx` entry in `DEFAULT_IGNORE` is dead. |
| `any(name.startswith(ign) for ign in patterns)` | `name in patterns` set lookup is O(1) and sufficient. The `startswith` loop is speculative generality. |
| `file != ".featureignore"` exemption in scan | `.featureignore` has no feature tags; suffix check drops it anyway. The exemption is dead. |
| `detect_subprojects()` called unconditionally | Only call in the code path that uses the result (non-quiet mode). |

### CLI (`cli.py`)

| Pattern | Rule |
|---|---|
| `if not args.command or args.command == "scan"` | Split: bare → `parser.print_help(); sys.exit(0)`. `scan` → own `if args.command == "scan"` block. |
| Hardcoded `"version": "0.1.0"` in formatter | Use `importlib.metadata.version("featuregraph")` with `except Exception: _VERSION = "unknown"` fallback. |

### Formatters

| Pattern | Rule |
|---|---|
| Silent slice truncations (`[:4]`, `[:40]`) | Always comment intent: `# cap at 4 per feature to keep table scannable`. |
| `from typing import Dict, List, Any, Set` in Python 3.10+ files | Replace with `from __future__ import annotations`. |

---

## Fix History

| Commit | What was fixed |
|---|---|
| `f1306c8` | Python 3.12 AST docstring TypeError, dot-dir yagni, O(1) ignore check, DRY parser loop, exception tightening |
| `2ed03c1` | Unused imports, dead `getattr` fallbacks, `Path()` re-wrap, `except Exception`, magic `35`, dynamic version, truncation comments, bare-scan UX, vanity `detect_subprojects()` call |
