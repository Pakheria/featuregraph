from pathlib import Path

HOOK_MARKER = "# featuregraph-managed-hook"

HOOK_SCRIPT = f"""#!/usr/bin/env bash
{HOOK_MARKER}
# Auto-sync FeatureGraph on every git commit
if command -v featuregraph >/dev/null 2>&1; then
    echo "⚡ [FeatureGraph] Auto-syncing Feature Graph & Line Index..."
    featuregraph scan --quiet
    git add -f .featuregraph/ 2>/dev/null || true
fi
"""

# @feature [GIT_HOOK-01] Git hook manager
class GitHookManager:
    """Installs or removes the git pre-commit hook. Never touches foreign hooks."""

    @staticmethod
    # @feature [GIT_HOOK-02] Install
    def install(repo_root: Path) -> str:
        """Returns 'installed', 'no-git', or 'foreign-hook' (existing hook left untouched)."""
        git_dir = repo_root / ".git"
        if not git_dir.exists():
            return "no-git"

        hook_path = git_dir / "hooks" / "pre-commit"
        if hook_path.exists() and HOOK_MARKER not in hook_path.read_text(encoding="utf-8", errors="ignore"):
            return "foreign-hook"

        hook_path.parent.mkdir(parents=True, exist_ok=True)
        hook_path.write_text(HOOK_SCRIPT, encoding="utf-8")
        hook_path.chmod(0o755)
        return "installed"

    @staticmethod
    # @feature [GIT_HOOK-03] Uninstall
    def uninstall(repo_root: Path) -> bool:
        """Removes the hook only if FeatureGraph installed it. Returns True if removed."""
        hook_path = repo_root / ".git" / "hooks" / "pre-commit"
        if hook_path.exists() and HOOK_MARKER in hook_path.read_text(encoding="utf-8", errors="ignore"):
            hook_path.unlink()
            return True
        return False
