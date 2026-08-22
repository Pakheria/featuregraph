# FeatureGraph ⚡

> **Token-efficient, AST-indexed feature topology maps for AI coding assistants. Eliminates AI amnesia and slashes context token waste by 90%.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)

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
| **Zero-Config Git Auto-Sync**| ❌ Manual re-runs | **✅ Instant Pre-Commit Git Hook** |
| **AI Anti-Amnesia Protection**| ❌ Passive graph | **✅ Invariant Contract (`[depends_on]`)** |
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
*This scans your code, generates `FEATURE_INDEX.json` and `SYSTEM_FEATURE_GRAPH.md`, and automatically installs the `.git/hooks/pre-commit` hook.*

---

## 🏷️ Annotating Your Code

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

## 🛠️ CLI Commands

```bash
# Scan codebase and update graphs
featuregraph scan

# Generate an interactive visual HTML graph
featuregraph visualize --out graph.html

# Query exact lines and dependencies for a specific feature ID
featuregraph query AUTH-01

# Manage automated pre-commit hook
featuregraph hook --install
featuregraph hook --uninstall
```

---

## 📄 License
MIT © [ProximaLink](https://proximalink.pk) / [Faizan Haroon](https://github.com/Pakheria)
