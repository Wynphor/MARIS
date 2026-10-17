"""
Competition configuration service.

Manages per-workspace competition metadata (type, team info, deadline)
and auto-creates standard directory templates on workspace creation.
"""
import json
from pathlib import Path
from typing import Optional

from ..core.config import settings

DATA_DIR = settings.DATA_DIR

# Standard directory structure for a math modeling workspace
STANDARD_DIRS = [
    "data",
    "data/raw",
    "data/processed",
    "src",
    "paper",
    "paper/figures",
    "paper/sections",
    "output",
    "output/figures",
    "output/tables",
    "docs",
    "docs/references",
    "docs/award_papers",
]

DEFAULT_CONFIG = {
    "competition_type": "国赛",
    "problem_id": "",
    "problem_title": "",
    "team_name": "",
    "members": [],
    "mentor": "",
    "start_time": "",
    "deadline": "",
    "language": "zh",
    "max_pages": 20,
    "latex_template": "default",
    "preferred_llm": "auto",
    "auto_compile": True,
    "review_rounds": 2,
    "run_code_on_generate": True,
    "notes": "",
}


class CompetitionConfigService:
    """Manage competition configuration and workspace templates."""

    @staticmethod
    def init_workspace(workspace_id: str, competition_type: str = "国赛") -> dict:
        """Create standard directory structure and config.json for a new workspace."""
        ws = DATA_DIR / workspace_id
        for d in STANDARD_DIRS:
            (ws / d).mkdir(parents=True, exist_ok=True)

        config_path = ws / "config.json"
        if not config_path.exists():
            config = DEFAULT_CONFIG.copy()
            config["competition_type"] = competition_type
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        # Copy CUMCM LaTeX template if available
        if competition_type in ("国赛", "CUMCM"):
            CompetitionConfigService._copy_cumcm_template(ws)

        return {"created_dirs": STANDARD_DIRS, "config": config}

    @staticmethod
    def _copy_cumcm_template(ws_path: Path):
        """Copy CUMCM LaTeX class file to workspace paper/ directory."""
        # Look for the template in project root
        template_candidates = [
            Path("paper/cumcmthesis.cls"),
            Path("docs/2026国赛最新模版（Word+LaTeX）/数学建模国赛latex模板/cumcmthesis.cls"),
        ]
        dest = ws_path / "paper" / "cumcmthesis.cls"
        if dest.exists():
            return  # Already copied
        for candidate in template_candidates:
            if candidate.exists():
                import shutil
                shutil.copy2(candidate, dest)
                # Also copy template .tex if available
                tex_candidate = candidate.parent / "example.tex"
                template_tex = ws_path / "paper" / "template.tex"
                if tex_candidate.exists() and not template_tex.exists():
                    shutil.copy2(tex_candidate, template_tex)
                return

    @staticmethod
    def get_config(workspace_id: str) -> dict:
        """Read competition config from workspace."""
        config_path = DATA_DIR / workspace_id / "config.json"
        if not config_path.exists():
            return DEFAULT_CONFIG.copy()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def update_config(workspace_id: str, updates: dict) -> dict:
        """Merge updates into existing config and save."""
        current = CompetitionConfigService.get_config(workspace_id)

        # Only update known keys (ignore unknown fields)
        for k in DEFAULT_CONFIG:
            if k in updates:
                current[k] = updates[k]

        config_path = DATA_DIR / workspace_id / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)

        return current
