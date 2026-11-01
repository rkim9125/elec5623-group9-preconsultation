"""Shared, offline-safe evaluation file helpers."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as out:
        json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")


def append_jsonl(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600), "a") as out:
        out.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        out.flush()


def read_jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def load_cases():
    return [read_json(p) for p in sorted((ROOT / "cases").glob("*.json"),
                                        key=lambda p: (p.stem.startswith("I"), p.stem))]
