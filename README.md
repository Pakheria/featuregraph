# FeatureGraph ⚡

> **Token-efficient, AST-indexed feature topology maps for AI coding assistants. Eliminates AI amnesia and slashes context token waste by 90%.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Pakheria%2Ffeaturegraph-black?logo=github)](https://github.com/Pakheria/featuregraph)

---

## 🎯 The Problem: Why AI Coding Fails on Large Codebases

1. **AI Amnesia & Accidental Code Deletions**: When an AI assistant (Antigravity, Claude, Gemini, Cursor) scans a file, it cannot see cross-file callers. It assumes unreferenced helper functions or security middleware are "dead code" and deletes or refactors them.
2. **Context Token Exhaustion**: Reading entire 1,000-line files on every turn burns tokens rapidly, drives up LLM costs, and slows turn latency.
3. **Graphify Limitations**: Traditional tools create multi-megabyte semantic graphs (`graph.json > 2MB`) that themselves blow past LLM context limits and lack precise line-range pointers.

---

## ⚡ The Solution: How FeatureGraph Works

FeatureGraph scans your codebase using **Abstract Syntax Trees (AST)** and builds an ultra-compact, line-indexed topology map:

```text
AI Coding Agent / Developer
            │
            ▼
 [1. Reads FEATURE_INDEX.json] ───> Tiny ~3KB index (<150 tokens)
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

## 📊 FeatureGraph vs. Graphify

| Feature | Graphify | **FeatureGraph** |
| :--- | :--- | :--- |
| **Index File Size** | 2MB – 15MB (`graph.json`) | **2KB – 5KB (`FEATURE_INDEX.json`)** |
| **Token Cost to Read Index** | ~50,000+ tokens | **< 150 tokens** |
| **Line-Level Slicing** | ❌ File-level only | **✅ Exact Line Spans (`#Lstart-Lend`)** |
| **Multi-Project Workspaces** | ❌ Flat scans only | **✅ Monorepo / Subproject Auto-Detection** |
| **Zero-Config Git Auto-Sync**| ❌ Manual re-runs | **✅ Instant Pre-Commit Git Hook** |
| **AI Anti-Amnesia Protection**| ❌ Passive graph | **✅ Invariant Contract (`[depends_on]`)** |
| **Agent Constitution (`AGENTS.md`)**| ❌ None | **✅ Auto-generates Token Circuit-Breakers** |
| **Interactive HTML Visualizer**| Basic | **✅ Interactive Standalone Canvas DAG** |

---

## 🚀 Installation & Quickstart

### Install via pip / uv
```bash
pip install featuregraph
# or with uv:
uv tool install featuregraph
```

### Initialize in Your Repository
```bash
cd your-project
featuregraph init
```
*This scans your code, generates `FEATURE_INDEX.json`, `SYSTEM_FEATURE_GRAPH.md`, auto-configures the `AGENTS.md` AI circuit-breaker protocol, and installs the `.git/hooks/pre-commit` hook.*

---

## 🏷️ Annotating Your Code

FeatureGraph parses comments in **Python, TypeScript, JavaScript, and TSX** files.

### Python Example
```python
# @feature [AUTH-01] JWT Cookie Session Gate
# @depends [FIREWALL-01], [RBAC-01]
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validates user session token."""
    return await auth_service.validate(token)
```

### TypeScript / React Example
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
# Scan codebase and update graphs (supports custom directory & output paths)
featuregraph scan
featuregraph scan --dir ./my-project --json index.json --md GRAPH.md --quiet

# Initialize repository, pre-commit hook & AGENTS.md constitution
featuregraph init

# Query exact lines and dependencies for a specific feature ID
featuregraph query AUTH-01

# Generate an interactive visual HTML DAG
featuregraph visualize --out graph.html

# Manage automated pre-commit hook
featuregraph hook --install
featuregraph hook --uninstall
```

---

## 🤖 AI Agent Integration Protocol

When using FeatureGraph with AI coding agents (Antigravity, Claude Code, Gemini CLI, Cursor):

1. FeatureGraph auto-generates an `AGENTS.md` directive at your workspace root.
2. The AI reads `FEATURE_INDEX.json` on turn 1 to find the target feature ID and file `#Lstart-Lend`.
3. The AI reads **only** those specific lines, preventing multi-file exploratory scans and accidental deletions of linked dependencies.

---

## 📄 License
MIT © [ProximaLink](https://proximalink.pk) / [Faizan Haroon](https://github.com/Pakheria)
