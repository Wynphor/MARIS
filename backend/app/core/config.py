from pydantic_settings import BaseSettings
from pathlib import Path
import os

# 自动定位 .env 文件：优先当前目录，其次项目根目录
_env_candidates = [Path(".env")]
_backend_dir = Path(__file__).resolve().parent.parent.parent  # backend/
_project_root = _backend_dir.parent
_env_candidates.append(_backend_dir / ".env")
_env_candidates.append(_project_root / ".env")

_env_file = None
for candidate in _env_candidates:
    if candidate.exists():
        _env_file = str(candidate)
        break


class Settings(BaseSettings):
    PROJECT_NAME: str = "MathModel-Engine"
    API_V1_STR: str = "/api/v1"
    DATA_DIR: Path = Path("data")
    DATABASE_URL: str = "sqlite:///./mathmodel.db"
    DEFAULT_MODEL: str = "gemini-1.5-pro-002"

    # AI API Keys (loaded from .env)
    MIMO_API_KEY: str = ""
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"

    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    CLAUDE_API_KEY: str = ""
    CLAUDE_BASE_URL: str = "https://api.anthropic.com/v1"

    GROK_API_KEY: str = ""
    GROK_BASE_URL: str = "https://api.x.ai/v1"

    model_config = {"env_file": _env_file, "extra": "ignore"}


settings = Settings()
