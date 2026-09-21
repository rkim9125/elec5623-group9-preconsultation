#!/usr/bin/env bash
# Run from any directory. Use PYTHON=/path/to/python to choose an interpreter.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_CLOUD=false
case "${1:-}" in
  "") ;;
  --cloud) WITH_CLOUD=true ;;
  *) echo "Usage: scripts/setup.sh [--cloud]" >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
  echo "Usage: scripts/setup.sh [--cloud]" >&2
  exit 2
fi

if [[ -z "${PYTHON:-}" ]]; then
  for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
      PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "${PYTHON:-}" ]] || ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
  echo "Python 3.11+ is required. Set PYTHON to its executable path." >&2
  exit 1
fi

"$PYTHON" -m venv "$ROOT/backend/.venv"
"$ROOT/backend/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements.txt"
if [[ "$WITH_CLOUD" == true ]]; then
  "$ROOT/backend/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements-storage.txt"
fi
if [[ ! -e "$ROOT/backend/.env" ]]; then
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
fi
echo "Backend ready. Start with scripts/start.sh; verify with backend/.venv/bin/python scripts/smoke.py."
