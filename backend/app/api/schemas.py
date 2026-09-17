"""HTTP request/response bodies. Kept separate from app.core.models (the domain
state) so the wire format can evolve independently."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.models import SessionStatus


class CreateSessionRequest(BaseModel):
    patient_ref: str | None = None
    locale: str = "en-AU"


class MessageRequest(BaseModel):
    text: str = Field(min_length=1)


class SlotActionRequest(BaseModel):
    action: Literal["confirm", "edit", "skip", "unknown"]
    value: Any = None


class PromptOut(BaseModel):
    slot_id: str
    text: str


class SafetyOut(BaseModel):
    triggered: bool
    category: str | None = None
    message: str | None = None


class CompletenessOut(BaseModel):
    coverage: float
    resolution: float
    unresolved_required: list[str]


class MessageResponse(BaseModel):
    session_id: str
    status: SessionStatus
    next_prompt: PromptOut | None
    updated_slots: list[str]
    stopped: bool
    stop_reason: str | None
    safety: SafetyOut
    completeness: CompletenessOut


class SlotActionResponse(BaseModel):
    session_id: str
    status: SessionStatus
    slot_id: str
    outcome: str
    detail: str | None
    next_prompt: PromptOut | None
    completeness: CompletenessOut


class CompleteResponse(BaseModel):
    session_id: str
    status: SessionStatus
    summary_ref: str | None


class SummaryResponse(BaseModel):
    session_id: str
    summary_ref: str | None
    sections: dict[str, str]
    patient_questions: list[str]
    model: str
