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

## Working in this repo

- **Branch off `develop`, not `main`.** Name branches by component, e.g.
  `feat/c3-session-api`, `fix/c5-summary-render`.
- **Never commit `.env`.** Copy `backend/.env.example` locally and fill in your
  own keys. `.env` is git-ignored.
- **The folder layout mirrors the components** — put code where its component
  lives (see [Repository layout](#repository-layout)).
- **Open a PR into `develop`** using the
  [PR template](.github/pull_request_template.md). Tag the owners of any
  component your change touches.
- **If you change an interface, update the docs in the same PR** — primarily
  [docs/api-contract.md](docs/api-contract.md) — and tag whoever it affects.

The API contract in [docs/api-contract.md](docs/api-contract.md) is **draft
v0.1**, not final. Review the parts that touch your component and open a PR for
anything that doesn't fit.

## Docs

- [Implementation spec](docs/implementation-spec.md)
- [Implementation status](docs/implementation-status.md) — what is actually built
- [API contract](docs/api-contract.md)
- [Setup](docs/setup.md)

## Patient frontend prototype

영어·한국어 환자용 문진 데모가 `frontend/`에 구현되어 있습니다. 백엔드 없이 실행합니다.

```bash
cd frontend
npm ci
npm run dev
```

[실행 방법과 mock 범위](frontend/README.md) · [UX 설계·검증·화면 캡처](docs/patient-prototype.md)

환자 계정 데모: `http://127.0.0.1:5173/#/login`. [계정·예약·문진 경로와 체험 안내](docs/patient-account.md)를 참고하세요.

언어 전환: 최초 방문은 English이며 공통 헤더에서 korean으로 변경할 수 있습니다. [다국어 구현·검증 안내](docs/localization.md).
