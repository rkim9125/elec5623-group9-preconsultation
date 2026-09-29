"""Session persistence seam.

The database implementation is request-scoped. InMemorySessionStore remains
available for isolated unit tests and mocks.
"""

from __future__ import annotations

from typing import Protocol

from datetime import datetime, timezone

from app.core.errors import (
    PersistenceConflict,
    SessionNotFound,
    SummaryNotReady,
)
from app.core.models import SessionState
from app.llm.base import GeneratedSummary


class SessionStore(Protocol):
    def create(self, state: SessionState) -> None: ...
    def get(self, session_id: str) -> SessionState: ...
    def save(self, state: SessionState) -> None: ...
    def put_summary(self, session_id: str, summary: GeneratedSummary) -> None: ...
    def get_summary(self, session_id: str) -> GeneratedSummary: ...
    def list_summary_versions(self, session_id: str) -> list[dict]: ...
    def record_summary_approval(
        self, session_id: str, version: int, approved_by: str
    ) -> None: ...
    def get_approved_summary(self, session_id: str) -> dict: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._summaries: dict[str, list[dict]] = {}

    def create(self, state: SessionState) -> None:
        self._sessions[state.session_id] = state

    def get(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFound(f"No session {session_id!r}") from None

    def save(self, state: SessionState) -> None:
        # State is mutated in place; kept explicit for the DB-backed swap.
        self._sessions[state.session_id] = state

    def put_summary(self, session_id: str, summary: GeneratedSummary) -> None:
        versions = self._summaries.setdefault(session_id, [])
        versions.append(
            {
                "version": len(versions) + 1,
                "summary": summary,
                "approved_at": None,
                "approved_by": None,
            }
        )

    def _versions(self, session_id: str) -> list[dict]:
        versions = self._summaries.get(session_id)
        if not versions:
            raise SessionNotFound(f"No summary for session {session_id!r}")
        return versions

    def get_summary(self, session_id: str) -> GeneratedSummary:
        return self._versions(session_id)[-1]["summary"]

    def list_summary_versions(self, session_id: str) -> list[dict]:
        return [dict(v) for v in self._versions(session_id)]

    def record_summary_approval(
        self, session_id: str, version: int, approved_by: str
    ) -> None:
        if not approved_by or not approved_by.strip():
            raise ValueError("Approval requires an actor reference.")
        for row in self._versions(session_id):
            if row["version"] == version:
                if row["approved_at"] is not None:
                    if row["approved_by"] != approved_by:
                        raise PersistenceConflict(
                            "Approval is already recorded for another actor."
                        )
                    return
                row["approved_at"] = datetime.now(timezone.utc).isoformat()
                row["approved_by"] = approved_by
                return
        raise SummaryNotReady("Summary version does not exist.")

    def get_approved_summary(self, session_id: str) -> dict:
        for row in reversed(self._versions(session_id)):
            if row["approved_at"] is not None:
                return {"version": row["version"], "summary": row["summary"]}
        raise SummaryNotReady("No explicitly approved summary exists.")

    def reset(self) -> None:
        """Test helper."""
        self._sessions.clear()
        self._summaries.clear()


def get_store():
    """FastAPI dependency: commit all writes together before returning success."""
    from app.db.session import store_transaction

    with store_transaction() as store:
        yield store
