#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/scripts/local-server.py" stop
