"""Runtime domain models for a pre-consultation session.

These mirror docs/api-contract.md sections 2, 3 and 5. They describe the *state*
of a session; the deterministic rules that change that state live in
app/core/engine.py (added in feat/c3-state-engine).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SlotType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    DATE = "date"
    LIST = "list"


class SlotStatus(str, Enum):
    EMPTY = "empty"
    CANDIDATE = "candidate"  # LLM-proposed, not yet confirmed
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"  # patient declined to answer
    UNKNOWN = "unknown"  # patient answered "I don't know" — distinct from skip


class SlotSource(str, Enum):
    PATIENT = "patient"  # typed directly
    LLM = "llm"  # extracted
    CLINICIAN = "clinician"  # overridden


class SessionStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TranscriptRole(str, Enum):
    PATIENT = "patient"
    ASSISTANT = "assistant"


class Candidate(BaseModel):
    """One LLM-extracted value for a slot. Never written straight to Slot.value.

    Lands in Slot.candidates[] until confirmed by the patient or clinician.
    """

    value: Any = None
    confidence: float = 0.0
    evidence_span: str | None = None
    rationale: str | None = None
    model: str = "unknown"
    extracted_at: datetime = Field(default_factory=_now)


class Slot(BaseModel):
    """One structured field the intake flow tries to fill."""

    slot_id: str
    label: str
    type: SlotType
    required: bool = False
    options: list[str] | None = None  # present only when type == ENUM
    value: Any = None
    status: SlotStatus = SlotStatus.EMPTY
    source: SlotSource | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=_now)


class TranscriptEntry(BaseModel):
    role: TranscriptRole
    text: str
    at: datetime = Field(default_factory=_now)


class Prompt(BaseModel):
    """The slot the intake flow is currently asking about."""

    slot_id: str
    text: str


class SessionState(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.IN_PROGRESS
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    patient_ref: str | None = None
    locale: str = "en-AU"
    schema_version: str
    current_prompt: Prompt | None = None
    slots: dict[str, Slot] = Field(default_factory=dict)
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    summary_ref: str | None = None
