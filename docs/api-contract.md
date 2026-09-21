# API Contract — draft v0.1

> **Change rule:** any change to the API (routes, payloads, status objects, slot
> schema, error shape, or LLM candidate format) must be made in the **same PR**
> that changes the code, and this document updated to match. Assign the owner of
> each affected component (backend API, LLM extraction, frontend patient,
> frontend clinician) as a reviewer on that PR.

Status: **draft v0.1** — shapes are provisional and may change without deprecation
until v1.0.

## Conventions

- Base URL: `/api`
- Content type: `application/json`, except multipart document upload and binary download
- Timestamps: ISO 8601 UTC (`2026-09-10T04:20:00Z`)
- IDs: opaque strings; do not parse

---

## 1. Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `GET`  | `/api/health` | Liveness check |
| `POST` | `/api/sessions` | Create a pre-consultation session |
| `GET`  | `/api/sessions/{session_id}` | Fetch full session state |
| `POST` | `/api/sessions/{session_id}/messages` | Submit a patient message; returns updated state + next prompt |
| `POST` | `/api/sessions/{session_id}/slots/{slot_id}` | Confirm, edit, or skip a slot value |
| `POST` | `/api/sessions/{session_id}/complete` | Finalise intake and generate clinician summary |
| `GET`  | `/api/sessions/{session_id}/summary` | Review summary, content hash and approval state |
| `POST` | `/api/sessions/{session_id}/summary/approve` | Approve the reviewed server summary version |

Session bodies are JSON. `POST /api/sessions` takes `{"patient_ref": null, "locale": "en-AU"}`
(both optional) and returns the [session state object](#2-session-state-object)
with `201`.

Example — `POST /api/sessions/{session_id}/messages`:

```json
{
  "request": {
    "text": "I've had a sore throat and a fever since Monday"
  },
  "response": {
    "session_id": "sess_a1b2c3",
    "status": "in_progress",
    "next_prompt": {
      "slot_id": "symptom_duration_days",
      "text": "How many days have you had these symptoms?"
    },
    "updated_slots": ["chief_complaint", "associated_symptoms"],
    "stopped": false,
    "stop_reason": null,
    "safety": { "triggered": false, "category": null, "message": null },
    "completeness": { "coverage": 0.0, "resolution": 0.0, "unresolved_required": ["symptom_duration_days", "symptom_severity", "associated_symptoms", "current_medications", "allergies"] }
  }
}
```

When `safety.triggered` is `true` the turn short-circuits: `stopped` is `true`,
`updated_slots` is empty, `next_prompt` is `null`, and `safety.message` carries
the fixed wording to show the patient.

Example — `POST /api/sessions/{session_id}/slots/{slot_id}`:

```json
{
  "request": { "action": "edit", "value": "moderate" },
  "response": {
    "session_id": "sess_a1b2c3",
    "status": "in_progress",
    "slot_id": "symptom_severity",
    "outcome": "accepted",
    "detail": null,
    "next_prompt": { "slot_id": "current_medications", "text": "..." },
    "completeness": { "coverage": 0.09, "resolution": 0.33, "unresolved_required": ["associated_symptoms", "current_medications", "allergies"] }
  }
}
```

`action` is `confirm` (promotes the top candidate, or uses `value` if given),
`edit` (requires `value`), `skip` (patient declined to answer), or `unknown`
(patient answered "I don't know" — distinct from `skip`, see
[slot schema](#3-slot-schema)). `outcome` is `accepted` / `rejected` /
`contradiction` / `inactive` / `unknown_slot`; a `rejected` value returns `422`.

Example — `POST /api/sessions/{session_id}/complete` → `{"session_id", "status": "completed", "summary_ref": "sum_sess_a1b2c3"}`.

Example — `GET /api/sessions/{session_id}/summary` (only after `complete`, else `409`):

```json
{
  "session_id": "sess_a1b2c3",
  "summary_ref": "sum_sess_a1b2c3",
  "sections": { "Main reason for the visit": "sore throat", "Current severity": "moderate" },
  "patient_questions": ["What are the most likely causes of my symptoms?"],
  "model": "fake-llm-0",
  "content_sha256": "<64 lowercase hexadecimal characters from server>",
  "approved": false,
  "approved_at": null
}
```

`completed` means intake has finished and the summary is available for review;
it does **not** mean the patient has approved it. After displaying the entire
summary, C1 sends `POST /api/sessions/{session_id}/summary/approve` with
`{"content_sha256": "<hash from GET summary>"}` on an explicit patient action.
The response has the same shape as GET summary with `approved: true` and an
ISO timestamp. Repeating approval of the same version is idempotent. A stale
hash returns `SUMMARY_VERSION_CONFLICT` (409); approval before completion
returns `SUMMARY_NOT_READY` (409).

The hash covers session ID, summary reference, sections, patient questions and
model using canonical UTF-8 JSON. Changes invalidate approval at retrieval and
export time. C2 must display only `approved: true` content as a final handoff.
The review GET remains available before approval to preserve patient review.
The new approval route uses the document integration-token dependency described
in section 6; the existing session routes still lack patient authentication.

---

## 2. Session state object

Returned by `GET /api/sessions/{session_id}` and embedded (partially) in message
responses.

- `status`: `in_progress` | `awaiting_confirmation` | `completed` | `abandoned`
- `schema_version`: consultation schema the session was created against (currently `"0.2"`)
- `slots`: map of `slot_id` → [slot object](#3-slot-schema)
- `current_prompt`: the slot the intake flow is currently asking about, or `null`
- `history`: append-only audit trail of slot state transitions (correction
  history) — see below
- `summary_ref`: id of the generated summary once `status` is `completed`
- `summary_approved_sha256`, `summary_approved_at`: nullable approval record;
  clients should use GET summary's derived `approved` field to check freshness

```json
{
  "session_id": "sess_a1b2c3",
  "status": "in_progress",
  "created_at": "2026-09-10T04:15:00Z",
  "updated_at": "2026-09-10T04:20:00Z",
  "patient_ref": "pat_9f8e7d",
  "locale": "en-AU",
  "schema_version": "0.2",
  "current_prompt": { "slot_id": "symptom_duration_days", "text": "How many days have you had these symptoms?" },
  "slots": {
    "chief_complaint": {
      "slot_id": "chief_complaint",
      "label": "Chief complaint",
      "type": "string",
      "required": true,
      "value": "Sore throat and fever",
      "status": "candidate",
      "source": "llm"
    }
  },
  "transcript": [
    { "role": "patient", "text": "I've had a sore throat and a fever since Monday", "at": "2026-09-10T04:19:50Z" },
    { "role": "assistant", "text": "How many days have you had these symptoms?", "at": "2026-09-10T04:20:00Z" }
  ],
  "history": [
    {
      "slot_id": "symptom_severity",
      "event": "corrected",
      "previous_value": "mild",
      "previous_status": "confirmed",
      "new_value": "moderate",
      "new_status": "confirmed",
      "source": "patient",
      "at": "2026-09-10T04:21:00Z"
    }
  ],
  "summary_ref": null
}
```

`history` entries are append-only — nothing in the backend ever edits or removes
one. `event` is `confirmed` (first value set), `corrected` (a confirmed value
changed), `skipped`, `marked_unknown`, or `reopened` (a skipped/unknown slot
got new candidate evidence). Re-confirming an already-confirmed slot with the
same value does not add an entry, and a rejected edit (`422`) never reaches
history. C6 persists this list verbatim — it's the provenance/correction-history
trail the proposal requires.

---

## 3. Slot schema

One structured field the intake flow tries to fill.

- `type`: `string` | `number` | `boolean` | `enum` | `date` | `list`
- `status`: `empty` | `candidate` (LLM-proposed, unconfirmed) | `confirmed` |
  `skipped` (patient declined to answer) | `unknown` (patient answered "I don't
  know" — an affirmative answer, not a decline; present it differently in the
  clinician summary)
- `source`: `patient` (typed directly) | `llm` (extracted) | `clinician` (overridden)
- `options`: present only when `type` is `enum`
- `candidates`: [LLM candidate values](#5-llm-extraction-candidate-value) not yet confirmed

```json
{
  "slot_id": "symptom_duration_days",
  "label": "Symptom duration (days)",
  "type": "number",
  "required": true,
  "options": null,
  "value": null,
  "status": "candidate",
  "source": "llm",
  "candidates": [
    {
      "value": 3,
      "confidence": 0.72,
      "evidence_span": "since Monday",
      "model": "gpt-4o-mini",
      "extracted_at": "2026-09-10T04:20:01Z"
    }
  ],
  "updated_at": "2026-09-10T04:20:01Z"
}
```

---

## 4. Error response format

All non-2xx responses use this envelope. HTTP status carries the class; `error.code`
is the stable machine string.

- `code`: stable `SCREAMING_SNAKE_CASE` identifier
- `message`: human-readable, safe to show to the patient
- `details`: optional array of field-level problems
- `request_id`: echo for support / log correlation

```json
{
  "error": {
    "code": "SLOT_VALIDATION_FAILED",
    "message": "Symptom duration must be a whole number of days.",
    "details": [
      { "field": "value", "issue": "expected number, got \"a while\"" }
    ],
    "request_id": "req_5k4j3h"
  }
}
```

Common codes: `SESSION_NOT_FOUND` (404), `SESSION_ALREADY_COMPLETED` (409),
`SLOT_NOT_FOUND` (404), `SLOT_VALIDATION_FAILED` (422),
`REQUEST_VALIDATION_FAILED` (422, malformed/mistyped body — FastAPI's own
validation, normalised into this envelope), `SUMMARY_NOT_READY` (409),
`LLM_UNAVAILABLE` (503), `RATE_LIMITED` (429), `INTERNAL` (500, catch-all for
anything unhandled — also normalised into this envelope).

---

## 5. LLM extraction candidate value

Emitted by `app/llm/` when parsing a patient message into slot values. Never
written straight to `slot.value`; it lands in `slot.candidates[]` with
`status: "candidate"` until confirmed by the patient or clinician.

- `slot_id`: target slot
- `value`: typed per the slot's `type`
- `confidence`: model-reported, `0.0`–`1.0`
- `evidence_span`: verbatim substring of the patient message supporting the value
- `rationale`: short model explanation (for review UI / debugging)
- `model`: model id used, for reproducibility

```json
{
  "slot_id": "associated_symptoms",
  "value": ["fever", "sore throat"],
  "confidence": 0.88,
  "evidence_span": "a sore throat and a fever",
  "rationale": "Both symptoms stated explicitly in the same sentence as the complaint.",
  "model": "gpt-4o-mini",
  "extracted_at": "2026-09-10T04:20:01Z"
}
```

---

## 6. C5 document tools and C6 metadata seam

Detailed examples, Python calls and browser integration are in
[c5-tools.md](c5-tools.md). These are ordinary HTTP/Python tools, not an MCP
server or automatically registered LLM tools.

Every route in this section, plus summary approval, requires
`Authorization: Bearer <DOCUMENT_API_TOKEN>` when that setting is nonempty.
Cloud configuration requires a token; tokenless local development must bind to
loopback. This shared integration token does not identify patients or implement
per-user access control. C3 must provide authenticated session ownership before
public deployment. The proxy checks that a document belongs to the requested
session; a different session returns `DOCUMENT_NOT_FOUND` (404).

| Method | Path | Request | Success |
| --- | --- | --- | --- |
| GET | `/api/documents/health` | None | 200 `{status, storage_backend, ocr_enabled}` |
| POST | `/api/sessions/{sid}/documents` | Multipart `file` | 201 document record |
| GET | `/api/sessions/{sid}/documents` | None | 200 array of records |
| GET | `/api/sessions/{sid}/documents/{did}` | None | 200 record |
| POST | `/api/sessions/{sid}/documents/{did}/extract` | None | 200 record with extraction |
| GET | `/api/sessions/{sid}/documents/{did}/download` | None | 200 raw file, attachment, no-store |
| DELETE | `/api/sessions/{sid}/documents/{did}` | None | 204 empty body |
| POST | `/api/sessions/{sid}/exports` | JSON `{"format":"pdf"}` or `docx` | 201 export record |

A document record contains:

```json
{
  "document_id": "doc_<opaque UUID>",
  "session_id": "sess_<opaque ID>",
  "filename": "notes.txt",
  "content_type": "text/plain",
  "size_bytes": 21,
  "sha256": "<file SHA-256>",
  "storage_backend": "local",
  "storage_key": "c5/<session ID hash>/<document ID>.txt",
  "status": "processed",
  "created_at": "2026-09-22T00:00:00Z",
  "extraction": {
    "status": "processed",
    "chunks": [{"text": "Synthetic source text", "location": {"line": 1}, "method": "text"}],
    "warnings": []
  },
  "error_code": null,
  "summary_ref": null,
  "summary_sha256": null
}
```

`storage_key` is an internal opaque locator, not a URL or permission to access
storage directly. Upload stores bytes and metadata with `uploaded` status;
extraction is an explicit synchronous operation. It can produce `processed`,
`partial`, `ocr_required`, or an error that marks the record `failed` with an
`error_code`. A failed object can be inspected, retried or deleted. Exported
records start as `exported` and include the approved summary reference/hash.

Locations use one-based `page`, `paragraph`, `table`/`row`/`column` (with
`cell_paragraph` for DOCX cells), `line`, or `image`. OCR chunks use
`method: "ocr"` and require source review. Disabled/unavailable OCR returns
explicit warnings; a PDF containing text pages and unprocessed scanned pages
is `partial`. Extraction **never** changes slots, transcript or approval state.
C3/C4 must treat the content as untrusted evidence, retain source references,
validate candidates, and collect patient confirmation separately.

Exports accept only a format, not arbitrary client text or an approval boolean.
The server retrieves and checks the approved snapshot. Unapproved or changed
content returns `SUMMARY_NOT_APPROVED` (409). No model is called during export.

Supported inputs: UTF-8 TXT, PDF, non-macro DOCX, PNG and JPEG. Legacy DOC,
encrypted PDF, invalid packages and unsupported MIME/extension combinations are
rejected. Default upload/export limit is 10 MiB (hard maximum 20 MiB), PDF limit
50 pages, extraction/export text limit 200,000 characters, image limit 20 million
pixels. The multipart body is also bounded to the file limit plus 64 KiB header
overhead before parsing. DOCX ZIP expansion is limited to 50 MiB / 2,000 entries.
Full format/Unicode/OCR limits are recorded in the tool guide.

Additional error codes (same section-4 envelope): `DOCUMENT_ACCESS_DENIED`
(401), `DOCUMENT_NOT_FOUND` / `FILE_NOT_FOUND` (404), `FILE_TOO_LARGE` (413),
`INVALID_FILENAME`, `EMPTY_FILE`, `UNSUPPORTED_FILE_TYPE`,
`DOCUMENT_PARSE_FAILED`, `EMPTY_DOCUMENT`, `DOCUMENT_LIMIT_EXCEEDED`,
`DOCUMENT_RENDER_FAILED` (normally 422; service export limit can return 413),
`DOCUMENT_INTEGRITY_FAILED`, `STORAGE_CONFIGURATION_ERROR`,
`STORAGE_UNAVAILABLE` (503). OCR unavailability/timeouts are warnings in the
extraction result so successfully extracted pages are not lost.

`DocumentMetadataStore` defines `save`, session-scoped `get`, `list` and
`delete`. C6 can provide a durable implementation and replace
`get_document_service`; object bytes remain in the chosen storage adapter.
Session summaries and approvals must be persisted together by C6. The supplied
metadata adapter is in memory and supports one process only. Object writes are
rolled back best-effort if metadata saving fails; failed storage deletes retain
metadata for retry. A persistent deployment needs transactions/outbox cleanup,
not a claim of distributed atomicity from these two separate stores.
