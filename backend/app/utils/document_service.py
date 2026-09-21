"""Reusable C5 tools. C3 authorizes access; C6 may replace the metadata store.

Extraction returns untrusted evidence for review, never mutations to slot state.
Exports render only the exact approved snapshot supplied by the C3 store.
"""

from functools import lru_cache
from hashlib import sha256
from pathlib import PurePosixPath
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.models import SessionState, SessionStatus
from app.core.summary_approval import summary_digest, summary_is_approved
from app.llm.base import GeneratedSummary
from app.utils.document_errors import DocumentError
from app.utils.document_models import DocumentRecord
from app.utils.document_processing import extract_document, validate_file
from app.utils.document_rendering import render_summary
from app.utils.storage import ObjectStorage, build_storage


class DocumentMetadataStore(Protocol):
    def save(self, record: DocumentRecord) -> None: ...
    def get(self, session_id: str, document_id: str) -> DocumentRecord: ...
    def list(self, session_id: str) -> list[DocumentRecord]: ...
    def delete(self, session_id: str, document_id: str) -> None: ...


class InMemoryDocumentMetadataStore:
    """One-process development adapter; metadata does not survive restart."""

    def __init__(self) -> None:
        self._records: dict[str, DocumentRecord] = {}
        self._lock = RLock()

    def save(self, record: DocumentRecord) -> None:
        with self._lock:
            self._records[record.document_id] = record.model_copy(deep=True)

    def get(self, session_id: str, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._records.get(document_id)
            if record is None or record.session_id != session_id:
                raise DocumentError("DOCUMENT_NOT_FOUND", "Document not found in this session.", 404)
            return record.model_copy(deep=True)

    def list(self, session_id: str) -> list[DocumentRecord]:
        with self._lock:
            return [r.model_copy(deep=True) for r in self._records.values() if r.session_id == session_id]

    def delete(self, session_id: str, document_id: str) -> None:
        with self._lock:
            self.get(session_id, document_id)
            del self._records[document_id]


class DocumentService:
    def __init__(self, settings: Settings, storage: ObjectStorage, metadata: DocumentMetadataStore) -> None:
        self.settings = settings
        self.storage = storage
        self.metadata = metadata
        # Serialise local prototype mutations to avoid delete/extract races.
        # A persistent C6 store should replace this with transactions/leases.
        self._lock = RLock()

    def _store(self, session_id: str, filename: str, data: bytes, content_type: str,
               *, status: str = "uploaded", summary_ref: str | None = None,
               summary_sha256: str | None = None) -> DocumentRecord:
        document_id = f"doc_{uuid4().hex}"
        # No user-supplied IDs, names, or clinical data enter object keys.
        key = f"{self.settings.storage_prefix}/{sha256(session_id.encode()).hexdigest()}/{document_id}{PurePosixPath(filename).suffix.lower()}"
        record = DocumentRecord(
            document_id=document_id, session_id=session_id, filename=filename,
            content_type=content_type, size_bytes=len(data), sha256=sha256(data).hexdigest(),
            storage_backend=self.settings.storage_backend, storage_key=key, status=status,
            summary_ref=summary_ref, summary_sha256=summary_sha256,
        )
        self.storage.put(key, data, content_type)
        try:
            self.metadata.save(record)
        except Exception:
            # Best effort rollback; preserve the metadata failure if cleanup fails.
            try:
                self.storage.delete(key)
            except Exception:
                pass
            raise
        return record

    def upload(self, session_id: str, filename: str, data: bytes,
               content_type: str | None = None) -> DocumentRecord:
        name, mime = validate_file(filename, data, content_type, self.settings.document_max_bytes)
        with self._lock:
            return self._store(session_id, name, data, mime)

    def get(self, session_id: str, document_id: str) -> DocumentRecord:
        return self.metadata.get(session_id, document_id)

    def list(self, session_id: str) -> list[DocumentRecord]:
        return self.metadata.list(session_id)

    def download(self, session_id: str, document_id: str) -> tuple[DocumentRecord, bytes]:
        with self._lock:
            record = self.get(session_id, document_id)
            data = self.storage.get(record.storage_key)
            if len(data) != record.size_bytes or sha256(data).hexdigest() != record.sha256:
                raise DocumentError("DOCUMENT_INTEGRITY_FAILED", "Stored document integrity check failed.", 503)
            return record, data

    def extract(self, session_id: str, document_id: str) -> DocumentRecord:
        with self._lock:
            record, data = self.download(session_id, document_id)
            try:
                result = extract_document(
                    record.filename, data,
                    ocr_enabled=self.settings.document_ocr_enabled,
                    ocr_language=self.settings.document_ocr_language,
                    max_pdf_pages=self.settings.document_max_pdf_pages,
                    max_text_chars=self.settings.document_max_text_chars,
                    max_image_pixels=self.settings.document_max_image_pixels,
                    ocr_timeout_seconds=self.settings.document_ocr_timeout_seconds,
                )
            except DocumentError as exc:
                record.status = "failed"
                record.error_code = exc.code
                record.extraction = None
                self.metadata.save(record)
                raise
            record.extraction = result
            record.status = result.status
            record.error_code = None
            self.metadata.save(record)
            return record

    def delete(self, session_id: str, document_id: str) -> None:
        with self._lock:
            record = self.get(session_id, document_id)
            # Keep metadata if the provider fails, so deletion can be retried.
            self.storage.delete(record.storage_key)
            self.metadata.delete(session_id, document_id)

    def export(self, state: SessionState, summary: GeneratedSummary, format: str) -> DocumentRecord:
        # Snapshot mutable C3 state before testing approval and rendering.
        state = state.model_copy(deep=True)
        summary = summary.model_copy(deep=True)
        if state.status != SessionStatus.COMPLETED or not state.summary_ref:
            raise DocumentError("SUMMARY_NOT_READY", "Complete the session first.", 409)
        if not summary_is_approved(state, summary):
            raise DocumentError("SUMMARY_NOT_APPROVED", "Review and approve this summary version before exporting.", 409)
        if format not in {"pdf", "docx"}:
            raise DocumentError("UNSUPPORTED_EXPORT_FORMAT", "Use pdf or docx.")
        if sum(len(k) + len(v) for k, v in summary.sections.items()) + sum(map(len, summary.patient_questions)) > self.settings.document_max_text_chars:
            raise DocumentError("DOCUMENT_LIMIT_EXCEEDED", "Summary exceeds the configured text limit.", 413)
        data = render_summary(summary.sections, summary.patient_questions,
                              session_id=state.session_id, summary_ref=state.summary_ref, format=format,
                              max_text_chars=self.settings.document_max_text_chars,
                              font_path=self.settings.c5_pdf_font_path or None)
        if len(data) > self.settings.document_max_bytes:
            raise DocumentError("FILE_TOO_LARGE", "Export exceeds the configured size limit.", 413)
        mime = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with self._lock:
            return self._store(state.session_id, f"approved-summary.{format}", data, mime,
                               status="exported", summary_ref=state.summary_ref,
                               summary_sha256=summary_digest(state, summary))


@lru_cache
def get_document_service() -> DocumentService:
    settings = get_settings()
    return DocumentService(settings, build_storage(settings), InMemoryDocumentMetadataStore())
