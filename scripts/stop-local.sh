#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
  APP_PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [ -x "$PROJECT_DIR/backend/.venv/bin/python" ]; then
  APP_PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
else
  APP_PYTHON=python3
fi
"$APP_PYTHON" "$PROJECT_DIR/scripts/local-server.py" stop
