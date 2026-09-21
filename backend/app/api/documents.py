"""Session-scoped C5 HTTP tools. Binary access is proxied, never public URLs."""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.api.deps import get_store
from app.api.document_auth import require_document_access
from app.api.schemas import ExportRequest
from app.core.models import SessionStatus
from app.core.errors import SummaryNotReady
from app.utils.document_errors import DocumentError
from app.utils.document_models import DocumentRecord
from app.utils.document_service import get_document_service

router = APIRouter(tags=["documents"], dependencies=[Depends(require_document_access)])


@router.get("/documents/health")
def document_health(service=Depends(get_document_service)):
    service.storage.check()
    return {"status": "ok", "storage_backend": service.settings.storage_backend,
            "ocr_enabled": service.settings.document_ocr_enabled}


@router.post("/sessions/{session_id}/documents", status_code=201, response_model=DocumentRecord)
def upload_document(session_id: str, file: UploadFile = File(...),
                    store=Depends(get_store), service=Depends(get_document_service)):
    try:
        store.get(session_id)
        data = file.file.read(service.settings.document_max_bytes + 1)
        if len(data) > service.settings.document_max_bytes:
            raise DocumentError("FILE_TOO_LARGE", "File exceeds the configured size limit.", 413)
        return service.upload(session_id, file.filename or "", data, file.content_type)
    finally:
        file.file.close()


@router.get("/sessions/{session_id}/documents", response_model=list[DocumentRecord])
def list_documents(session_id: str, store=Depends(get_store), service=Depends(get_document_service)):
    store.get(session_id)
    return service.list(session_id)


@router.get("/sessions/{session_id}/documents/{document_id}", response_model=DocumentRecord)
def get_document(session_id: str, document_id: str, store=Depends(get_store), service=Depends(get_document_service)):
    store.get(session_id)
    return service.get(session_id, document_id)


@router.post("/sessions/{session_id}/documents/{document_id}/extract", response_model=DocumentRecord)
def extract_document(session_id: str, document_id: str, store=Depends(get_store), service=Depends(get_document_service)):
    store.get(session_id)
    return service.extract(session_id, document_id)


@router.get("/sessions/{session_id}/documents/{document_id}/download")
def download_document(session_id: str, document_id: str, store=Depends(get_store), service=Depends(get_document_service)):
    store.get(session_id)
    record, data = service.download(session_id, document_id)
    return Response(content=data, media_type=record.content_type, headers={
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.filename, safe='')}",
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


@router.delete("/sessions/{session_id}/documents/{document_id}", status_code=204)
def delete_document(session_id: str, document_id: str, store=Depends(get_store), service=Depends(get_document_service)):
    store.get(session_id)
    service.delete(session_id, document_id)
    return Response(status_code=204)


@router.post("/sessions/{session_id}/exports", status_code=201, response_model=DocumentRecord)
def export_summary(session_id: str, body: ExportRequest,
                   store=Depends(get_store), service=Depends(get_document_service)):
    state = store.get(session_id)
    if state.status != SessionStatus.COMPLETED:
        raise SummaryNotReady("Complete the session and approve the summary first.")
    return service.export(state, store.get_summary(session_id), body.format)
