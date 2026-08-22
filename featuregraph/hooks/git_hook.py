from pathlib import Path

HOOK_SCRIPT = """#!/usr/bin/env bash
# Auto-sync FeatureGraph on every git commit
if command -v featuregraph >/dev/null 2>&1; then
    echo "⚡ [FeatureGraph] Auto-syncing Feature Graph & Line Index..."
    featuregraph scan --quiet
    git add -f FEATURE_INDEX.json SYSTEM_FEATURE_GRAPH.md 2>/dev/null || true
fi
"""

class GitHookManager:
    """Installs or removes the zero-config git pre-commit hook."""

    @staticmethod
    def install(repo_root: Path) -> bool:
        hook_path = repo_root / ".git" / "hooks" / "pre-commit"
        if not (repo_root / ".git").exists():
            return False

        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text(HOOK_SCRIPT, encoding="utf-8")
        hook_path.chmod(0o755)
        return True

    @staticmethod
    def uninstall(repo_root: Path) -> bool:
        hook_path = repo_root / ".git" / "hooks" / "pre-commit"
        if hook_path.exists():
            hook_path.unlink()
            return True
        return False
