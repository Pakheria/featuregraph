from __future__ import annotations

from pathlib import Path
from typing import List

_SKILL_DIR = Path(__file__).parent / "featuregraph"

# @feature [SKILL-01] Skill Manager
class SkillManager:
    """Manages installation of the FeatureGraph skill across workspaces and AI agent environments."""

    @staticmethod
    def get_skill_content() -> str:
        skill_file = _SKILL_DIR / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
        return __doc__ or ""

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
        """Installs the skill across user-global AI agent configurations."""
        installed: List[Path] = []
        home = Path.home()

        targets = [
            home / ".gemini" / "config" / "skills" / "featuregraph" / "SKILL.md",
            home / ".claude" / "skills" / "featuregraph" / "SKILL.md",
            home / ".cursor" / "skills" / "featuregraph" / "SKILL.md",
            home / ".config" / "opencode" / "skills" / "featuregraph" / "SKILL.md",
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
