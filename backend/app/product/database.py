"""Local SQLite persistence with WAL and optimistic intake revisions.

get_connection() is a context manager: it commits on success, rolls back on
error, and always closes its connection. Each call creates an independent
connection. Engine/provider work must run outside SQLite write transactions.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Iterator, Callable

from .config import get_settings


class ConcurrentUpdate(Exception):
    """The intake changed while a request was being processed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Create with private permissions before WAL/journal files inherit its mode.
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    os.chmod(path, 0o600)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS otp_challenges (
                id TEXT PRIMARY KEY, email TEXT NOT NULL, role TEXT NOT NULL,
                salt TEXT NOT NULL, code_hash TEXT NOT NULL,
                expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL, UNIQUE(email, role)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                role TEXT NOT NULL, expires_at REAL NOT NULL, created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
            CREATE TABLE IF NOT EXISTS rate_limits (
                bucket TEXT NOT NULL, happened_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS rate_limit_bucket ON rate_limits(bucket, happened_at);
            CREATE TABLE IF NOT EXISTS intakes (
                id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES users(id),
                revision INTEGER NOT NULL, data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS intake_owner ON intakes(patient_id);
        """)
    os.chmod(get_settings().db_path, 0o600)


def load_intake(intake_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT data FROM intakes WHERE id = ?", (intake_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def save_intake(session: dict, expected_version: int | None = None) -> None:
    """Persist a new or loaded intake. Loaded revision is a compare-and-swap token.

    Updates the supplied dictionary's revision only after a successful commit.
    Existing rows cannot be overwritten by a dictionary without a revision.
    """
    expected = expected_version if expected_version is not None else session.get("revision")
    new_revision = (expected or 0) + 1
    stored = {**session, "revision": new_revision, "updated_at": utc_now()}
    encoded = json.dumps(stored, ensure_ascii=False, allow_nan=False)
    with get_connection() as conn:
        if expected is None:
            try:
                conn.execute("INSERT INTO intakes (id, patient_id, revision, data, updated_at) VALUES (?, ?, ?, ?, ?)",
                             (stored["id"], stored["patient_id"], new_revision, encoded, stored["updated_at"]))
            except sqlite3.IntegrityError as exc:
                if conn.execute("SELECT 1 FROM intakes WHERE id = ?", (stored["id"],)).fetchone():
                    raise ConcurrentUpdate("This intake already exists.") from exc
                raise
        else:
            result = conn.execute("UPDATE intakes SET revision = ?, data = ?, updated_at = ? WHERE id = ? AND revision = ?",
                                  (new_revision, encoded, stored["updated_at"], stored["id"], expected))
            if result.rowcount != 1:
                raise ConcurrentUpdate("This intake changed. Refresh it before trying again.")
    session.update(revision=new_revision, updated_at=stored["updated_at"])


def list_intakes(patient_id: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if patient_id is None:
            rows = conn.execute("SELECT data FROM intakes ORDER BY updated_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT data FROM intakes WHERE patient_id = ? ORDER BY updated_at DESC", (patient_id,)).fetchall()
    return [json.loads(row["data"]) for row in rows]


def delete_intake(intake_id: str, patient_id: str) -> bool:
    with get_connection() as conn:
        return conn.execute("DELETE FROM intakes WHERE id = ? AND patient_id = ?", (intake_id, patient_id)).rowcount == 1


def mutate_intake(intake_id: str, callback: Callable[[dict], dict | None]) -> dict | None:
    """Serialize brief local mutations such as attachment metadata; no network IO."""
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT data, revision FROM intakes WHERE id = ?", (intake_id,)).fetchone()
        if row is None:
            return None
        session = json.loads(row["data"])
        result = callback(session)
        if result is not None:
            session = result
        session["revision"] = row["revision"] + 1
        session["updated_at"] = utc_now()
        conn.execute("UPDATE intakes SET revision = ?, data = ?, updated_at = ? WHERE id = ?",
                     (session["revision"], json.dumps(session, ensure_ascii=False, allow_nan=False), session["updated_at"], intake_id))
    return session
