#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p .local
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if ! .venv/bin/python -c 'import fastapi, uvicorn, httpx, multipart, PIL, pypdf, openai' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r backend/requirements.lock.txt
fi
if [ ! -d frontend/node_modules ]; then (cd frontend && npm ci); fi
(cd frontend && npm run build)
.venv/bin/python scripts/local-server.py start
