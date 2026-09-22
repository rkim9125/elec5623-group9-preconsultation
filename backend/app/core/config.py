"""Application settings, loaded from environment / .env.

Every value has a default so the app runs without a .env file in development.
See backend/.env.example for the full list of keys.
"""

from __future__ import annotations

from functools import lru_cache

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

    # LLM provider (unused until C4 wires the adapter)
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # CORS: comma-separated list of allowed origins
    frontend_origin: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
