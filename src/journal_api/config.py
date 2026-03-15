"""Configuration via environment variables and optional YAML file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_yaml_config() -> dict[str, Any]:
    """Load config.yaml if it exists alongside the project root."""
    for candidate in [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
    ]:
        if candidate.exists():
            with open(candidate) as f:
                return yaml.safe_load(f) or {}
    return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JOURNAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API keys / emails for polite pools
    crossref_email: str = ""
    unpaywall_email: str = ""
    openalex_api_key: str = ""
    semantic_scholar_api_key: str = ""

    # Campus proxy
    campus_proxy_url: str = ""

    # Sci-Hub mirrors
    scihub_mirrors: list[str] = Field(default_factory=lambda: [
        "https://sci-hub.se",
        "https://sci-hub.st",
        "https://sci-hub.ru",
    ])

    # Cache
    cache_dir: str = str(Path.cwd() / ".cache" / "journal_api")
    metadata_ttl_days: int = 30

    # Rate limits (requests per second)
    rate_crossref: float = 50.0
    rate_openalex: float = 10.0
    rate_semantic_scholar: float = 5.0
    rate_unpaywall: float = 10.0
    rate_scihub: float = 0.33  # 1 per 3 seconds
    rate_google_scholar: float = 0.1  # 1 per 10 seconds
    rate_publisher_proxy: float = 2.0

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"

    def __init__(self, **kwargs: Any) -> None:
        yaml_config = _load_yaml_config()
        # YAML values are overridden by env vars (pydantic-settings handles env)
        merged = {**yaml_config, **kwargs}
        super().__init__(**merged)


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
