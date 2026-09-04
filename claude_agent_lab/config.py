"""Configuration loading and the Settings model for claude_agent_lab.

Precedence (highest wins):
    1. Environment variables — AGENT_LAB_<SECTION>_<FIELD>, e.g. AGENT_LAB_LLM_MODEL
    2. .env at the repo root (loaded into the environment before step 1 is read)
    3. config.yaml at the repo root (versioned, non-secret defaults)
    4. Built-in field defaults on the models below

Secrets (API keys) are read only from the environment/.env, under their
provider-native names (ANTHROPIC_API_KEY, VOYAGE_API_KEY) — never from
config.yaml, which is checked into git and never should hold a secret.

The merge in `get_settings` is deliberately explicit rather than routed
through a settings-source framework's own precedence rules — for a project
whose whole point is understanding each layer, "read the function" should be
enough to know where a value came from.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"
DEFAULT_ENV_PATH = REPO_ROOT / ".env"

_ENV_PREFIX = "AGENT_LAB_"

# Maps an env var suffix (after AGENT_LAB_) to where it lands in the config
# dict: (section, field), or (None, field) for a top-level field.
_ENV_OVERRIDES: dict[str, tuple[str | None, str]] = {
    "LLM_PROVIDER": ("llm", "provider"),
    "LLM_MODEL": ("llm", "model"),
    "LLM_MAX_TOKENS": ("llm", "max_tokens"),
    "EMBEDDING_PROVIDER": ("embedding", "provider"),
    "EMBEDDING_MODEL": ("embedding", "model"),
    "LOG_LEVEL": (None, "log_level"),
}


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-opus-5"
    max_tokens: int = 16000


class EmbeddingConfig(BaseModel):
    """Config for the embedding client.

    Not yet exercised by a real retrieval path — that's Phase 2 (RAG core).
    Defaults to "fake" so the CLI runs with zero setup.
    """

    provider: str = "fake"
    model: str = "voyage-3.5"


class Settings(BaseModel):
    llm: LLMConfig = LLMConfig()
    embedding: EmbeddingConfig = EmbeddingConfig()
    log_level: str = "INFO"

    anthropic_api_key: str | None = None
    voyage_api_key: str | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a top-level mapping")
    return data


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Overlay AGENT_LAB_<SECTION>_<FIELD> environment variables onto config."""
    for suffix, (section, field) in _ENV_OVERRIDES.items():
        env_var = f"{_ENV_PREFIX}{suffix}"
        if env_var not in os.environ:
            continue
        value: Any = os.environ[env_var]
        if section is None:
            config[field] = value
        else:
            config.setdefault(section, {})[field] = value
    return config


@lru_cache
def get_settings(config_path: Path | None = None, env_path: Path | None = None) -> Settings:
    """Build the merged Settings object.

    Cached per (config_path, env_path) — call get_settings.cache_clear() to
    force a reload (tests that mutate the environment need this).
    """
    load_dotenv(env_path or DEFAULT_ENV_PATH)

    config = _load_yaml(config_path or DEFAULT_CONFIG_PATH)
    config = _apply_env_overrides(config)
    config["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY")
    config["voyage_api_key"] = os.environ.get("VOYAGE_API_KEY")

    return Settings(**config)
