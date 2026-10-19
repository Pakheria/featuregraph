# FeatureGraph ⚡

> **Token-efficient, AST-indexed feature topology maps with automated call-graph dependency resolution. Eliminates AI amnesia and slashes LLM context waste by 90%+.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Pakheria%2Ffeaturegraph-black?logo=github)](https://github.com/Pakheria/featuregraph)

---

## 🎯 The Core Problem FeatureGraph Solves

1. **AI Amnesia & Accidental Code Deletions:** AI coding assistants (Antigravity, Claude Code, Gemini CLI, Cursor) lack cross-file caller visibility. When editing a function, they frequently assume unreferenced helpers or security gates are "dead code" and break downstream callers.
2. **Context Token Exhaustion:** Feeding entire 1,000-line files on every agent turn wastes tokens, slows turn latency, and degrades reasoning focus.
3. **Traditional Graph Bloat:** Legacy semantic graph tools dump multi-megabyte AST trees (`graph.json` > 10MB – 25MB+) that exceed agent context windows and fail to provide exact line slices.

---

## ⚡ The Solution & Core KPIs

FeatureGraph is engineered around four core metrics:

1. **2-Tier Hierarchical Token Budget:** Compact `manifest.json` (one line per feature — 30–75 bytes per feature, measured) lets agents pinpoint domain categories, then read only that domain's file `categories/<domain>.json` (typically 150–2,000 bytes) before slicing only the target lines.
2. **Automated AST Call-Graph Dependency Resolution:** Automatically detects function/method calls and component usages to wire `depends_on` and `called_by` with zero manual effort.
3. **Line-Range Slicing (`#Lstart-Lend`):** Directs the AI to read and edit *only* the specific lines of the target feature. Python ranges are exact; TS/JS ends are a bounded 35-line estimate.
4. **Sub-Second Scan Speed:** Optimized two-pass AST mapping — 1,000 files scanned in ~0.1 s (measured).

```text
AI Coding Agent / Developer
            │
            ▼
 [1. Reads .featuregraph/manifest.json] ───> Tier-1 directory (1 line per feature)
            │
            ▼
 [2. Reads .featuregraph/categories/<domain>.json] ──> Exact domain map
            │
            ▼
 [3. Slices Exact Code Only (#Lstart-Lend)] ────────> Fraction of full-file token cost
            │
            ▼
 [4. Commits Code] ─────────────────────────────────> Git Hook Auto-Syncs Line Map
```

---

## 📊 FeatureGraph vs. Traditional Graph Tools

| Dimension | Traditional Graph Tools (e.g. Graphify) | **FeatureGraph** |
| :--- | :--- | :--- |
| **Dependency Resolution** | ❌ None or Manual only | **✅ Automated AST 2-Pass Call-Graph Inference** |
| **Small Repo Index Size (20–50 features)** | 1MB – 5MB dense `graph.json` | **5KB – 20KB (`.featuregraph/index.json`)** |
| **Enterprise Repo Index Size (500–5,000+ features)** | 10MB – 25MB+ | **125KB – 2MB (≈0.25–0.4 KB/feature, measured)** |
| **Token Cost to Read Index** | ~50,000 to 500,000+ tokens | **Manifest + one category chunk ≈ 0.03–0.16 KB/feature (measured) — full index never read** |
| **Line-Level Slicing** | ❌ File-level only | **✅ Exact Line Spans (`#Lstart-Lend`)** |
| **Auto-Suggest & Write Tags** | ❌ Manual only | **✅ `featuregraph annotate` tag generator (lexer-guarded)** |
| **Out-of-the-Box AI Agent Skills** | ❌ None | **✅ Auto-installs to Antigravity, Claude Code, Cursor** |
| **Multi-Language Support** | Limited | **✅ Python, TS/JS, Go, Rust, Java, C#, PHP, Ruby, etc.** |
| **Zero-Config Git Auto-Sync**| ❌ Manual re-runs | **✅ Instant Pre-Commit Git Hook** |
| **Visual Architecture DAG**  | Basic | **✅ Native Mermaid Dependency Graph (`graph.md`)** |

### 📏 Index Sizing Across Project Sizes (measured)

| Project | Features | Manifest (Tier 1) | Full index | One category chunk | Scan |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Small mixed test fixture (py/ts/go) | 12 | 0.9 KB | 4 KB | ~0.4 KB | 0.08 s |
| This repository | 35 | 2 KB | 14 KB | ~1 KB (14 categories) | 0.1 s |
| Synthetic 1,000-file repo | 1,000 | 31 KB | 254 KB | 127 KB (only 2 categories) | 0.1 s |

Scaling is linear in feature count: **manifest ≈ 30–75 bytes/feature**, **full index ≈ 0.25–0.4 KB/feature**, **scan ≈ 0.1 s per 1,000 files**. Agents read the manifest plus the single category chunk they need — the full index never enters context. Uniform tags in the synthetic repo concentrate 500 features per category (a worst case); real projects spread features across more domains, shrinking chunks.

---

## 🧠 Automated AST Dependency Resolution

FeatureGraph does **not** require manual `@depends` comments to build a real dependency graph:

1. **Pass 1 (Symbol Indexing):** Scans all codebase files and maps defined functions, classes, and components to feature IDs and deterministic symbol IDs (bare when unique, path-qualified on collision).
2. **Pass 2 (AST Call-Site Inference):** Analyzes call-sites, type references, and JSX usage inside each feature's line boundaries.
3. **Graph Topology:** Automatically wires `depends_on` and `called_by` edges, generates Mermaid DAGs in `.featuregraph/graph.md`, and lists isolated features (no deps, no callers) for dead-code review.
4. **Manual Overrides & Trust Checks:** `@depends` (or `@depends_on`) tags add explicit edges; dangling references are warned about. Colliding symbol names are qualified deterministically (e.g. `web.app.layout` vs `web.app.docs.layout`), and bare calls resolve through the same IDs by path affinity; exact ties are left unresolved, never guessed.

---

## 🚨 Scan Warnings

Warnings are aggregated to one line each per scan:

```bash
⚠ 6 file(s) with no parseable features (untagged or syntax error): src/legacy.py, … (+3 more)
⚠ 1 unresolved @depends reference(s) — no such feature: DANGLE-01 → GHOST-77
```

### Symbol IDs & collisions

A tagged location's symbol ID is its bare symbol when unique (`validate_token`) and a deterministic path prefix on collision (`web.app.layout` vs `web.app.docs.layout`; when even the directory repeats, the full path is used, e.g. `test.bypass_matrix.1_drifted_params.processPayment`). Explicit `@feature [ID]` tags remain the canonical feature ID.

`query` and `search` accept a feature ID, a qualified symbol ID, or an unambiguous bare symbol. An ambiguous bare name exits 1 and lists the candidate qualified IDs. Inferred calls use the same IDs with path affinity (same file > same directory > longest shared path); exact ties are left unresolved, not guessed.

---

## 🏷️ Tag Rules & Coverage Model

A tag only counts on a **real comment line**. All scanners, the annotator, and dependency inference share one lexical mask, so `@feature` or exported symbols inside string literals and template literals are ignored — they can never create phantom features or get annotated.

| Language | Tag placement | Symbol window |
| :--- | :--- | :--- |
| Python | Comment above `def` / `class` (or the docstring) | 6 lines above |
| TypeScript / JS | Comment above the export | 6 lines below the tag |
| Go, Rust, Java, C#, PHP, Ruby, Swift, Dart, Shell | Comment above the declaration | 6 lines below the tag |

Python end lines are exact; TS/JS end lines use a fixed 35-line lookahead and can overshoot or clip long components.

`featuregraph annotate --yes` only inserts at code positions, replaces files atomically, and re-parses every write; if a tag would not round-trip it restores the original file. Untagged symbols are not indexed — `scan` reports files with no parseable features.

---

## ⚡ Fast AST Feature Search

Search symbols and line ranges in <50ms without bloating your context window:

```bash
featuregraph search "parser"
# Output gives exact file paths and surgical #Lstart-Lend ranges:
# • featuregraph/core/parser_py.py #L10-L95 (PythonFeatureParser)

featuregraph query web.app.docs.layout   # qualified symbol ID
featuregraph query layout                # ambiguous -> exit 1 + candidate IDs
```

---

## 🚀 Installation & Quickstart

### 1. Install via pip / uv (Direct from GitHub)
```bash
# Install with pip:
pip install git+https://github.com/Pakheria/featuregraph.git

# Or install globally as an isolated CLI tool with uv:
uv tool install git+https://github.com/Pakheria/featuregraph.git
```

### 2. Initialize in Your Repository
```bash
cd your-project
featuregraph init
```
*This command:*
- Scans your codebase and generates `.featuregraph/index.json` & `.featuregraph/graph.md`
- Creates the **`AGENTS.md` AI Circuit-Breaker Constitution**
- Installs the workspace AI agent skill (`.agents/skills/featuregraph/SKILL.md`)
- Installs the `.git/hooks/pre-commit` hook (if in a git repository)

All artifacts are kept inside a clean `.featuregraph/` directory to prevent cluttering your repository root.

### 3. Install Global AI Agent Skills (Multi-IDE / Multi-CLI)
```bash
featuregraph skill --global
```
*Installs the `/featuregraph` skill out-of-the-box across your environment:*
- **Google Antigravity & Gemini CLI** (`~/.gemini/config/skills/featuregraph/SKILL.md`)
- **Anthropic Claude Code** (`~/.claude/skills/featuregraph/SKILL.md`)
- **Cursor IDE** (`~/.cursor/skills/featuregraph/SKILL.md`)
- **OpenCode** (`~/.config/opencode/skills/featuregraph/SKILL.md`)
- **Shared agent config** (`~/.agents/skills/featuregraph/SKILL.md`)

---

## 🌐 Multi-Language Support & Auto-Annotation

FeatureGraph supports **Python, TypeScript, JavaScript, Go, Rust, Java, Kotlin, C#, C/C++, PHP, Ruby, Swift, Dart, and Shell**.

### Supported Language Matrix

| Language | Extensions | Comment Style |
| :--- | :--- | :--- |
| **Python** | `.py` | `# @feature [ID] Name` |
| **TypeScript / JavaScript** | `.ts`, `.tsx`, `.js`, `.jsx` | `// @feature [ID] Name` |
| **Go** | `.go` | `// @feature [ID] Name` |
| **Rust** | `.rs` | `// @feature [ID] Name` |
| **Java / Kotlin** | `.java`, `.kt`, `.kts` | `// @feature [ID] Name` |
| **C# / .NET** | `.cs` | `// @feature [ID] Name` |
| **C / C++** | `.c`, `.cpp`, `.cc`, `.h`, `.hpp` | `// @feature [ID] Name` |
| **PHP** | `.php` | `// @feature [ID] Name` |
| **Ruby** | `.rb` | `# @feature [ID] Name` |
| **Swift / Dart** | `.swift`, `.dart` | `// @feature [ID] Name` |
| **Shell** | `.sh`, `.bash`, `.zsh` | `# @feature [ID] Name` |

### Auto-Annotating Existing Codebases
If your project is un-annotated, let FeatureGraph suggest and insert tags automatically:

```bash
# Preview suggested tags without touching files (dry-run)
featuregraph annotate --dry-run

# Write suggested @feature tags into source files
featuregraph annotate --yes
```

---

## 🛠️ CLI Reference & Commands

```bash
# Show all commands and options
featuregraph --help

# Initialize repository, pre-commit hook, AGENTS.md constitution & workspace skill
featuregraph init

# Auto-suggest and write @feature tags for un-annotated symbols
featuregraph annotate --dry-run
featuregraph annotate --yes
featuregraph annotate --dir ./src --limit 50 --yes

# Scan codebase, resolve AST call-graph dependencies & update graphs
featuregraph scan
featuregraph scan --dir ./my-project --json index.json --md GRAPH.md --quiet

# Query exact lines and dependencies for a specific feature ID
featuregraph query AUTH-01
featuregraph query AUTH-01 --json            # machine-readable output (agents / CI)
featuregraph search "parser" --dir ./app --json

# Install or print AI agent skills
featuregraph skill --install         # install workspace skill (.agents/skills/featuregraph)
featuregraph skill --global          # install globally (~/.agents, ~/.gemini, ~/.claude, ~/.cursor, ~/.config/opencode)
featuregraph skill --show            # output SKILL.md definition

# Manage automated pre-commit hook
featuregraph hook --install
featuregraph hook --uninstall
```

---

## 🤖 AI Agent Integration Protocol

When using FeatureGraph with AI coding agents (Antigravity, Claude Code, Gemini CLI, Cursor):

1. **Auto-Discovery**: Agents discover the `/featuregraph` skill either from the repository (`.agents/skills/`) or their global configuration.
2. **Circuit-Breaker Directive**: `AGENTS.md` instructs the agent to read `.featuregraph/manifest.json` on turn 1 rather than performing expensive recursive directory listings.
3. **Exact Line Slicing**: The agent reads **only** the target feature's `#Lstart-Lend` span, preventing hallucinations and accidental deletion of cross-cutting invariants.

---

## 📄 License
MIT © [ProximaLink](https://proximalink.pk) / [Faizan Haroon](https://github.com/Pakheria)
