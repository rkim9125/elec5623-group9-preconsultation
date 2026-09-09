# ELEC5623 Group 9 — Pre-Consultation

Pre-consultation tool: patients complete a guided intake before their appointment,
and clinicians receive a structured summary.

## Stack

- **Backend:** Python + FastAPI
- **Frontend:** React + Vite
- **LLM:** used to structure/summarise patient intake

## Repository layout

```
backend/
  app/
    api/     # route handlers
    core/    # config, settings, app wiring
    llm/     # LLM client + prompt logic
    db/      # models, session, migrations
    utils/   # shared helpers
  tests/
  requirements.txt
  .env.example
frontend/
  src/
    pages/
      patient/     # patient-facing screens
      clinician/   # clinician-facing screens
    components/
      shared/      # reusable UI
    api/           # backend API client
  package.json
docs/
  implementation-spec.md
  api-contract.md
  setup.md
.github/
  pull_request_template.md
```

## Getting started

See [docs/setup.md](docs/setup.md).

## Docs

- [Implementation spec](docs/implementation-spec.md)
- [API contract](docs/api-contract.md)
- [Setup](docs/setup.md)
