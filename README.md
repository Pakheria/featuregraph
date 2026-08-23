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

1. **Token Efficiency (Context Budget):** Replaces massive code dumps with a compact line-indexed map (`< 150` to `~3,500` tokens total — **90% to 95%+ savings**).
2. **Automated AST Call-Graph Dependency Resolution:** Automatically detects function calls, type references, and component usages to wire `depends_on` and `called_by` with zero manual effort.
3. **Line-Exact Slicing (`#Lstart-Lend`):** Directs the AI to read and edit *only* the specific lines of the target feature.
4. **Sub-Second to Fast Scan Speed:** Optimized single-pass line-interval AST mapping scans thousands of symbols in seconds.

```text
AI Coding Agent / Developer
            │
            ▼
 [1. Reads FEATURE_INDEX.json] ───> Compact Map (<150–3,500 tokens)
            │
            ▼
 [2. Finds Target Line Span & Automated [depends_on] Callers]
            │
            ▼
 [3. Slices Exact Code Only (#Lstart-Lend)] ──> 90-95% Token Savings
            │
            ▼
 [4. Commits Code] ───────────────> Git Hook Auto-Syncs Line Map
```

---

## 📊 FeatureGraph vs. Traditional Graph Tools

| Dimension | Traditional Graph Tools (e.g. Graphify) | **FeatureGraph** |
| :--- | :--- | :--- |
| **Dependency Resolution** | ❌ None or Manual only | **✅ Automated AST 2-Pass Call-Graph Inference** |
| **Small Repo Index Size (20–50 features)** | 2MB – 5MB (`graph.json`) | **2KB – 25KB (`FEATURE_INDEX.json`)** |
| **Enterprise Repo Size (200–500+ features)** | 10MB – 25MB+ | **100KB – 350KB (`FEATURE_INDEX.json`)** |
| **Token Cost to Read Index** | ~50,000 to 500,000+ tokens | **< 150 to 4,500 tokens (95%+ savings)** |
| **Line-Level Slicing** | ❌ File-level only | **✅ Exact Line Spans (`#Lstart-Lend`)** |
| **Auto-Suggest & Write Tags** | ❌ Manual only | **✅ `featuregraph annotate` AST generator** |
| **Out-of-the-Box AI Agent Skills** | ❌ None | **✅ Auto-installs to Antigravity, Claude Code, Cursor** |
| **Multi-Language Support** | Limited | **✅ Python, TS/JS, Go, Rust, Java, C#, PHP, Ruby, etc.** |
| **Zero-Config Git Auto-Sync**| ❌ Manual re-runs | **✅ Instant Pre-Commit Git Hook** |
| **Interactive HTML Visualizer**| Basic | **✅ Interactive Standalone Canvas DAG** |

---

## 🧠 Automated AST Dependency Resolution

FeatureGraph does **not** require manual `@depends` comments to build a real dependency graph:

1. **Pass 1 (Symbol Indexing):** Scans all codebase files and maps defined functions, classes, and components to their Feature IDs.
2. **Pass 2 (AST Call-Site Inference):** Analyzes call-sites, type references, and JSX usage inside each feature's line boundaries.
3. **Graph Topology:** Automatically wires `depends_on` and `called_by` edges and generates interactive Mermaid DAGs in `SYSTEM_FEATURE_GRAPH.md`.

---

## 🚀 Installation & Quickstart

### 1. Install via pip / uv
```bash
pip install featuregraph
# or with uv:
uv tool install featuregraph
```

### 2. Initialize in Your Repository
```bash
cd your-project
featuregraph init
```
*This command:*
- Scans your codebase and generates `FEATURE_INDEX.json` & `SYSTEM_FEATURE_GRAPH.md`
- Creates the **`AGENTS.md` AI Circuit-Breaker Constitution**
- Installs the workspace AI agent skill (`.agents/skills/featuregraph/SKILL.md`)
- Installs the `.git/hooks/pre-commit` hook (if in a git repository)

### 3. Install Global AI Agent Skills (Multi-IDE / Multi-CLI)
```bash
featuregraph skill --global
```
*Installs the `/featuregraph` skill out-of-the-box across your environment:*
- **Google Antigravity & Gemini CLI** (`~/.gemini/config/skills/featuregraph/SKILL.md`)
- **Anthropic Claude Code** (`~/.claude/skills/featuregraph/SKILL.md`)
- **Cursor IDE** (`~/.cursor/skills/featuregraph/SKILL.md`)

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

# Install or print AI agent skills
featuregraph skill --install         # install workspace skill (.agents/skills/featuregraph)
featuregraph skill --global          # install globally (~/.gemini, ~/.claude, ~/.cursor)
featuregraph skill --show            # output SKILL.md definition

# Generate an interactive visual HTML DAG
featuregraph visualize --out graph.html

# Manage automated pre-commit hook
featuregraph hook --install
featuregraph hook --uninstall
```

---

## 🤖 AI Agent Integration Protocol

When using FeatureGraph with AI coding agents (Antigravity, Claude Code, Gemini CLI, Cursor):

1. **Auto-Discovery**: Agents discover the `/featuregraph` skill either from the repository (`.agents/skills/`) or their global configuration.
2. **Circuit-Breaker Directive**: `AGENTS.md` instructs the agent to read `FEATURE_INDEX.json` on turn 1 rather than performing expensive recursive directory listings.
3. **Exact Line Slicing**: The agent reads **only** the target feature's `#Lstart-Lend` span, preventing hallucinations and accidental deletion of cross-cutting invariants.

---

## 📄 License
MIT © [ProximaLink](https://proximalink.pk) / [Faizan Haroon](https://github.com/Pakheria)
