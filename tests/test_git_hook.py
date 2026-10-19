import shutil
import subprocess
import unittest
import tempfile
from pathlib import Path

from featuregraph.hooks.git_hook import GitHookManager, HOOK_MARKER, HOOK_SCRIPT


class TestGitHookManager(unittest.TestCase):
    def test_install_and_uninstall_own_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git" / "hooks").mkdir(parents=True)

            self.assertEqual(GitHookManager.install(root), "installed")
            hook = root / ".git" / "hooks" / "pre-commit"
            self.assertIn(HOOK_MARKER, hook.read_text())
            self.assertTrue(hook.stat().st_mode & 0o100)

            # Idempotent reinstall of our own hook
            self.assertEqual(GitHookManager.install(root), "installed")

            self.assertTrue(GitHookManager.uninstall(root))
            self.assertFalse(hook.exists())

    def test_foreign_hook_never_touched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hook_dir = root / ".git" / "hooks"
            hook_dir.mkdir(parents=True)
            hook = hook_dir / "pre-commit"
            hook.write_text("#!/bin/sh\necho custom\n")

            self.assertEqual(GitHookManager.install(root), "foreign-hook")
            self.assertEqual(hook.read_text(), "#!/bin/sh\necho custom\n")

            self.assertFalse(GitHookManager.uninstall(root))
            self.assertTrue(hook.exists())

    def test_legacy_featuregraph_hook_is_upgraded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hook_dir = root / ".git" / "hooks"
            hook_dir.mkdir(parents=True)
            hook = hook_dir / "pre-commit"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "# Auto-sync FeatureGraph on every git commit\n"
                "featuregraph scan --quiet\n"
                "git add -f .featuregraph/index.json .featuregraph/graph.md\n"
            )

            self.assertEqual(GitHookManager.install(root), "upgraded")
            content = hook.read_text()
            self.assertIn(HOOK_MARKER, content)
            self.assertNotIn("index.json", content)

    def test_no_git_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(GitHookManager.install(Path(tmpdir)), "no-git")

    def test_hook_skips_dirty_worktree(self):
        self.assertIn("git diff --quiet", HOOK_SCRIPT)
        self.assertIn("git ls-files --others --exclude-standard", HOOK_SCRIPT)

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_install_respects_core_hooks_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", "custom-hooks"], check=True)

            self.assertEqual(GitHookManager.install(repo), "installed")
            self.assertTrue((repo / "custom-hooks" / "pre-commit").exists())
            self.assertTrue(GitHookManager.uninstall(repo))

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_install_in_git_worktree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-q", "--allow-empty", "-m", "init"],
                check=True,
            )
            worktree = Path(tmpdir) / "worktree"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(worktree)], check=True)

            self.assertEqual(GitHookManager.install(worktree), "installed")
            hook = repo / ".git" / "hooks" / "pre-commit"
            self.assertTrue(hook.exists())
            self.assertTrue(GitHookManager.uninstall(worktree))
            self.assertFalse(hook.exists())


if __name__ == "__main__":
    unittest.main()
