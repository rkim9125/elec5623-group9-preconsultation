"""Server-only configuration. Never serialize Settings into an API response."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_base_url: str
    db_path: Path
    upload_dir: Path
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    openai_transcription_model: str
    resend_api_key: str
    resend_from_email: str
    doctor_emails: tuple[str, ...]
    session_ttl_seconds: int = 60 * 60 * 12
    otp_ttl_seconds: int = 60 * 10
    otp_attempt_limit: int = 5
    max_upload_bytes: int = 10 * 1024 * 1024
    max_file_mb: int = 10

    @property
    def production(self) -> bool:
        return self.app_env == "production"

    @property
    def allowed_origins(self) -> set[str]:
        origins = {self.app_base_url.rstrip("/")}
        origins.update(x.strip().rstrip("/") for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip())
        if not self.production:
            origins.update(f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (8000, 5173))
        return origins

    @property
    def mail_configured(self) -> bool:
        return bool(self.resend_api_key and self.resend_from_email)


def get_settings() -> Settings:
    """Read env at call time, allowing isolated test DBs and key rotation."""
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        app_base_url=os.getenv("APP_BASE_URL", "http://localhost:8000").strip(),
        db_path=Path(os.getenv("PRODUCT_DB_PATH", str(BACKEND_DIR / "data" / "product.sqlite3"))).expanduser().resolve(),
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(BACKEND_DIR / "data" / "uploads"))).expanduser().resolve(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-6-sol").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        openai_transcription_model=os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe").strip(),
        resend_api_key=os.getenv("RESEND_API_KEY", "").strip(),
        resend_from_email=os.getenv("RESEND_FROM_EMAIL", "").strip(),
        doctor_emails=tuple(sorted({e.strip().lower() for e in os.getenv("DOCTOR_EMAILS", "").split(",") if e.strip()})),
    )


def model_options() -> list[dict[str, str]]:
    """Actual availability is verified by the provider, never assumed by this menu."""
    configured = get_settings().openai_model
    ids = list(dict.fromkeys([configured, "gpt-6-sol", "gpt-5.6-sol"]))
    return [{"id": model, "label": model} for model in ids]
