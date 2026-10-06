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


class SummaryApprovalRequest(BaseModel):
    # The version the patient actually reviewed. Approving a stale version is
    # a conflict, not a silent no-op.
    version: int = Field(ge=1)
    approved_by: str = Field(min_length=1)


class SummaryItemOut(BaseModel):
    """One summary line, addressable by slot rather than by its display label."""

    slot_id: str
    label: str
    status: str
    text: str


class SummaryResponse(BaseModel):
    session_id: str
    summary_ref: str | None
    version: int
    approved: bool
    approved_at: str | None
    # `items` is the one to build UI against: ordered, keyed by slot_id, and it
    # carries the slot status so "skipped" and "don't know" stay distinguishable
    # without parsing prose. `sections` is the original label-keyed shape, kept
    # so existing consumers don't break — but a label is display text, so it is
    # the wrong thing to look a field up by.
    items: list[SummaryItemOut]
    sections: dict[str, str]
    patient_questions: list[str]
    model: str
