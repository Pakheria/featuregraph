from __future__ import annotations

import os
from pathlib import Path
from typing import List

FEATUREGRAPH_SKILL_MD = """---
name: featuregraph
description: >-
  Runs featuregraph commands on the current project. Use when the user mentions
  featuregraph, wants to init a project, scan for features, annotate code,
  query a feature ID, or generate a visual graph. Also pairs with ponytail: index first, then review.
---

# FeatureGraph Skill

FeatureGraph is a CLI tool that AST-scans a codebase and generates a 2-Tier Hierarchical topology index:
- `.featuregraph/manifest.json` — Tier-1 ultra-compact directory (<100 tokens) of domains & feature summaries
- `.featuregraph/categories/<category>.json` — Tier-2 exact line maps (#Lstart-Lend) per domain
- `.featuregraph/graph.md` — markdown table + Mermaid dependency diagram
- `AGENTS.md` — AI circuit-breaker directive (read manifest first, stop scanning)
- `.git/hooks/pre-commit` — auto-syncs index on every commit

---

## Step 0: Always Check First (MANDATORY)

**Before doing anything with the feature index — whether the user asked for it or not — check if it exists:**

```bash
(test -f .featuregraph/manifest.json || test -f .featuregraph/index.json || test -f FEATURE_INDEX.json) && echo "EXISTS" || echo "MISSING"
```

### If MISSING → Auto-init without asking
Run `featuregraph init` immediately. Do not ask the user. Do not tell them to run it.
Just do it, then continue with their original request.

```bash
featuregraph init
```

### If EXISTS → 2-Tier Inspection Workflow (Max Token Efficiency)
1. **Turn 1:** Read `.featuregraph/manifest.json` (**< 100 tokens**) to find which category owns the target feature.
2. **Turn 2:** Read only that domain's file: `.featuregraph/categories/<category>.json` (**< 300 tokens**).
3. **Turn 3:** Read and edit **ONLY** the exact line spans (`#Lstart-Lend`). Never do full-file exploratory reads.

### If EXISTS → Check staleness
If the last git commit is newer than the index, re-scan silently before reading:
```bash
featuregraph scan --quiet
```

---

## When to Activate

- User types `/featuregraph` or mentions featuregraph
- User asks to "init", "index", "scan", "annotate", or "map" a project
- User references FEATURE_INDEX.json or a feature ID (e.g. AUTH-01)
- User combines with `/ponytail` — index first, then review
- **Any time you are about to read FEATURE_INDEX.json and it may not exist**

---

## Commands

### Init (first time setup in repository)
```bash
featuregraph init
```
Generates FEATURE_INDEX.json, SYSTEM_FEATURE_GRAPH.md, AGENTS.md, workspace skill, and pre-commit hook.

### Re-scan
```bash
featuregraph scan
featuregraph scan --quiet
featuregraph scan --dir ./src --json index.json --md GRAPH.md
```

### Auto-suggest & write feature tags
```bash
# Preview suggestions without modifying files (dry-run)
featuregraph annotate --dry-run
# Apply suggestions directly to un-annotated symbols
featuregraph annotate --yes
# Annotate specific directory with limit
featuregraph annotate --dir ./src --yes --limit 50
```

### Query a feature
```bash
featuregraph query AUTH-01
```

### Visual HTML DAG
```bash
featuregraph visualize --out graph.html
```

### Hook management
```bash
featuregraph hook --install
featuregraph hook --uninstall
```

---

## Pairing with Ponytail

When user invokes both `/featuregraph` and `/ponytail`:
1. Check/init index (Step 0 above)
2. Read `FEATURE_INDEX.json` to understand what features exist
3. Run ponytail review on the changed files with feature context

---

## Annotating Code for Indexing

**Python:**
```python
# @feature [AUTH-01] JWT Cookie Session Gate
# @depends [FIREWALL-01], [RBAC-01]
async def get_current_user(...):
```

**TypeScript/React:**
```tsx
// @feature [DASH-01] Executive Analytics Widget
// @depends [AUTH-01]
export const AnalyticsWidget = () => { ... }
```

Feature IDs: `[A-Za-z0-9_-]+`, normalised to UPPER.

---

## After Running

Always show the user:
- How many features were indexed
- Whether AGENTS.md was created (first init only)
- If the project was auto-inited, tell them: "Project wasn't indexed yet — ran `featuregraph init` automatically."
"""

# @feature [SKILL-01] Skill Manager
class SkillManager:
    """Manages installation of the FeatureGraph skill across workspaces and AI agent environments."""

    @staticmethod
    def get_skill_content() -> str:
        return FEATUREGRAPH_SKILL_MD.strip() + "\n"

    @staticmethod
    def install_workspace_skill(project_root: Path) -> Path:
        """Installs the skill in the workspace's .agents/skills/ directory."""
        target_dir = project_root / ".agents" / "skills" / "featuregraph"
        target_dir.mkdir(parents=True, exist_ok=True)
        skill_file = target_dir / "SKILL.md"
        skill_file.write_text(SkillManager.get_skill_content(), encoding="utf-8")
        return skill_file

    @staticmethod
    def install_global_skills() -> List[Path]:
        """Installs the skill across user-global AI agent configurations (Antigravity/Gemini, Claude Code, Cursor)."""
        installed: List[Path] = []
        home = Path.home()

        targets = [
            home / ".gemini" / "config" / "skills" / "featuregraph" / "SKILL.md",
            home / ".claude" / "skills" / "featuregraph" / "SKILL.md",
            home / ".cursor" / "skills" / "featuregraph" / "SKILL.md",
        ]

        content = SkillManager.get_skill_content()
        for target in targets:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                installed.append(target)
            except Exception:
                pass

        return installed
