import unittest
import tempfile
from pathlib import Path
from featuregraph.skills.skill_manager import SkillManager

class TestSkillManager(unittest.TestCase):
    def test_install_workspace_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            skill_file = SkillManager.install_workspace_skill(tmp_path)
            self.assertTrue(skill_file.exists())
            self.assertIn("name: featuregraph", skill_file.read_text())

if __name__ == "__main__":
    unittest.main()
