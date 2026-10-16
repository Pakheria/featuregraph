import unittest
import tempfile
from pathlib import Path

from featuregraph.hooks.git_hook import GitHookManager, HOOK_MARKER


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

    def test_no_git_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(GitHookManager.install(Path(tmpdir)), "no-git")


if __name__ == "__main__":
    unittest.main()
