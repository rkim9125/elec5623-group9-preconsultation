#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p .local
if [ -x .venv/bin/python ]; then
  APP_PYTHON=.venv/bin/python
elif [ -x backend/.venv/bin/python ]; then
  APP_PYTHON=backend/.venv/bin/python
else
  python3 -m venv .venv
  APP_PYTHON=.venv/bin/python
fi
if ! "$APP_PYTHON" -c 'import fastapi, uvicorn, httpx, multipart, PIL, pypdf, reportlab, openai' >/dev/null 2>&1; then
  "$APP_PYTHON" -m pip install -r backend/requirements.lock.txt
fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm ci); fi
(cd frontend && npm run build)
"$APP_PYTHON" scripts/local-server.py start
