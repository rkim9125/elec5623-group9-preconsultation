# Implementation Spec

> Draft skeleton. Fill in as the design settles.

## 1. Overview

- **Problem:**
- **Goal:**
- **Non-goals:**

## 2. Users & roles

- **Patient:**
- **Clinician:**

## 3. Core flows

1. Patient intake
2. LLM structuring / summarisation
3. Clinician review

## 4. Backend design

### Modules

- `app/api/` — HTTP routes
- `app/core/` — settings, app startup, dependencies
- `app/llm/` — LLM client, prompts, response parsing
- `app/db/` — models, session management
- `app/utils/` — shared helpers

### Data model

- SQLAlchemy models in `backend/app/db/models.py`; migrations under
  `backend/alembic/versions`. See [database.md](database.md) for table relations,
  transaction boundaries, DAO contracts, provenance and remaining integrations.

## 5. Frontend design

- `pages/patient/` — intake screens
- `pages/clinician/` — summary / review screens
- `components/shared/` — reusable UI
- `api/` — typed client for the backend

## 6. LLM usage

- **Provider / model:**
- **Prompts:**
- **Guardrails:**

## 7. Open questions

- (TBD)
