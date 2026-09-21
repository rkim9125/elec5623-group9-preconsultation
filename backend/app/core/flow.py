"""Turn orchestration: glue between transcript, safety, the LLM and the engine.

Still deterministic control flow — the LLM is called only for extraction and
wording, and every value goes through the engine's validation.
"""

from __future__ import annotations

from uuid import uuid4

from pydantic import BaseModel

from app.core.engine import ApplyOutcome, ApplyResult, apply_extraction
from app.core.models import (
    Prompt,
    SessionState,
    SessionStatus,
    TranscriptEntry,
    TranscriptRole,
)
from app.core.planner import (
    Completeness,
    StopDecision,
    compute_completeness,
    select_next_slot,
    should_stop,
)
from app.core.safety import SafetyResult, check_safety
from app.core.schema import SCHEMA_VERSION, build_initial_slots, get_slot_def
from app.llm.base import LLMClient

_ADVANCING = {ApplyOutcome.ACCEPTED, ApplyOutcome.CONTRADICTION}


class TurnResult(BaseModel):
    next_prompt: Prompt | None
    updated_slots: list[str]
    applied: list[ApplyResult]
    stop: StopDecision
    safety: SafetyResult
    completeness: Completeness


def start_session(patient_ref: str | None = None, locale: str = "en-AU") -> SessionState:
    return SessionState(
        session_id=f"sess_{uuid4().hex[:10]}",
        patient_ref=patient_ref,
        locale=locale,
        schema_version=SCHEMA_VERSION,
        slots=build_initial_slots(),
    )


def _asked_count(state: SessionState) -> int:
    return sum(1 for t in state.transcript if t.role == TranscriptRole.ASSISTANT)


def _phrase(llm: LLMClient, state: SessionState, slot_id: str) -> str:
    slot = state.slots[slot_id]
    try:
        text = llm.phrase_question(slot, state)
        if text and text.strip():
            return text.strip()
    except Exception:
        pass
    return get_slot_def(slot_id).prompt_hint or f"Please tell me about {slot.label.lower()}."


def _advance(state: SessionState, llm: LLMClient) -> tuple[Prompt | None, StopDecision]:
    stop = should_stop(state, _asked_count(state))
    if stop.stop:
        state.current_prompt = None
        return None, stop
    slot_id = select_next_slot(state)
    if slot_id is None:
        state.current_prompt = None
        return None, stop
    prompt = Prompt(slot_id=slot_id, text=_phrase(llm, state, slot_id))
    state.current_prompt = prompt
    state.transcript.append(TranscriptEntry(role=TranscriptRole.ASSISTANT, text=prompt.text))
    return prompt, stop


def ingest_message(state: SessionState, text: str, llm: LLMClient) -> TurnResult:
    state.transcript.append(TranscriptEntry(role=TranscriptRole.PATIENT, text=text))

    safety = check_safety(text)
    if safety.triggered:
        state.transcript.append(
            TranscriptEntry(role=TranscriptRole.ASSISTANT, text=safety.message or "")
        )
        state.current_prompt = None
        return TurnResult(
            next_prompt=None,
            updated_slots=[],
            applied=[],
            stop=StopDecision(stop=True),
            safety=safety,
            completeness=compute_completeness(state),
        )

    applied = apply_extraction(state, llm.extract_candidates(text, state.slots, state.schema_version))
    updated = [r.slot_id for r in applied if r.outcome in _ADVANCING]

    next_prompt, stop = _advance(state, llm)
    return TurnResult(
        next_prompt=next_prompt,
        updated_slots=updated,
        applied=applied,
        stop=stop,
        safety=safety,
        completeness=compute_completeness(state),
    )


def advance_after_action(state: SessionState, llm: LLMClient) -> Prompt | None:
    """Recompute the next question after a manual slot confirm/edit/skip."""
    prompt, _ = _advance(state, llm)
    return prompt


def finalise(state: SessionState, llm: LLMClient):
    """Generate the summary from confirmed state and mark the session completed.

    'completed' means intake is finished, not that the summary is approved.
    The separate summary/approve route binds approval to this stored content;
    C5 exports and the C2 final view require that approval.
    """
    summary = llm.generate_summary(state)
    state.summary_ref = f"sum_{state.session_id}"
    state.summary_approved_sha256 = None
    state.summary_approved_at = None
    state.status = SessionStatus.COMPLETED
    state.current_prompt = None
    return summary
