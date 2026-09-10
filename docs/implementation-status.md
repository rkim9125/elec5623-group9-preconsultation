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
  - Tests: `tests/test_schema.py`, `tests/test_fake_llm.py`. 12 passing total.

### In progress

- (nothing yet)

### Next

- `feat/c3-state-engine` — `app/core/engine.py`: candidate validation, state
  transitions, contradiction/correction handling, conditional-slot activation,
  completeness/resolution, next-slot selection, stopping rules, safety check.
- `feat/c3-session-api` — wire `app/api/sessions.py` to the engine, in-memory
  session store, error envelope, integration tests with `FakeLLM`.

### Stubs / deferred

- `database_url` in settings is unused until C6 wires persistence.
- `llm_*` settings unused until C4 wires the adapter.

## How to run

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.core.main:app --reload   # http://localhost:8000/api/health
pytest
```
