# Implementation Status

Living record of what is actually built. Updated in the same change as the code.

Last updated: 2026-09-10

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

### In progress

- (nothing yet)

### Next

- `feat/c3-domain-models` — Pydantic models (`SessionState`, `Slot`, `Candidate`,
  `TranscriptEntry`), versioned consultation schema (`SCHEMA_VERSION = "0.1"`,
  ~5–8 slots), LLM boundary `Protocol` in `app/llm/base.py` + `FakeLLM` in
  `app/llm/fake.py`.
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
