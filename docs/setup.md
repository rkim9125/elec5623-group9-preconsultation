# Development and integration setup (C7)

The backend runs with **FakeLLM, in-memory metadata and local files**. No cloud
account, database server, API key or live model call is needed. Use synthetic
data for development. This environment is for local integration, not deployment
with patient data.

## Prerequisites

- Python 3.11+ on macOS/Linux, or WSL2. The local storage adapter uses POSIX file
  operations; use Docker/WSL2 on Windows.
- Git; Node.js 20+ only if working on the separate frontend.
- Internet access for the initial dependency install. Tests and the default
  smoke test run without live external services after installation.

## Backend quick start

From the repository root:

```bash
./scripts/setup.sh
./scripts/start.sh
```

Setup creates `backend/.venv`, installs `backend/requirements.txt`, and copies
`backend/.env.example` to `backend/.env` only if no local file exists. Set
`PYTHON=/path/to/python3.11` before setup to choose an interpreter. Existing
`.env` files are preserved; compare older copies with the updated example.

The server runs at <http://127.0.0.1:8000> with **one worker**. Open
<http://127.0.0.1:8000/docs> for interactive API documentation.

```bash
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/documents/health
```

The first checks the API process. The document health check exercises local
storage readiness (or the selected cloud adapter when configured). If
`DOCUMENT_API_TOKEN` is set, document health needs the same bearer token as the
document endpoints. It is an explicit check, not an automatic cloud startup call.

Settings are read from `backend/.env` because the start script changes into
`backend/`. Relative `STORAGE_LOCAL_ROOT=.data/objects` therefore means
`backend/.data/objects`. Restart the process after changing settings. The script
intentionally fixes host/port to `127.0.0.1:8000`; `API_HOST`/`API_PORT` do not
override its CLI options.

## Tests and synthetic smoke flow

```bash
cd backend
.venv/bin/python -m pytest -q
cd ..
backend/.venv/bin/python scripts/smoke.py
```

The smoke command defaults to a new in-process API instance and temporary local
storage, regardless of cloud settings in `.env`. It creates a synthetic session,
uploads and extracts a generated DOCX, checks list/get/download, completes the
intake, tests rejection of unapproved export and stale approval, approves the
current summary, exports PDF and DOCX, then deletes the created files. Temporary
storage and in-process metadata disappear at exit. OCR remains disabled.

To test the **already running** server instead:

```bash
backend/.venv/bin/python scripts/smoke.py --base-url http://127.0.0.1:8000
```

Live smoke accepts loopback origins only. It uses that server's configured
storage and loads the integration token from the environment or `backend/.env`.
It deletes its uploaded/exported objects, but its synthetic session remains in
memory until restart. A live cloud-configured server will make cloud requests;
the default in-process command does not.

Local validation passed 225 backend tests plus the default offline smoke and
the actual running-server HTTP smoke. No GitHub Actions run is claimed.

### Enable GitHub Actions after merge

[`ci/backend.yml`](../ci/backend.yml) is a **reviewable, inactive template** for
Python 3.11/3.12 pytest and offline smoke. It installs the OCR Python extras for
controlled parser tests but requires no cloud credentials or Tesseract executable.
GitHub refused publishing an active workflow because the available credential
lacks workflow-write permission, so the template stays outside `.github/workflows`.

After this change merges, a maintainer with permission to update GitHub Actions
workflows can run the following from an up-to-date checkout:

```bash
git switch develop
git pull --ff-only
git switch -c chore/enable-backend-ci
mkdir -p .github/workflows
cp ci/backend.yml .github/workflows/backend.yml
git add .github/workflows/backend.yml
git commit -m "ci: enable backend tests and synthetic smoke"
git push -u origin chore/enable-backend-ci
```

Open a pull request into `develop` and merge the activation change. The workflow
will then run on matching pushes/pull requests and can be started from Actions
with `workflow_dispatch`. Review the actual run before claiming CI passed. For a
classic personal access token, GitHub requires the `workflow` scope to publish
workflow-file changes; use an appropriately authorized maintainer credential.

## State lifetime and safe reset

Sessions, summaries, approval records and document metadata currently live in
memory. **Restarting, hot reload, or using multiple workers loses or separates
that state.** Local and cloud object bytes can outlive the metadata, so persisted
files alone do not make sessions recoverable. C6 must implement durable DAO
storage before multi-worker or persistent use. `DATABASE_URL` is a placeholder;
there is currently no migration or database initialisation command to run.

Prefer deleting documents through the API while the owning session still exists.
For a complete reset of the default local development environment:

1. Stop the backend with Ctrl+C.
2. Run `backend/.venv/bin/python scripts/reset_dev_data.py --yes`.
3. Restart with `./scripts/start.sh` and rerun smoke if desired.

The reset utility removes only this checkout's `backend/.data/objects`, refuses
symlinked data paths, and requires `--yes`. It never reads a configurable deletion
target or contacts cloud storage. Custom local directories and cloud objects
need separate, explicit owner-managed cleanup. A cloud test bucket should have
a deliberate lifecycle policy for abandoned synthetic objects.

## Optional Docker environment

```bash
docker compose up --build
```

Compose runs only the backend, bound to host loopback, with local object storage
in a named volume. It does not load host `.env` credentials, a live model or a
database. Container state is in memory; object files persist in `local-objects`.
Stop with `docker compose down`; **`docker compose down --volumes` also deletes
this Compose project's local object volume** when you deliberately want a reset.

For OCR in the container:

```bash
INSTALL_OCR=true DOCUMENT_OCR_ENABLED=true DOCUMENT_OCR_LANGUAGE=eng+chi_sim docker compose up --build
```

The optional build installs Tesseract plus English and simplified Chinese language
data. The default image omits the OCR executable. Docker is an alternative local
runtime, not a claim of production readiness.

## Optional local OCR and cloud storage

For OCR, install the Tesseract executable and required language data on your OS,
then set `DOCUMENT_OCR_ENABLED=true` and `DOCUMENT_OCR_LANGUAGE=eng` (or
`eng+chi_sim` when both language packs are installed). Install Python OCR extras:
`backend/.venv/bin/python -m pip install -r backend/requirements-ocr.txt`.
Check available languages with `tesseract --list-langs`.
OCR may misread source content; consumers must display its warnings and retain
human review. Scanned documents return `ocr_required` when OCR cannot produce
text; mixed PDFs may return `partial`.

Cloud setup is optional: run `./scripts/setup.sh --cloud` and follow
[storage configuration](storage-configuration.md). AWS names its service **S3**;
Alibaba Cloud names its service **OSS**. Use only one selected storage backend
per process. Changing providers does not migrate existing metadata or files.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

The existing frontend is a scaffold; this C5/C7 change supplies backend tools and
contracts, not completed C1/C2 upload or summary pages. Configure API calls against
`http://127.0.0.1:8000`; `FRONTEND_ORIGIN` controls FastAPI CORS and defaults to
`http://localhost:5173`. Frontend integration starts with [C5 tool usage](c5-tools.md).

## Troubleshooting

| Symptom | Check |
|---|---|
| Import/module not found | Run setup and use `backend/.venv/bin/python`; start from the root with the script. |
| Port 8000 already in use | Stop the existing local server or container before starting another. |
| A document/session is missing after restart | Metadata is in memory; create a fresh session and upload again. |
| HTTP 401 on a document action | Supply `Authorization: Bearer <DOCUMENT_API_TOKEN>` when configured. |
| Export returns HTTP 409 | Complete intake, display the summary, and approve its current `content_sha256`. |
| Cloud startup configuration error | Install optional SDKs and provide the bucket/token/provider-specific fields. |
| `STORAGE_UNAVAILABLE` | Check credentials, region/endpoint, IAM/RAM permissions and network; avoid exposing provider error details to users. |
| `ocr_required` / `partial` | Inspect warnings, installed OCR languages and limits; provide an unscanned source or enable OCR. |
