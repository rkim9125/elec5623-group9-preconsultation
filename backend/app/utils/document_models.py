"""C5/C6 attachment metadata contract, separate from raw object bytes."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.utils.document_processing import ExtractionResult


class DocumentRecord(BaseModel):
    document_id: str
    session_id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    storage_backend: Literal["local", "s3", "oss"]
    storage_key: str
    status: Literal["uploaded", "processed", "partial", "ocr_required", "failed", "exported"]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    extraction: ExtractionResult | None = None
    error_code: str | None = None
    summary_ref: str | None = None
    summary_sha256: str | None = None
