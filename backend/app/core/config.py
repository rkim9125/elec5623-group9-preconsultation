"""Application settings, loaded from environment / .env.

Every value has a default so the app runs without a .env file in development.
See backend/.env.example for the full list of keys.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # App
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Database (unused until C6 wires persistence)
    database_url: str = "sqlite:///./preconsult.db"

    # LLM provider (unused until C4 wires the adapter)
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # CORS: comma-separated list of allowed origins
    frontend_origin: str = "http://localhost:5173"

    # C5 uses private storage; local mode needs no account or network.
    storage_backend: Literal["local", "s3", "oss"] = "local"
    storage_local_root: Path = Path(".data/objects")
    storage_bucket: str = ""
    storage_region: str = ""
    storage_endpoint: str = ""
    storage_oss_is_cname: bool = False
    storage_prefix: str = "c5"
    storage_access_key_id: SecretStr = SecretStr("")
    storage_access_key_secret: SecretStr = SecretStr("")
    storage_session_token: SecretStr = SecretStr("")
    storage_timeout_seconds: int = Field(default=10, ge=1, le=120)
    document_api_token: SecretStr = SecretStr("")
    document_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=20 * 1024 * 1024)
    document_max_pdf_pages: int = Field(default=50, ge=1, le=200)
    document_max_text_chars: int = Field(default=200_000, ge=1, le=1_000_000)
    document_max_image_pixels: int = Field(default=20_000_000, ge=1, le=40_000_000)
    document_ocr_enabled: bool = False
    document_ocr_language: str = "eng"
    document_ocr_timeout_seconds: int = Field(default=20, ge=1, le=120)
    c5_pdf_font_path: str = ""

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        prefix = self.storage_prefix
        if not prefix or "\\" in prefix or any(p in {"", ".", ".."} for p in prefix.split("/")):
            raise ValueError("STORAGE_PREFIX must be a relative object-key prefix")
        key = self.storage_access_key_id.get_secret_value()
        secret = self.storage_access_key_secret.get_secret_value()
        if bool(key) != bool(secret):
            raise ValueError("Provide both STORAGE_ACCESS_KEY_ID and STORAGE_ACCESS_KEY_SECRET")
        if self.storage_backend != "local":
            if not self.storage_bucket or not self.document_api_token.get_secret_value():
                raise ValueError("Cloud storage requires STORAGE_BUCKET and DOCUMENT_API_TOKEN")
            if self.storage_backend == "s3" and not self.storage_region:
                raise ValueError("S3 requires STORAGE_REGION")
            if self.storage_backend == "oss" and (not key or not self.storage_endpoint):
                raise ValueError("OSS requires STORAGE_ENDPOINT and access credentials")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so settings are parsed once per process."""
    return Settings()
