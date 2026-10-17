"""
System configuration API endpoints.

Provides runtime view of system-level settings (LLM providers, default model)
and allows updating select fields without restarting the server.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ...core.config import settings

router = APIRouter(prefix="/system", tags=["system"])

# LLM provider definitions
LLM_PROVIDERS = [
    {"id": "mimo", "name": "MIMO (小米)", "key_env": "MIMO_API_KEY", "url_env": "MIMO_BASE_URL",
     "default_url": "https://token-plan-cn.xiaomimimo.com/v1"},
    {"id": "deepseek", "name": "DeepSeek", "key_env": "DEEPSEEK_API_KEY", "url_env": "DEEPSEEK_BASE_URL",
     "default_url": "https://api.deepseek.com"},
    {"id": "gemini", "name": "Google Gemini", "key_env": "GEMINI_API_KEY", "url_env": "GEMINI_BASE_URL",
     "default_url": "https://generativelanguage.googleapis.com/v1beta"},
    {"id": "openai", "name": "OpenAI", "key_env": "OPENAI_API_KEY", "url_env": "OPENAI_BASE_URL",
     "default_url": "https://api.openai.com/v1"},
    {"id": "claude", "name": "Claude (Anthropic)", "key_env": "CLAUDE_API_KEY", "url_env": "CLAUDE_BASE_URL",
     "default_url": "https://api.anthropic.com/v1"},
    {"id": "grok", "name": "Grok (xAI)", "key_env": "GROK_API_KEY", "url_env": "GROK_BASE_URL",
     "default_url": "https://api.x.ai/v1"},
]


def _mask_key(key: str) -> str:
    """Mask API key for safe display: show first 4 and last 4 chars."""
    if not key or len(key) < 12:
        return "***已配置***" if key else ""
    return key[:4] + "****" + key[-4:]


def _find_env_file() -> Optional[str]:
    """Find the .env file path."""
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent.parent.parent.parent / ".env",  # backend/.env
        Path(__file__).resolve().parent.parent.parent.parent.parent / ".env",  # project root
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve())
    return None


@router.get("/config")
async def get_system_config():
    """Get system-level configuration (API keys masked)."""
    providers = []
    for p in LLM_PROVIDERS:
        key = getattr(settings, p["key_env"], "")
        url = getattr(settings, p["url_env"], "")
        providers.append({
            "id": p["id"],
            "name": p["name"],
            "configured": bool(key),
            "key_masked": _mask_key(key),
            "base_url": url or p["default_url"],
        })

    configured_count = sum(1 for p in providers if p["configured"])

    return {
        "providers": providers,
        "default_model": settings.DEFAULT_MODEL,
        "data_dir": str(settings.DATA_DIR),
        "database_url": _mask_database_url(settings.DATABASE_URL),
        "env_file": _find_env_file(),
        "configured_count": configured_count,
        "total_providers": len(LLM_PROVIDERS),
    }


class SystemConfigUpdate(BaseModel):
    default_model: Optional[str] = None
    data_dir: Optional[str] = None


@router.put("/config")
async def update_system_config(updates: SystemConfigUpdate):
    """Update select system config fields (writes to .env file)."""
    env_file = _find_env_file()
    if not env_file:
        # Create .env in backend directory
        env_file = str(
            Path(__file__).resolve().parent.parent.parent.parent / ".env"
        )

    env_path = Path(env_file)
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    changes = {}

    if updates.default_model is not None:
        settings.DEFAULT_MODEL = updates.default_model
        _upsert_env_line(lines, "DEFAULT_MODEL", updates.default_model)
        changes["default_model"] = updates.default_model

    if updates.data_dir is not None:
        settings.DATA_DIR = Path(updates.data_dir)
        _upsert_env_line(lines, "DATA_DIR", updates.data_dir)
        changes["data_dir"] = updates.data_dir

    if changes:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"updated": changes, "env_file": str(env_path.resolve())}


class ProviderUpdate(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None


@router.put("/config/providers/{provider_id}")
async def update_provider_config(provider_id: str, updates: ProviderUpdate):
    """Update a specific LLM provider's API key and/or base URL."""
    provider = next((p for p in LLM_PROVIDERS if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    env_file = _find_env_file()
    if not env_file:
        env_file = str(
            Path(__file__).resolve().parent.parent.parent.parent / ".env"
        )

    env_path = Path(env_file)
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    changes = {}

    if updates.api_key is not None:
        setattr(settings, provider["key_env"], updates.api_key)
        _upsert_env_line(lines, provider["key_env"], updates.api_key)
        changes["api_key"] = _mask_key(updates.api_key)

    if updates.base_url is not None:
        setattr(settings, provider["url_env"], updates.base_url)
        _upsert_env_line(lines, provider["url_env"], updates.base_url)
        changes["base_url"] = updates.base_url

    if changes:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"provider": provider_id, "updated": changes}


def _upsert_env_line(lines: list, key: str, value: str):
    """Insert or update a KEY=VALUE line in the .env lines list."""
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.strip().startswith(prefix) or line.strip().startswith(f"#{prefix}"):
            lines[i] = f"{key}={value}"
            return
    lines.append(f"{key}={value}")


def _mask_database_url(url: str) -> str:
    """Mask database URL for display."""
    if "sqlite" in url.lower():
        return url  # SQLite URLs are safe to show
    # For non-SQLite, mask password
    if "@" in url:
        parts = url.split("@")
        prefix = parts[0]
        if ":" in prefix.split("://")[-1]:
            scheme_user = prefix.split("://")[0] + "://" + prefix.split("://")[1].split(":")[0]
            return f"{scheme_user}:****@{parts[1]}"
    return url
