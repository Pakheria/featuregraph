# FeatureGraph ⚡

> **Token-efficient, AST-indexed feature topology maps and AI agent skills. Eliminates AI amnesia and slashes LLM context waste by 90%.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Pakheria%2Ffeaturegraph-black?logo=github)](https://github.com/Pakheria/featuregraph)

---

## 🎯 The Problem: Why AI Coding Fails on Large Codebases

1. **AI Amnesia & Accidental Code Deletions**: When an AI coding agent (Antigravity, Claude Code, Gemini CLI, Cursor) scans a file, it cannot see cross-file callers. It assumes unreferenced helper functions or security middleware are "dead code" and deletes or refactors them.
2. **Context Token Exhaustion**: Reading entire 1,000-line files on every turn burns tokens rapidly, drives up LLM costs, and degrades agent focus.
3. **Traditional Graph Bloat**: Semantic code graphs dump massive AST trees (`graph.json` > 2MB – 25MB) that themselves exceed LLM token budgets and lack line-exact slice references.

---

## ⚡ The Solution: How FeatureGraph Works

FeatureGraph scans your codebase using **Abstract Syntax Trees (AST)** and builds an ultra-compact, line-indexed topology map and out-of-the-box AI agent skills:

```text
AI Coding Agent / Developer
            │
            ▼
 [1. Reads FEATURE_INDEX.json] ───> Tiny ~3KB–100KB index (<150–3,500 tokens)
            │
            ▼
 [2. Finds Target Lines (#Lstart-Lend) & [depends_on] IDs]
            │
            ▼
 [3. Slices Exact Code Only] ────> 85-92% Token Savings
            │
            ▼
 [4. Commits Code] ───────────────> Git Hook Auto-Syncs Line Map
```

---

## 📊 FeatureGraph vs. Traditional Graph Tools

| Dimension | Traditional Graph Tools (e.g. Graphify) | **FeatureGraph** |
| :--- | :--- | :--- |
| **Small Repo Index Size (20–50 features)** | 2MB – 5MB (`graph.json`) | **2KB – 25KB (`FEATURE_INDEX.json`)** |
| **Enterprise Repo Index Size (200–500+ endpoints)** | 10MB – 25MB+ | **100KB – 350KB (`FEATURE_INDEX.json`)** |
| **Token Cost to Read Index** | ~50,000 to 500,000+ tokens | **< 150 to 4,500 tokens (95%+ savings)** |
| **Line-Level Slicing** | ❌ File-level only | **✅ Exact Line Spans (`#Lstart-Lend`)** |
| **Auto-Suggest & Write Tags** | ❌ Manual only | **✅ `featuregraph annotate` AST generator** |
| **Out-of-the-Box AI Agent Skills** | ❌ None | **✅ Auto-installs to Antigravity, Claude Code, Cursor** |
| **Multi-Project Workspaces** | ❌ Flat scans only | **✅ Monorepo / Subproject Auto-Detection** |
| **Zero-Config Git Auto-Sync**| ❌ Manual re-runs | **✅ Instant Pre-Commit Git Hook** |
| **AI Anti-Amnesia Protection**| ❌ Passive graph | **✅ Invariant Contract (`[depends_on]`)** |
| **Agent Constitution (`AGENTS.md`)**| ❌ None | **✅ Auto-generates Token Circuit-Breakers** |
| **Interactive HTML Visualizer**| Basic | **✅ Interactive Standalone Canvas DAG** |

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
- Scans your code and generates `FEATURE_INDEX.json` & `SYSTEM_FEATURE_GRAPH.md`
- Creates the **`AGENTS.md` AI Circuit-Breaker Constitution**
- Installs the workspace AI agent skill (`.agents/skills/featuregraph/SKILL.md`)
- Installs the `.git/hooks/pre-commit` hook (if git repository)

### 3. Install Global AI Agent Skills (Multi-IDE / Multi-CLI)
```bash
featuregraph skill --global
```
*Installs the `/featuregraph` skill out-of-the-box across your environment:*
- **Google Antigravity & Gemini CLI** (`~/.gemini/config/skills/featuregraph/SKILL.md`)
- **Anthropic Claude Code** (`~/.claude/skills/featuregraph/SKILL.md`)
- **Cursor IDE** (`~/.cursor/skills/featuregraph/SKILL.md`)

---

## 🌐 Multi-Language Support & Annotation

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
If your project is un-annotated, let FeatureGraph suggest and insert tags automatically across any supported language:

```bash
# Preview suggested tags without touching files (dry-run)
featuregraph annotate --dry-run

# Write suggested @feature tags into source files
featuregraph annotate --yes
```

### Polyglot Annotation Examples

**Python:**
```python
# @feature [AUTH-01] JWT Cookie Session Gate
# @depends [FIREWALL-01], [RBAC-01]
async def get_current_user(token: str = Depends(oauth2_scheme)):
    return await auth_service.validate(token)
```

**Go:**
```go
// @feature [AUTH-01] JWT Auth Middleware
// @depends [CONFIG-01]
func AuthMiddleware(token string) bool {
    return validateToken(token)
}
```

**Rust:**
```rust
// @feature [CORE-01] Matrix Solver Engine
pub fn solve_matrix(data: &[f64]) -> Vec<f64> {
    data.to_vec()
}
```

**TypeScript / React:**
```tsx
// @feature [DASH-01] Executive Analytics Widget
// @depends [AUTH-01], [API-METRICS]
export const AnalyticsWidget = () => {
  return <div>Metrics View</div>;
};
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

# Scan codebase and update graphs (supports custom directory & output paths)
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
