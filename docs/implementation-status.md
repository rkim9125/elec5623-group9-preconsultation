# Implementation Status

Living record of what is actually built. Updated in the same change as the code.

Last updated: 2026-09-23

Backend requires **Python 3.11+** (models use 3.10+ union syntax). macOS system
Python 3.9 fails at import.

## Component ownership

| ID | Component | Owner |
|----|-----------|-------|
| C3 | Backend — Core Logic | Robin Kim |
| C4 | Backend — LLM Calls and Prompt Engineering | Alan |
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
  - `app/api/deps.py` — `get_store`, `get_llm` (provider selected by C4 config).
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

## C4 — Backend: LLM Calls and Prompt Engineering

### Done

- **Azure OpenAI-compatible adapter**
  - `app/llm/azure.py` implements the existing `LLMClient` boundary for
    `extract_candidates`, `phrase_question` and `generate_summary`.
  - Uses the OpenAI Responses API with Pydantic structured outputs. The model
    returns candidates and wording only; C3 remains responsible for accepting
    values, selecting the target slot and controlling workflow state.
  - Extraction is restricted to supplied slot IDs, declared slot types and
    exact evidence spans from the patient's message. Unknown slot IDs and
    evidence not present in the source message are discarded.
  - Explicit negative list answers such as no medications or no known allergies
    are normalised to empty lists rather than stored as list items.
  - Question generation is locked to C3's selected slot and uses neutral,
    non-diagnostic wording. Required non-list fields are not presented as
    allowing a `none` response.
  - Summary generation receives only confirmed, skipped or unknown slots.
    Candidate values are excluded. Skipped and unknown states are rendered by
    deterministic code, and suggested patient questions use confirmed facts
    only.

- **Configuration and dependency injection**
  - `Settings.llm_provider` supports `fake` (default) and `azure`.
  - `app/api/deps.py::get_llm` lazily constructs and caches the configured
    provider. Team members without credentials continue to use `FakeLLM`.
  - `.env.example` and `docs/setup.md` document provider selection without
    containing credentials.

- **Reliability and observability**
  - 30-second client timeout and at most two SDK retries.
  - Versioned prompts: `extract-v1`, `question-v1`, `summary-v1`.
  - Logs operation, model, prompt version, latency and available input/output/
    total token counts. Persistence of model-call records remains a C6 concern.
  - API failures and missing parsed output use bounded deterministic fallbacks:
    no extracted candidates, fixed question wording, or a summary built from
    validated state.

- **Testing**
  - `tests/test_azure_llm.py` uses mocked SDK responses and never accesses the
    network. It covers configuration validation, output filtering, evidence
    grounding, structured output, fallbacks, retry/timeout configuration,
    prompt-version/token/latency logging and exclusion of unconfirmed state.
  - `tests/test_llm_provider.py` covers provider selection.
  - `tests/test_sessions_api.py` explicitly overrides `get_llm` with `FakeLLM`,
    keeping API tests deterministic and free of model cost.
  - The Azure path was manually smoke-tested with synthetic data through the
    complete HTTP -> C3 -> C4 -> Azure -> C3 -> HTTP flow.

Total: 95 tests passing.

- **Consultation schema v0.3 — patient agenda slots**
  (`feat/c3-schema-v0.3-agenda-slots`)
  - `docs/workflow-catalogue.md` (committed separately, PR #16) lists
    `functional_impact`, `patient_worry`, `appointment_goal` and
    `clinician_questions` as **every-session** targets in §3.2. None of them
    existed in the schema, which meant the patient's own questions and goals —
    the proposal's stated output — were never collected. `clinician_questions`
    was the worst gap: the summary only ever carried model-generated
    suggestions.
  - `SCHEMA_VERSION` `"0.2"` → `"0.3"`; 24 → 28 slots.
    `patient_worry` / `appointment_goal` / `clinician_questions` are
    **required** (consistent with how the other every-session fields are
    treated); `functional_impact` is optional because the catalogue makes it
    conditional on a reported symptom concern.
  - `app/llm/fake.py`: `generate_summary` now returns the patient's own
    confirmed `clinician_questions` when present and only falls back to
    generated suggestions otherwise, and it distinguishes "chose not to
    answer" (skipped) from "did not know" (unknown) per catalogue §6.4.
  - Tests: `test_patient_agenda_targets_exist_and_are_required`,
    `test_summary_prefers_the_patients_own_questions`,
    `test_summary_distinguishes_skipped_from_unknown`; existing planner/API
    tests updated for the new required set and active-slot count.
  - Verified live against `uvicorn` + the C6 SQLite database: the flow now asks
    worry → goal → questions after the symptom fields, reaches
    `resolution = 1.0`, and the completed summary carries the patient's
    verbatim questions.

**Not done — needs a team decision (from the workflow catalogue):**
multi-concern namespacing (`concerns.c01.*`), workflow-level activation for
WF-01…WF-30, and nested leaf fields (`previous_consultation.exists` / `.date`
/ …). These change `SessionState.slots` and therefore C6's tables, so they are
a scope decision, not a C3-only change.

Total: 113 tests passing.

## Remaining project work

### In progress

- (nothing yet)

### Next (outside the skeleton)

- Explicit "patient approves summary" gate (with C1/C2) before `completed` feeds
  the clinician view.
- C6 database integration is implemented below; coordinate version-specific
  patient approval and source/telemetry handoffs with C1/C2/C4/C5.
- Safety patterns/wording need team + supervisor sign-off.

### Stubs / deferred

- `database_url` now configures C6 persistence; run migrations before session APIs.
- Sessions now persist in the configured database across application restarts.

## C6 — Database and data access (local feature branch)

- SQLAlchemy data models and frozen Alembic initial migration: sessions,
  transcript messages, slot state, correction history, archived candidates,
  summary versions, audit events, explicit source references, attachment
  metadata and model-call metadata.
- Request-scoped DatabaseSessionStore implements all five existing store methods.
  A request commits before its success response; summary and state writes are
  atomic. Stale writes/SQLite contention produce 409 PERSISTENCE_CONFLICT.
- Transcript/history are append-only and repeat saves do not duplicate entries.
  Candidate evidence survives C3 clearing its current candidates after confirmation.
- CLI initialization/check/seed commands, isolated temporary test databases,
  synthetic demo data and setup/DAO documentation in [database.md](database.md).
- Explicit approval storage and approved-version retrieval exist at DAO level.
  C3's approval API/UI gate remains open; `completed` never creates an approval.
- Source linking, file metadata and model-call telemetry have tested DAO methods;
  real C4/C5 producers must still be connected by their owners.
- Verification: 97 tests pass, including the original 82 and 15 persistence/API
  checks. One existing third-party Starlette/AnyIO deprecation warning remains.
  Agent verification used Python 3.12.14 with the project's installed .venv
  packages; the developer's Python launcher is 3.12.10.

## How to run

```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.db.manage init
uvicorn app.core.main:app --reload   # http://localhost:8000/api/health
pytest
```
