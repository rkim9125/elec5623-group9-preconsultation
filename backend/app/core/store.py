"""Session persistence seam.

In-memory for now. C6 replaces `InMemorySessionStore` with a DB-backed
implementation of the same interface; nothing else in C3 should need to change.
"""

from __future__ import annotations

from typing import Protocol

from app.core.errors import SessionNotFound
from app.core.models import SessionState
from app.llm.base import GeneratedSummary


class SessionStore(Protocol):
    def create(self, state: SessionState) -> None: ...
    def get(self, session_id: str) -> SessionState: ...
    def save(self, state: SessionState) -> None: ...
    def put_summary(self, session_id: str, summary: GeneratedSummary) -> None: ...
    def get_summary(self, session_id: str) -> GeneratedSummary: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._summaries: dict[str, GeneratedSummary] = {}

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
        self._summaries[session_id] = summary

    def get_summary(self, session_id: str) -> GeneratedSummary:
        try:
            return self._summaries[session_id]
        except KeyError:
            raise SessionNotFound(f"No summary for session {session_id!r}") from None

    def reset(self) -> None:
        """Test helper."""
        self._sessions.clear()
        self._summaries.clear()


_STORE = InMemorySessionStore()


def get_store() -> InMemorySessionStore:
    return _STORE
