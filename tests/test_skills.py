import unittest
import tempfile
from pathlib import Path
from featuregraph.skills.skill_manager import SkillManager

import json
from featuregraph.formatters.json_formatter import JSONFormatter

class TestSkillManager(unittest.TestCase):
    def test_install_workspace_skill(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            skill_file = SkillManager.install_workspace_skill(tmp_path)
            self.assertTrue(skill_file.exists())
            self.assertIn("name: featuregraph", skill_file.read_text())

    def test_json_formatter_2tier(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            fg_dir = tmp_path / ".featuregraph"
            
            sample_graph = {
                "AUTH-01": {"name": "Token Gate", "category": "auth", "locations": [{"file": "auth.py", "lines": [1, 10]}]},
                "PAY-01": {"name": "Payroll Engine", "category": "payroll", "locations": [{"file": "pay.py", "lines": [1, 20]}]},
            }

            JSONFormatter.write_all(sample_graph, fg_dir, tmp_path)

            self.assertTrue((fg_dir / "manifest.json").exists())
            self.assertTrue((fg_dir / "index.json").exists())
            self.assertTrue((fg_dir / "categories" / "auth.json").exists())
            self.assertTrue((fg_dir / "categories" / "payroll.json").exists())

            manifest = json.loads((fg_dir / "manifest.json").read_text())
            self.assertIn("auth", manifest["categories"])
            self.assertEqual(manifest["categories"]["auth"]["AUTH-01"], "Token Gate")

if __name__ == "__main__":
    unittest.main()
