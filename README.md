# ELEC5623 Group 9 — Pre-Consultation

A preparation tool for guided patient intake and a structured, patient-reviewed
summary. The repository currently provides the C3 intake engine, a deterministic
FakeLLM adapter, C5 document/storage/export utilities, and C7 integration setup.
The React frontend and durable C6 persistence remain separate integration work.

## Run locally

Python 3.11+ on macOS/Linux/WSL2 is required. No cloud account or API key is needed.

```bash
./scripts/setup.sh
./scripts/start.sh
```

Open <http://127.0.0.1:8000/docs>. In another terminal:

```bash
backend/.venv/bin/python scripts/smoke.py
```

For dependencies, tests, Docker, OCR and reset instructions, see
[setup](docs/setup.md). Sessions and document metadata are in memory; run one
worker and expect a restart to lose that state even though stored files persist.
Use synthetic data in this local development environment.

Local validation passed 225 backend tests plus offline and running-server HTTP
smoke checks. The [GitHub Actions template](ci/backend.yml) is ready for review
but **not active**: the publishing credential cannot modify workflow files.
A maintainer can enable it after merge using the [activation steps](docs/setup.md#enable-github-actions-after-merge).

## Documents and storage

C5 supports TXT, PDF, DOCX, PNG and JPEG uploads, literal extraction with source
locations, optional OCR, PDF/DOCX exports of an explicitly approved summary, and
private local/AWS S3/Alibaba Cloud OSS storage. Cloud storage is optional. Export
and document access use the backend API; storage credentials stay on the server.

- [How other components call C5 tools](docs/c5-tools.md)
- [Storage variables, AWS S3 and Alibaba Cloud OSS setup](docs/storage-configuration.md)
- [中文交接与配置清单](docs/c5-c7-handoff.zh-CN.md)

## Repository layout

```text
backend/app/api/      HTTP routes and request/response models
backend/app/core/     state engine, workflow, settings and session-store seam
backend/app/llm/      model protocol and FakeLLM
backend/app/utils/    document processing, rendering, storage and metadata seam
backend/app/db/       reserved for C6 persistence
backend/tests/        backend unit and API tests
frontend/            React + Vite scaffold
scripts/             setup, start, safe local reset and synthetic smoke
ci/backend.yml       inactive GitHub Actions template; maintainer activation needed
docs/                component plan, implementation and integration contracts
compose.yaml         local backend container
```

## Working in this repository

- Branch off `develop`, for example `feat/c5-documents` or `feat/c7-environment`.
- Never commit `.env`, credentials, patient files or generated local data.
- Open a pull request into `develop` using the PR template; tag affected component
  owners. C5 support does not alter the team allocation recorded in the plan.
- Update the API contract and integration docs whenever an interface changes.

## Team documentation

- [Component breakdown and collaboration](docs/component-breakdown.md)
- [Implementation specification](docs/implementation-spec.md)
- [Implementation status](docs/implementation-status.md)
- [API contract](docs/api-contract.md)
- [Development setup and smoke checks](docs/setup.md)
