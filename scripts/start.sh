#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -ne 0 ]]; then
  echo "Usage: scripts/start.sh" >&2
  exit 2
fi
if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  echo "Run scripts/setup.sh first." >&2
  exit 1
fi
cd "$ROOT/backend"
# One worker is required while session/document metadata remain in memory.
exec .venv/bin/python -m uvicorn app.core.main:app --host 127.0.0.1 --port 8000 --workers 1
