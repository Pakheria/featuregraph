"""Jev-powered semantic router for FeatureGraph using OpenJev/Verdict."""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


class JevRouter:
    """Non-autoregressive decision router that matches natural language questions
    to FeatureGraph categories in a single pass (<40ms).

    Model path resolution (highest to lowest priority):
    1. --jev-model CLI flag (set via route_query call site)
    2. FEATUREGRAPH_JEV_MODEL env var
    3. .featuregraph/jev.json config file
    4. Hardcoded default (author's machine — may not work elsewhere)
    """

    DEFAULT_MODEL_PATH = Path("/home/proxima/Verdict-open-jev/artifacts/v2")
    CONFIG_FILE = Path(".featuregraph/jev.json")

    # Class-level override (set by CLI when --jev-model is passed)
    _override_model_path: Optional[Path] = None

    @classmethod
    def is_available(cls) -> bool:
        model_path = cls._resolve_model_path()
        return model_path is not None and model_path.exists()

    @classmethod
    def _resolve_model_path(cls) -> Optional[Path]:
        """Resolve model path with fallback chain."""
        # 1. CLI override (already set by CLI layer)
        if cls._override_model_path is not None:
            return cls._override_model_path

        # 2. Environment variable
        env = os.environ.get("FEATUREGRAPH_JEV_MODEL")
        if env:
            return Path(env)

        # 3. Config file
        config_file = Path(cls.CONFIG_FILE)
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding="utf-8"))
                model_path = Path(config.get("model_path", ""))
                if model_path.exists():
                    return model_path
            except (json.JSONDecodeError, OSError):
                pass

        # 4. Hardcoded default
        return cls.DEFAULT_MODEL_PATH

    @classmethod
    def route_query(cls, query_text: str, categories: Dict[str, Any]) -> Optional[str]:
        """Routes a natural language query to the best matching category."""
        if not categories:
            return None

        model_path = cls._resolve_model_path()
        if model_path is None or not model_path.exists():
            return None

        cat_keys = list(categories.keys())
        if len(cat_keys) == 1:
            return cat_keys[0]

        venv_python = Path("/home/proxima/Verdict-open-jev/.venv/bin/python")
        if not venv_python.exists():
            return None

        # ponytail: lightweight subprocess invocation of openjev to keep featuregraph dependency-free
        eval_script = (
            "import json, sys\n"
            "from rlcd import DecisionEngine, Choice, Option\n"
            f"engine = DecisionEngine(model_name_or_path='{model_path}', device='cpu')\n"
            f"cats = {json.dumps(cat_keys[:24])}\n"
            "query = Choice(\n"
            "    id='cat_route',\n"
            "    question='Which module or category does this code question relate to?',\n"
            "    options=[Option(id=c, description=f'Module related to {c}') for c in cats]\n"
            ")\n"
            f"res = engine.evaluate({json.dumps(query_text)}, [query]).results[0]\n"
            "if not res.is_abstention:\n"
            "    print(res.selected_id)\n"
        )

        try:
            p = subprocess.run(
                [str(venv_python), "-c", eval_script],
                capture_output=True,
                text=True,
                timeout=12,
            )
            out = p.stdout.strip().splitlines()
            if out:
                winner = out[-1].strip()
                if winner in categories:
                    return winner
        except Exception:
            pass

        return None

    @classmethod
    def set_model_path(cls, path: Path) -> None:
        """Override model path (used by CLI --jev-model flag)."""
        cls._override_model_path = path
