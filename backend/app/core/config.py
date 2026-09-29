"""Application settings, loaded from environment / .env.

Every value has a default so the app runs without a .env file in development.
See backend/.env.example for the full list of keys.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Relative SQLite paths are resolved against the backend directory.
    database_url: str = "sqlite:///./preconsult.db"

    # LLM provider
    llm_provider: Literal["fake", "azure"] = "fake"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # CORS: comma-separated list of allowed origins. Leave empty in local
    # development to allow any localhost/127.0.0.1 port (see cors_origin_regex).
    frontend_origin: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """Explicitly allowed origins. Empty in development — the regex below
        covers local dev instead."""
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        """Fallback for local development only.

        A browser treats http://localhost:5173 and http://127.0.0.1:5173 as
        different origins, and Vite silently moves to 5174+ when its default
        port is taken — so pinning a single origin means the frontend gets
        blocked for reasons that look nothing like a CORS problem. When no
        explicit FRONTEND_ORIGIN is configured, allow any local port instead.
        Setting FRONTEND_ORIGIN (as a deployment should) disables this.
        """
        if self.cors_origins:
            return None
        return r"http://(localhost|127\.0\.0\.1)(:\d+)?"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
