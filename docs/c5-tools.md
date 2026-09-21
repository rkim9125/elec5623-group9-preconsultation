# Calling the C5 document tools

C5 exposes **Python utilities and an HTTP API** inside the existing FastAPI
backend. It is not an MCP server, and it does not automatically register tools
with an LLM provider. Most teammates should call the HTTP API; C3 can call the
Python service in-process. Start locally using [setup](setup.md).

## Choose the integration boundary

| Component | Integration |
|---|---|
| C1 patient UI | Upload/list/extract files, display literal excerpts and warnings, display summary and send explicit approval, download exports |
| C2 clinician UI | Check summary `approved` before displaying final handoff; download the corresponding export |
| C3 orchestration | Authorize the session, call `DocumentService`, keep extracted content outside official slot state until normal validation/review |
| C4 LLM adapter | Consume excerpts plus source locations as untrusted evidence; do not let documents supply system instructions or automatically change slots |
| C6 persistence | Implement `DocumentMetadataStore` and durable session/approval storage; retain source pointers, hashes, status and errors |

Cloud credentials stay in the backend. The optional shared `DOCUMENT_API_TOKEN`
is a development integration key, not patient login or per-user authorization.
It is required when cloud storage is selected. C3 must add a real access-control
layer before remote deployment. Never ship storage keys or a shared server token
inside a public frontend bundle.

## Supported files and processing semantics

| Input | Extraction | Source locations |
|---|---|---|
| UTF-8 `.txt` | Literal nonempty lines | `line` |
| `.pdf` | Embedded text; optional OCR for pages without text | `page` |
| `.docx` | Body paragraphs and table cells in document order, including nested tables | `paragraph`, or `table`/`row`/`column`/`cell_paragraph` |
| `.png`, `.jpg`, `.jpeg` | Optional Tesseract OCR | `image` |

Locations are one-based. Legacy `.doc`, macro-enabled Word formats, encrypted
PDFs, unsupported MIME/extension combinations and unsafe filenames are rejected.
Default upload size is 10 MiB. Further page/text/image/ZIP limits protect parsing;
see [configuration](storage-configuration.md). Extraction is synchronous and
bounded by these limits; there is no job queue or polling-job API.

DOCX headers, footers and embedded image text are not full-document extraction.
Embedded DOCX images produce a warning; upload them separately for OCR. Native
PDF text does not reproduce the original visual layout, and a PDF page with some
text is not also OCR'd for embedded image-only material. Keep the source available
for review instead of treating extracted text as a complete medical record.

Extraction returns `processed`, `partial` or `ocr_required`. Always read
`warnings`; `processed` means the extraction completed, not that the contents are
clinically verified. OCR output carries review warnings. Parsing failures return
an error and preserve metadata with `status=failed` and an `error_code`.

## HTTP routes

All paths below are relative to `http://127.0.0.1:8000`. Add
`Authorization: Bearer <DOCUMENT_API_TOKEN>` when a token is configured. `sid` is
an existing session ID; `id` is a document ID returned by upload/export.

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/api/documents/health` | — | Adapter readiness and OCR configuration |
| POST | `/api/sessions/{sid}/documents` | Multipart field **`file`** | 201 document metadata |
| GET | `/api/sessions/{sid}/documents` | — | 200 metadata array |
| GET | `/api/sessions/{sid}/documents/{id}` | — | 200 one metadata record |
| POST | `/api/sessions/{sid}/documents/{id}/extract` | — | 200 metadata including extraction |
| GET | `/api/sessions/{sid}/documents/{id}/download` | — | 200 binary file with attachment headers |
| DELETE | `/api/sessions/{sid}/documents/{id}` | — | 204, empty body |
| GET | `/api/sessions/{sid}/summary` | — | Current summary, approval state and `content_sha256` |
| POST | `/api/sessions/{sid}/summary/approve` | `{"content_sha256":"<hash from GET>"}` | 200 approved summary |
| POST | `/api/sessions/{sid}/exports` | `{"format":"pdf"}` or `{"format":"docx"}` | 201 export document metadata |

The existing GET summary route remains unauthenticated; new document, export,
approval and document-health routes share the token check. Metadata retrieval is
scoped to the specified session. Cross-session document IDs return 404, but this
isolation is not a replacement for authenticating the caller's right to a session.

Upload and export responses share these fields:

```json
{
  "document_id": "doc_<generated>",
  "session_id": "sess_<generated>",
  "filename": "synthetic.txt",
  "content_type": "text/plain",
  "size_bytes": 21,
  "sha256": "<64-character content digest>",
  "storage_backend": "local",
  "storage_key": "<opaque private object key>",
  "status": "uploaded",
  "created_at": "<UTC ISO 8601 timestamp>",
  "extraction": null,
  "error_code": null,
  "summary_ref": null,
  "summary_sha256": null
}
```

After successful extraction, the same record contains, for example:

```json
{
  "status": "processed",
  "extraction": {
    "status": "processed",
    "chunks": [
      {"text": "Synthetic note only.", "location": {"line": 1}, "method": "text"}
    ],
    "warnings": []
  }
}
```

Retain `(session_id, document_id, sha256, chunk.location, chunk.method)` with any
excerpt passed to C3/C4. The HTTP extraction endpoint does **not** feed excerpts
into the LLM or modify session slots. That handoff must use C3's normal validation
and patient review. Uploaded text, including embedded instructions, is source
data rather than application authority.

## Runnable Python HTTP example

Run the backend first. This example uses only a synthetic UTF-8 note. For a
configured integration token, export `DOCUMENT_API_TOKEN` in the caller's shell.

```python
import os
from pathlib import Path
import httpx

headers = {}
if token := os.environ.get("DOCUMENT_API_TOKEN"):
    headers["Authorization"] = f"Bearer {token}"

with httpx.Client(base_url="http://127.0.0.1:8000", headers=headers, timeout=30) as api:
    def call(method, path, **kwargs):
        response = api.request(method, path, **kwargs)
        response.raise_for_status()
        return response

    sid = call("POST", "/api/sessions", json={}).json()["session_id"]
    base = f"/api/sessions/{sid}"
    note = call("POST", f"{base}/documents", files={
        "file": ("synthetic.txt", b"Synthetic note only.\n", "text/plain")
    }).json()
    document_url = f"{base}/documents/{note['document_id']}"
    result = call("POST", f"{document_url}/extract").json()
    print(result["extraction"])  # Display text, locations AND warnings.

    # Existing C3 intake path; file extraction does not set these slots.
    call("POST", f"{base}/slots/chief_complaint",
         json={"action": "edit", "value": "Synthetic example: sore throat"})
    call("POST", f"{base}/complete")
    summary = call("GET", f"{base}/summary").json()
    print(summary["sections"], summary["patient_questions"])

    # In C1 this is an explicit patient action after displaying the full summary.
    if input("Type APPROVE after reviewing this synthetic summary: ") == "APPROVE":
        call("POST", f"{base}/summary/approve",
             json={"content_sha256": summary["content_sha256"]})
        exported = call("POST", f"{base}/exports", json={"format": "pdf"}).json()
        export_url = f"{base}/documents/{exported['document_id']}"
        Path("synthetic-approved-summary.pdf").write_bytes(
            call("GET", f"{export_url}/download").content
        )
        call("DELETE", export_url)
    call("DELETE", document_url)
```

For multipart upload in JavaScript, use `FormData` and **do not manually set its
Content-Type**; the browser adds the required multipart boundary. Download with
`fetch`, check `response.ok`, then use `response.blob()`. Do not append bearer
secrets to URLs. The full noninteractive synthetic example is
[`scripts/smoke.py`](../scripts/smoke.py).

## Approval and export contract

`POST /complete` generates a draft summary. C1 retrieves and displays its sections
and question list, then sends the returned `content_sha256` only after the patient
approves that exact content. The server computes the hash from the stored session
ID, summary reference, sections, questions and model using canonical JSON. Clients
should reuse the returned hash rather than independently reconstruct it.

A stale hash returns 409. Export requires both completion and a current approval;
changing stored summary content invalidates approval. Export renders the stored
approved snapshot, never client-supplied arbitrary text. Its metadata includes
`summary_ref` and `summary_sha256`; download it through the same document route.
Completing the session still prevents later slot edits in the existing C3 flow;
a full post-completion revision UI is separate work.

PDF and DOCX retain section/question text with layout and identifying references.
Default PDF fonts cover Western Latin and GB2312 simplified Chinese; unsupported
glyphs fail explicitly. For other scripts, set a suitable TrueType font path
as `C5_PDF_FONT_PATH` in the environment or `backend/.env`, or choose DOCX. DOCX retains Unicode and uses
the recipient's fonts. The renderer does not call an LLM or infer additional facts.

## In-process Python service (C3)

From `backend/`, a self-contained local example is:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.config import Settings
from app.core.flow import start_session
from app.core.store import InMemorySessionStore
from app.utils.document_service import DocumentService, InMemoryDocumentMetadataStore
from app.utils.storage import LocalStorage

with TemporaryDirectory() as root:
    settings = Settings(_env_file=None, storage_backend="local", storage_local_root=Path(root))
    sessions = InMemorySessionStore()
    state = start_session()
    sessions.create(state)
    # A real caller must authorize its right to this session before using C5.
    sessions.get(state.session_id)
    tools = DocumentService(settings, LocalStorage(Path(root)), InMemoryDocumentMetadataStore())
    record = tools.upload(state.session_id, "synthetic.txt", b"Synthetic note only.\n", "text/plain")
    record = tools.extract(state.session_id, record.document_id)
    print(record.extraction.model_dump())
    metadata, contents = tools.download(state.session_id, record.document_id)
    tools.delete(state.session_id, record.document_id)
```

The running app reuses `get_document_service()` from
`app.utils.document_service`; do not instantiate a fresh metadata store for each
request.

| Method | Return |
|---|---|
| `upload(session_id, filename, data, content_type=None)` | `DocumentRecord` |
| `get(session_id, document_id)` | `DocumentRecord` |
| `list(session_id)` | `list[DocumentRecord]` |
| `extract(session_id, document_id)` | `DocumentRecord` with extraction |
| `download(session_id, document_id)` | `(DocumentRecord, bytes)` |
| `delete(session_id, document_id)` | `None` |
| `export(state, summary, format)` | Export `DocumentRecord`; verifies approval of the supplied stored snapshot |

The service does not independently look up or authenticate sessions. Obtain
`state` and `summary` from the trusted C3 store after authorizing access, and use
the shared approval flow rather than manually forging approval fields. A lower
level `render_summary` function only renders; it is not the access/approval gate.

## Failure handling and persistence seam

API errors use `{"error":{"code":"...","message":"...","request_id":"req_..."}}`.
Inspect status/code instead of matching human-readable messages.

| Status | Typical cause | Client response |
|---|---|---|
| 401 | Missing/wrong integration token | Fix caller configuration |
| 404 | Unknown session/document or unavailable object | Refresh metadata; do not guess another session ID |
| 409 | Summary incomplete, unapproved or stale approval hash | Retrieve/display current content and repeat the proper review action |
| 413 | Upload/export exceeds limit | Choose a smaller source; inspect configured limits |
| 422 | Unsupported/empty/corrupt document, validation/processing/rendering failure | Show the code and actionable message; preserve the source for review |
| 503 | Storage/configuration/integrity failure | Retry after configuration or storage recovery; do not imply success |

Extraction can succeed with warnings; check its semantic status as well as HTTP
200. Retrying an upload/export creates a new object, so retain successful IDs to
avoid unnecessary duplicates. Delete removes metadata only after storage deletion
succeeds, enabling a retry on provider failure.

C6 can replace `InMemoryDocumentMetadataStore` through `DocumentMetadataStore`
(`save`, `get`, `list`, `delete`). Persist every `DocumentRecord` field and its
extraction result, with session ownership constraints. Pair it with durable
session/summary/approval storage and transaction/cleanup strategy. Current stores
lose metadata on restart; bytes can remain orphaned. No migration, background
cleanup worker, automatic slot import or durable audit log is supplied by C5.
