import subprocess
from pathlib import Path

HOOK_MARKER = "# featuregraph-managed-hook"

HOOK_SCRIPT = f"""#!/usr/bin/env bash
set -e
{HOOK_MARKER}
# Auto-sync FeatureGraph on every git commit
if command -v featuregraph >/dev/null 2>&1; then
    if ! git diff --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo "⚠ [FeatureGraph] Unstaged or untracked changes present — skipping index sync."
        exit 0
    fi
    echo "⚡ [FeatureGraph] Auto-syncing Feature Graph & Line Index..."
    featuregraph scan --quiet
    git add -f .featuregraph/
fi
"""


def _hook_path(repo_root: Path) -> Path | None:
    """Resolve the pre-commit hook path, including worktrees and core.hooksPath."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-path", "hooks"],
            capture_output=True, text=True, check=True,
        )
        raw = result.stdout.strip()
        if raw:
            hooks = Path(raw)
            if not hooks.is_absolute():
                hooks = repo_root / hooks
            return hooks / "pre-commit"
    except (OSError, subprocess.SubprocessError):
        pass

    git_dir = repo_root / ".git"
    if git_dir.is_dir():
        return git_dir / "hooks" / "pre-commit"
    return None

# @feature [GIT_HOOK-01] Git hook manager
class GitHookManager:
    """Installs or removes the git pre-commit hook. Never touches foreign hooks."""

    @staticmethod
    # @feature [GIT_HOOK-02] Install
    def install(repo_root: Path) -> str:
        """Returns 'installed', 'upgraded', 'no-git', or 'foreign-hook' (foreign hooks untouched)."""
        hook_path = _hook_path(repo_root)
        if hook_path is None:
            return "no-git"

        if hook_path.exists():
            existing = hook_path.read_text(encoding="utf-8", errors="ignore")
            if HOOK_MARKER not in existing:
                # Pre-marker FeatureGraph hooks carry the same banner; take them over.
                if "Auto-sync FeatureGraph" not in existing:
                    return "foreign-hook"
                hook_path.write_text(HOOK_SCRIPT, encoding="utf-8")
                hook_path.chmod(0o755)
                return "upgraded"

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
