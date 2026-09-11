# Implementation Status

Living record of what is actually built. Updated in the same change as the code.

Last updated: 2026-09-10

Backend requires **Python 3.11+** (models use 3.10+ union syntax). macOS system
Python 3.9 fails at import.

## Component ownership

| ID | Component | Owner |
|----|-----------|-------|
| C3 | Backend — Core Logic | Robin Kim |
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

### In progress

- (nothing yet)

### Next (outside the skeleton)

- Explicit "patient approves summary" gate (with C1/C2) before `completed` feeds
  the clinician view.
- Swap `InMemorySessionStore` for C6's DB-backed store.
- Replace `FakeLLM` with C4's adapter via `app/api/deps.py::get_llm`.
- Safety patterns/wording need team + supervisor sign-off.

### Stubs / deferred

- `database_url` in settings is unused until C6 wires persistence.
- `llm_*` settings unused until C4 wires the adapter.
- Sessions live in process memory only — lost on restart until C6.

## How to run

```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.core.main:app --reload   # http://localhost:8000/api/health
pytest
```
