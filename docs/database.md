# C6: Database and data access

The backend uses SQLAlchemy 2.x and SQLite for local development. Schema changes
are versioned with Alembic. Production database selection remains a team decision;
this implementation is tested against SQLite, not a claim of PostgreSQL support.

## Setup (Windows PowerShell, from `backend`)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.db.manage init
.\.venv\Scripts\python.exe -m app.db.manage check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn app.core.main:app --reload
```

`init` upgrades the database to the latest migration and is safe to repeat. It
does not delete records. An unversioned database created manually with
`Base.metadata.create_all()` is **not** automatically adopted: use a fresh
development database or agree a migration/backup plan first. Earlier tutorial
checks used an in-memory database, so they do not create this problem.

Configuration is `DATABASE_URL=sqlite:///./preconsult.db`. Relative SQLite paths
are resolved against `backend`, even if the current working directory differs.
Dates are stored as ISO 8601 strings including their UTC offset; Pydantic restores
timezone-aware datetimes. Dynamic values use JSON, preserving null, lists,
numbers and booleans. Enum values are stored as their existing C3 strings.

For an isolated fresh demo environment, set a **new** file name rather than
deleting the working database:

```powershell
$env:DATABASE_URL = "sqlite:///./preconsult-demo-new.db"
.\.venv\Scripts\python.exe -m app.db.manage init
.\.venv\Scripts\python.exe -m app.db.manage seed
.\.venv\Scripts\python.exe -m app.db.manage check
```

`seed` creates only synthetic `demo_c6_001`, including a correction, unknown and
skipped slots. Running it again preserves the existing demo. It uses FakeLLM and
needs no API key. `Remove-Item Env:DATABASE_URL` returns the shell to the default
configuration (or `.env` value); it does not remove any database file.

Do not commit `.env`, `.db`, SQLite journal files or real patient data. There is
no general-purpose destructive reset endpoint. Test databases live in pytest
temporary directories and are isolated from development data. Before deleting
an old demo manually, stop its server and verify the exact file and backup needs.

## Data model

| Table | Purpose / identity |
|---|---|
| sessions | Existing SessionState metadata; internal version for stale-write detection |
| messages | Raw transcript, stable message ID; unique session + sequence |
| slot_states | Current slot metadata, value, state and candidate list; session + slot ID |
| slot_history | Verbatim C3 correction history; append-only session + sequence |
| candidate_records | Immutable archived candidate payloads, including evidence/model/time |
| summary_versions | Generated content versions, model, creation time, explicit approval metadata |
| audit_events | Append-only DAO events: created/saved/generated/approved |
| attachments | C5 metadata and object key; no file bytes |
| source_references | Explicit message or attachment source, quote/location, optional archived candidate |
| model_calls | C4 model/prompt version, tokens, latency, status/error code |

Sessions have many messages, slots, history entries, summaries and audit events.
Slots can have many archived candidates and source references. Source references
use composite foreign keys so a source/candidate cannot point into another
session or slot. SQLite foreign-key checks are enabled on every connection.
Deletion does not silently cascade through audit/provenance records.

Candidate archives are needed because C3 clears the current candidate list when
the patient confirms/skips a slot. Archiving preserves *observed persisted*
candidates, not intermediate states which callers never saved. Identical
candidate payloads in the same slot are idempotent; different extraction times
are distinct records. No DAO infers a source-message link from a text match.

## C3 integration and transactions

The existing five SessionStore methods are implemented by DatabaseSessionStore:
`create`, `get`, `save`, `put_summary`, `get_summary`.

```python
from app.db.session import store_transaction

with store_transaction() as store:
    state = store.get(session_id)
    # C3 applies validated changes to state here.
    store.save(state)
```

Use a fresh store/ORM session per request, and `get()` before `save()` in the
same store. Methods flush but never commit. Exiting the transaction commits all
operations; any uncaught exception rolls them all back. Do not catch a write
failure and then try to commit that transaction.

The FastAPI dependency uses `Depends(get_store, scope="function")` so the
transaction commits before a successful response is sent. This is why FastAPI
>= 0.121 is required. The existing complete endpoint's `put_summary` and `save`
are atomic without moving business decisions into the DAO.

An internal session revision uses compare-and-swap. A stale request receives
`409 PERSISTENCE_CONFLICT`; reload before retrying. SQLite lock contention is
also surfaced as a retryable 409. Messages and history are checked as unchanged
prefixes and only new entries appended; repeated saves do not add duplicates.
These invariants are enforced by the DAO, not tamper-proof database access rules.

Creation timestamps and consultation schema versions cannot be rewritten by
save. C6 does not run planning, field-value validation, or approval decisions.
It preserves C3's `updated_at` rather than inventing business timestamps.

## Additional DAO contracts

All methods below run inside the same store_transaction block. List methods
return detached dictionaries, not ORM objects tied to a closed session.

- `list_messages(session_id)` exposes stable message IDs and sequence numbers.
- `list_candidates(session_id)` exposes archived candidate IDs and payloads.
- `list_summary_versions(session_id)` returns all versions in ascending order.
- `record_summary_approval(session_id, version, approved_by)` records an action
  that C3 has already authorized. It does not authenticate a patient.
- `get_approved_summary(session_id)` returns the latest explicitly approved
  version as `{version, summary_id, summary}` or raises SummaryNotReady.
- `append_audit(session_id, event, actor="system", details={})`, `list_audit`.
- `add_attachment(session_id, object_key=..., filename=..., media_type=...,
  size_bytes=..., status="uploaded")` and `list_attachments`.
- `add_source_reference(session_id, slot_id, message_id=... OR attachment_id=...,
  candidate_id=None, quote=None, location={})` and `list_source_references`.
  Exactly one origin must be supplied. `location` can hold a page or offsets;
  C3/C4/C5 remain responsible for source interpretation and grounding validation.
- `record_model_call(session_id, operation=..., model=..., status=...,
  prompt_version=None, input_tokens=None, output_tokens=None, latency_ms=None,
  error_code=None)` and `list_model_calls`. Store no credentials or raw prompts.

## Explicit remaining cross-component work

- The existing `/complete` and `/summary` API contract has **no explicit patient
  approval gate**. C6 preserves that contract and never treats `completed` as
  approval. `get_summary` returns the latest generated version for compatibility.
  C3/C1/C2 must add authorization, version-specific approval and approved-only
  clinician access before claiming a patient-approved handoff. A later draft
  does not rewrite a previously approved version; visibility/invalidation after
  corrections is a C3 policy decision.
- C3's public `summary_ref` remains its existing stable alias; stored
  `summary_id` and `version` identify individual content versions. New API
  contracts should expose the exact version when introducing approval.
- Current C4 FakeLLM/LLM interfaces do not carry explicit message IDs or a
  telemetry callback. Candidates/evidence spans are archived automatically,
  but exact source links and model-call telemetry require callers to supply
  records through these DAO methods. Do not claim those integrations are done.
- Attachment metadata support does not implement C5 upload, OCR or object access.
- A failed request rolls back its request-scoped telemetry too. C4 should use a
  separate short transaction for failure telemetry that must survive rollback.

## Migrations and verification

`alembic/versions/c6_0001_initial.py` contains frozen schema operations, independent
of live model definitions. For future changes, create and review a new migration:

```powershell
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "describe change"
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Never edit an already-shared migration to change an existing database. Downgrades
can remove data and are not the normal development reset procedure.

Tests migrate fresh temporary databases and cover round trips, separate-process
reopening, schema drift, correction-history ordering, candidate retention,
summary versioning, explicit approvals, same-session reference ownership,
rollback (including API and commit failures), stale writes and existing C3 APIs.

For a manual persistence demo, create a session in Swagger, send a synthetic
message, edit a slot twice and note its ID. Stop/restart the server, retrieve
the same session, and inspect its transcript and history. The earlier in-memory
sessions are not automatically transferred; create a new one after this change.
