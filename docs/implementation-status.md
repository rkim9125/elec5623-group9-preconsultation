# Implementation Status

Living record of what is actually built. Updated in the same change as the code.

Last updated: 2026-09-22

Backend requires **Python 3.11+** (models use 3.10+ union syntax). macOS system
Python 3.9 fails at import.

## Component ownership

| ID | Component | Owner |
|----|-----------|-------|
| C3 | Backend — Core Logic | Robin Kim |
| C5 | Document utilities and storage (this implementation) | Guopeng Tan |
| C7 | Specification and test environment (this implementation) | Guopeng Tan |
| others | — | TBD (see docs component breakdown) |

## C3 — Backend: Core Logic

### Done

- **App skeleton** (`feat/c3-app-skeleton`)
  - `app/core/config.py` — `Settings` via pydantic-settings, all keys have dev
    defaults, `.env` optional. `cors_origins` helper splits `FRONTEND_ORIGIN`.
  - `app/core/main.py` — `create_app()` factory, CORS middleware, `/api` router
    mount. Exposes `app` for `uvicorn app.core.main:app`.
  - `app/api/health.py` — `GET /api/health -> {"status": "ok"}`.
  - `tests/test_health.py` — passes. `backend/pytest.ini` sets `pythonpath = .`.

- **Domain models + schema + LLM boundary** (`feat/c3-domain-models`)
  - `app/core/models.py` — `SessionState`, `Slot`, `Candidate`, `TranscriptEntry`,
    `Prompt`, and the `SlotType` / `SlotStatus` / `SlotSource` / `SessionStatus` /
    `TranscriptRole` enums. Mirrors api-contract.md sections 2, 3, 5.
  - `app/core/schema.py` — `SCHEMA_VERSION = "0.1"`, `CONSULTATION_SCHEMA`
    (8 slots), `SlotDef` / `SlotActivation`, `build_initial_slots()`,
    `get_slot_def()`, `all_slot_ids()`. One conditional slot
    (`fever_duration_days`, activates when `associated_symptoms` contains
    `"fever"`).
  - `app/llm/base.py` — `LLMClient` `Protocol` (`extract_candidates`,
    `phrase_question`, `generate_summary`), `ExtractedCandidate`,
    `GeneratedSummary`. This is the C3<->C4 contract.
  - `app/llm/fake.py` — `FakeLLM`, rule-based, no network. Implements the
    protocol so C3 can be built/tested without C4.
  - Tests: `tests/test_schema.py`, `tests/test_fake_llm.py`.

- **Deterministic state engine** (`feat/c3-state-engine`)
  - `app/core/engine.py` — `validate_value` (per SlotType), `apply_candidate` /
    `apply_extraction` (record LLM candidates, never auto-confirm),
    `confirm_slot` / `edit_slot` / `skip_slot` (patient actions),
    `detect_contradiction`, `is_slot_active` / `active_slot_defs` (conditional
    slots evaluated dynamically, no stored flag). Outcomes: accepted / rejected /
    contradiction / inactive / unknown_slot.
  - `app/core/planner.py` — `compute_completeness` (coverage vs resolution),
    `select_next_slot` (required-first, schema order), `should_stop`
    (all-required-addressed / question-limit / abandoned). `DEFAULT_MAX_QUESTIONS
    = 12`.
  - `app/core/safety.py` — `check_safety`: regex match against `SAFETY_RULES`
    (cardiac, breathing, stroke, anaphylaxis, self_harm, severe_bleeding) →
    fixed approved wording + stop. **Patterns/wording are placeholders pending
    team + supervisor sign-off.** Not triage or diagnosis.
  - Tests: `tests/test_engine.py`, `tests/test_planner.py`, `tests/test_safety.py`.
  - `tests/conftest.py` adds `make_state()` / `state` fixture.

- **Session API** (`feat/c3-session-api`)
  - `app/core/errors.py` — `AppError` hierarchy (`SESSION_NOT_FOUND`,
    `SLOT_NOT_FOUND`, `SESSION_ALREADY_COMPLETED`, `SLOT_VALIDATION_FAILED`,
    `SUMMARY_NOT_READY`) + `install_error_handlers` emitting the section-4
    envelope with a `request_id`.
  - `app/core/store.py` — `SessionStore` Protocol + `InMemorySessionStore`
    (the C6 swap point). Holds sessions and generated summaries.
  - `app/core/flow.py` — `start_session`, `ingest_message` (transcript → safety →
    extract → apply → advance), `advance_after_action`, `finalise`.
  - `app/api/deps.py` — `get_store`, `get_llm` (returns `FakeLLM`; C4 swaps here).
  - `app/api/schemas.py` — HTTP request/response DTOs, separate from domain models.
  - `app/api/sessions.py` — all 7 endpoints from api-contract.md, wired into
    `app/core/main.py`.
  - Tests: `tests/test_sessions_api.py` — create/fetch, error envelope, message
    extraction, safety short-circuit, confirm/edit/skip, full flow to summary,
    completion conflicts.

Total: 66 tests passing. First end-to-end flow (Milestone 2 backend side) works
against `FakeLLM`.

- **Error envelope coverage fix** (`fix/c3-error-envelope-coverage`)
  - Found while smoke-testing the merged skeleton by hand: a malformed/mistyped
    request body returned FastAPI's default `{"detail": [...]}` shape instead
    of the section-4 envelope — a real contract violation, not just a missing
    nicety.
  - `app/core/errors.py` now also registers handlers for
    `RequestValidationError` (`REQUEST_VALIDATION_FAILED`, 422) and a catch-all
    `Exception` (`INTERNAL`, 500), both emitting the same envelope as
    `AppError`. `docs/api-contract.md` updated with the two extra codes.
  - Tests: `test_malformed_json_body_still_uses_the_error_envelope`,
    `test_wrong_field_type_still_uses_the_error_envelope`.

Total: 68 tests passing. Manually smoke-tested end to end against a live
`uvicorn` process (create → message → confirm/edit → complete → summary) —
matches the automated tests.

- **"I don't know" vs "skip" as distinct slot states** (`feat/c3-unknown-slot-status`)
  - Prompted by comparing our design against Infermedica's evidence model
    (present/absent/unknown tri-state) — `docs/component-breakdown.md` C1 scope
    already listed "I don't know" and "skip" as separate patient actions, but
    the engine only had one `SKIPPED` status for both.
  - `SlotStatus.UNKNOWN` added, distinct from `SKIPPED`: skip = declined to
    answer, unknown = tried and doesn't have the information. Both count toward
    coverage, neither toward resolution — same treatment as before, just split.
  - `app/core/engine.py`: new `mark_unknown()`. Also fixed a latent bug found
    while doing this: a new LLM candidate arriving for an already-skipped slot
    used to sit in `candidates[]` unused since only `EMPTY` promoted to
    `CANDIDATE` — now `SKIPPED`/`UNKNOWN` slots reopen for confirmation too.
  - `app/api/schemas.py` / `app/api/sessions.py`: `SlotActionRequest.action`
    gains `"unknown"`. `docs/api-contract.md` updated (section 3 status enum,
    section 1 slot-action example).
  - Tests added in `test_engine.py`, `test_planner.py`, `test_sessions_api.py`.

Total: 72 tests passing.

- **Consultation schema expanded to v0.2** — checked against a standard
  clinical history-taking checklist and a commercial intake product before
  writing more code, per team discussion:
  - [Evaluation of Prompt Design and Internal Reasoning in Chatbot-Based
    Medical History Taking](https://pmc.ncbi.nlm.nih.gov/articles/PMC13501399/)
    (JMIR Medical Informatics, 2026) — its coverage checklist has 6 domains:
    history of presenting complaint, associated symptoms, past medical
    history, family history, social history, other context.
  - [Infermedica's "Intake" interview
    type](https://developer.infermedica.com/documentation/platform-api/interview-types/intake/)
    — a commercial pre-visit intake product; same domains plus a
    User/Patient/Survey entity split relevant to C6's schema.
  - `SCHEMA_VERSION` bumped `"0.1"` → `"0.2"` (interface change — C4/C6 should
    review). `CONSULTATION_SCHEMA` grew from 8 to 24 slots, organised by the
    6 domains above (`app/core/schema.py`): HPC detail (onset, location,
    character, progression, triggers, relieving factors, treatments tried),
    associated symptoms (now including explicitly *denied* symptoms), past
    medical history (+ hospitalisations, specialist care), family history,
    social history (smoking, alcohol, occupation), and other context (travel,
    free-text notes).
  - `associated_symptoms` promoted to **required**; everything else new is
    **optional** — deliberately. `planner.should_stop()` still stops once
    required slots are addressed, even with optional slots empty, because the
    project boundary is "coverage of chosen fields," not an exhaustive
    history. Optional slots are opportunistic: filled by LLM extraction from
    free text, or by direct confirm/edit calls the UI can offer, but the
    planner will not proactively march through all of them. Documented on
    `should_stop`'s docstring so it isn't mistaken for an oversight later.
  - Tests: `test_slot_ids_are_unique`,
    `test_covers_the_six_history_taking_domains`,
    `test_associated_symptoms_is_required_but_richness_fields_are_optional` in
    `test_schema.py`; existing planner/session tests updated for the new
    active-slot counts and required set.

Total: 75 tests passing.

- **Correction / audit history tracking** (`feat/c3-correction-history`) —
  closes a real gap: the proposal requires provenance/correction history
  (P3), but `confirm_slot`/`edit_slot` used to just overwrite a value with no
  record of what it changed from or why.
  - `app/core/models.py`: `SlotHistoryEvent` enum (`confirmed`, `corrected`,
    `skipped`, `marked_unknown`, `reopened`) + `SlotHistoryEntry`
    (slot_id, event, previous/new value+status, source, timestamp).
    `SessionState.history: list[SlotHistoryEntry]` — append-only, alongside
    `transcript`.
  - `app/core/engine.py`: every state-changing function
    (`confirm_slot`/`edit_slot`, `skip_slot`, `mark_unknown`, and the
    reopen-a-skipped-slot path in `apply_candidate`) appends a history entry.
    Re-confirming a slot with the value it already has does not add a
    duplicate entry; a rejected edit never reaches history.
  - Exposed automatically via `GET /api/sessions/{id}` (embedded, same
    pattern as `transcript`) — no new endpoint. `docs/api-contract.md`
    section 2 updated.
  - Tests: 7 new cases in `test_engine.py` (one per event type, ordering,
    dedup, cross-slot isolation), plus an assertion in
    `test_sessions_api.py` that the trail comes through the API and skips
    rejected attempts.

Total: 82 tests passing.

### In progress

- (nothing yet)

### Next (outside the skeleton)

- C1/C2 should wire the new explicit summary approval API and require
  `approved: true` before a final clinician handoff. The backend gate is now
  implemented; the existing review GET intentionally remains available.
- Swap `InMemorySessionStore` for C6's DB-backed store — `SessionState.history`
  is exactly the correction-history/audit-log data C6's DAO needs to persist.
- Replace `FakeLLM` with C4's adapter via `app/api/deps.py::get_llm`.
- Safety patterns/wording need team + supervisor sign-off.

### Stubs / deferred

- `database_url` in settings is unused until C6 wires persistence.
- `llm_*` settings unused until C4 wires the adapter.
- Sessions live in process memory only — lost on restart until C6.

## C5 — Document utilities and object storage

### Implemented in this change

- `app/utils/document_processing.py`: validated TXT/PDF/DOCX/PNG/JPEG inputs,
  bounded extraction with source locations, explicit OCR-required/partial
  results, optional Tesseract + PDFium OCR. No clinical interpretation or slot
  updates. DOCX embedded images require separate extraction/manual review.
- `app/utils/document_rendering.py`: literal PDF/DOCX exports, pagination,
  markup escaping, Latin/CJK PDF fonts and optional custom TrueType font.
- `app/utils/storage.py`: private local files, AWS S3/S3-compatible and Aliyun
  OSS adapters. Atomic local writes, path/symlink protection, secret-safe errors,
  explicit readiness checks, cloud timeouts and optional SDK imports.
- `app/utils/document_service.py`: upload/list/get/extract/download/delete and
  approved-summary export tools; file hashes, status and error metadata; C6
  `DocumentMetadataStore` protocol with in-memory implementation.
- `app/api/documents.py`: session-scoped HTTP tools, bounded multipart bodies,
  integration token, download proxy and no public storage URLs.
- A minimal C3 integration adds version-bound summary approval. Export refuses
  draft/stale summaries; completion does not imply approval. Error envelopes
  now also cover HTTP/multipart parser errors.

### Verified and remaining limits

The automated suite covers parser/render roundtrips, source locations, OCR
disabled/mocked recognition, approval/version conflicts, cross-session access,
storage failures, rollback, limits, traversal, SDK contracts and the existing
C3 tests. Local validation passed 225 tests, offline synthetic smoke and the
actual running-server HTTP smoke for the complete document workflow.
Cloud adapter tests use fake SDK clients: **no real AWS/OSS account has been
provisioned or connected**. Tesseract recognition requires the optional runtime
and language packs; mocked OCR tests do not establish recognition accuracy.

The prototype is single-process. Metadata, summaries and approval records are
lost on restart while object bytes may remain; C6 persistence is pending.
The shared document integration key does not replace C3 patient authentication.
Existing session routes are unauthenticated, so use local synthetic-data demos.
The frontend scaffold still needs C1/C2 pages and has no complete build entry.

## C7 — Specification and test environment

- Populated implementation specification and C5 API/tool examples, plus
  English storage setup and Chinese handoff documentation.
- Bootable `.env.example`, tested direct dependency pins, separate cloud/OCR
  extras, setup/start scripts, synthetic smoke and confined local reset.
- Dockerfile/loopback compose recipe and an **inactive** GitHub Actions
  pytest/smoke template at `ci/backend.yml`.
  Container build requires Docker, which was unavailable on the implementation
  host; no container execution is claimed by the local validation.
- Active workflow publication was rejected because the publishing credential
  lacks workflow-write permission. After merge, an authorized maintainer can
  copy `ci/backend.yml` to `.github/workflows/backend.yml`, commit and publish it
  using the [activation steps](setup.md#enable-github-actions-after-merge).
  No GitHub Actions run or CI pass is claimed.
- No placeholder DB reset/migration or live LLM dependency: those remain C6/C4
  integration points and are identified in the specification.

## How to run

```bash
./scripts/setup.sh
./scripts/start.sh
# Another terminal, from repository root:
backend/.venv/bin/python -m pytest -q backend/tests
backend/.venv/bin/python scripts/smoke.py
```
