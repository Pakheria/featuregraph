import subprocess
from pathlib import Path

HOOK_MARKER = "# featuregraph-managed-hook"

HOOK_SCRIPT = f"""#!/usr/bin/env bash
{HOOK_MARKER}
# Auto-sync FeatureGraph on every git commit
if command -v featuregraph >/dev/null 2>&1; then
    if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "⚠ [FeatureGraph] Unstaged or untracked changes present — skipping index sync."
        exit 0
    fi
    echo "⚡ [FeatureGraph] Auto-syncing Feature Graph & Line Index..."
    featuregraph scan --quiet
    git add -f .featuregraph/ 2>/dev/null || true
fi
"""


def _hook_path(repo_root: Path) -> Path | None:
    """Resolve the pre-commit hook path, including git worktrees and submodules."""
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return None
    if git_dir.is_dir():
        return git_dir / "hooks" / "pre-commit"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    hooks = Path(result.stdout.strip())
    if not hooks.is_absolute():
        hooks = repo_root / hooks
    return hooks / "pre-commit"

# @feature [GIT_HOOK-01] Git hook manager
class GitHookManager:
    """Installs or removes the git pre-commit hook. Never touches foreign hooks."""

    @staticmethod
    # @feature [GIT_HOOK-02] Install
    def install(repo_root: Path) -> str:
        """Returns 'installed', 'no-git', or 'foreign-hook' (existing hook left untouched)."""
        hook_path = _hook_path(repo_root)
        if hook_path is None:
            return "no-git"

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
        hook_path = _hook_path(repo_root)
        if hook_path is None:
            return False
        if hook_path.exists() and HOOK_MARKER in hook_path.read_text(encoding="utf-8", errors="ignore"):
            hook_path.unlink()
            return True
        return False
