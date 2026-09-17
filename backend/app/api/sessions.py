"""Session endpoints. See docs/api-contract.md sections 1-4.

Routes are thin: they validate the request, call app/core/flow.py or the engine,
persist through the store, and shape the response. All rules live in core.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_llm, get_store
from app.api.schemas import (
    CompletenessOut,
    CompleteResponse,
    CreateSessionRequest,
    MessageRequest,
    MessageResponse,
    PromptOut,
    SafetyOut,
    SlotActionRequest,
    SlotActionResponse,
    SummaryResponse,
)
from app.core import flow
from app.core.engine import (
    ApplyOutcome,
    SlotNotFound as EngineSlotNotFound,
    confirm_slot,
    edit_slot,
    mark_unknown,
    skip_slot,
)
from app.core.errors import (
    SessionAlreadyCompleted,
    SlotNotFound,
    SlotValidationFailed,
    SummaryNotReady,
)
from app.core.models import SessionState, SessionStatus
from app.core.planner import Completeness, compute_completeness

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _completeness_out(c: Completeness) -> CompletenessOut:
    return CompletenessOut(
        coverage=round(c.coverage, 3),
        resolution=round(c.resolution, 3),
        unresolved_required=c.unresolved_required,
    )


def _prompt_out(prompt) -> PromptOut | None:
    return PromptOut(slot_id=prompt.slot_id, text=prompt.text) if prompt else None


@router.post("", status_code=201, response_model=SessionState)
def create_session(body: CreateSessionRequest, store=Depends(get_store)) -> SessionState:
    state = flow.start_session(patient_ref=body.patient_ref, locale=body.locale)
    store.create(state)
    return state


@router.get("/{session_id}", response_model=SessionState)
def get_session(session_id: str, store=Depends(get_store)) -> SessionState:
    return store.get(session_id)


@router.post("/{session_id}/messages", response_model=MessageResponse)
def post_message(
    session_id: str,
    body: MessageRequest,
    store=Depends(get_store),
    llm=Depends(get_llm),
) -> MessageResponse:
    state = store.get(session_id)
    if state.status == SessionStatus.COMPLETED:
        raise SessionAlreadyCompleted(f"Session {session_id!r} is already completed")

    turn = flow.ingest_message(state, body.text, llm)
    store.save(state)

    return MessageResponse(
        session_id=state.session_id,
        status=state.status,
        next_prompt=_prompt_out(turn.next_prompt),
        updated_slots=turn.updated_slots,
        stopped=turn.stop.stop,
        stop_reason=turn.stop.reason.value if turn.stop.reason else None,
        safety=SafetyOut(
            triggered=turn.safety.triggered,
            category=turn.safety.category,
            message=turn.safety.message,
        ),
        completeness=_completeness_out(turn.completeness),
    )


@router.post("/{session_id}/slots/{slot_id}", response_model=SlotActionResponse)
def slot_action(
    session_id: str,
    slot_id: str,
    body: SlotActionRequest,
    store=Depends(get_store),
    llm=Depends(get_llm),
) -> SlotActionResponse:
    state = store.get(session_id)
    if state.status == SessionStatus.COMPLETED:
        raise SessionAlreadyCompleted(f"Session {session_id!r} is already completed")

    try:
        if body.action == "confirm":
            result = confirm_slot(state, slot_id, value=body.value)
        elif body.action == "edit":
            if body.value is None:
                raise SlotValidationFailed("'edit' requires a value")
            result = edit_slot(state, slot_id, body.value)
        elif body.action == "unknown":
            result = mark_unknown(state, slot_id)
        else:  # skip
            result = skip_slot(state, slot_id)
    except EngineSlotNotFound:
        raise SlotNotFound(f"No slot {slot_id!r} in this consultation") from None

    if result.outcome == ApplyOutcome.REJECTED:
        raise SlotValidationFailed(result.detail or "slot value rejected")

    next_prompt = flow.advance_after_action(state, llm)
    store.save(state)

    return SlotActionResponse(
        session_id=state.session_id,
        status=state.status,
        slot_id=slot_id,
        outcome=result.outcome.value,
        detail=result.detail,
        next_prompt=_prompt_out(next_prompt),
        completeness=_completeness_out(compute_completeness(state)),
    )


@router.post("/{session_id}/complete", response_model=CompleteResponse)
def complete_session(
    session_id: str,
    store=Depends(get_store),
    llm=Depends(get_llm),
) -> CompleteResponse:
    state = store.get(session_id)
    if state.status == SessionStatus.COMPLETED:
        raise SessionAlreadyCompleted(f"Session {session_id!r} is already completed")

    summary = flow.finalise(state, llm)
    store.put_summary(session_id, summary)
    store.save(state)
    return CompleteResponse(
        session_id=state.session_id,
        status=state.status,
        summary_ref=state.summary_ref,
    )


@router.get("/{session_id}/summary", response_model=SummaryResponse)
def get_summary(session_id: str, store=Depends(get_store)) -> SummaryResponse:
    state = store.get(session_id)
    if state.status != SessionStatus.COMPLETED:
        raise SummaryNotReady(f"Session {session_id!r} is not completed yet")

    summary = store.get_summary(session_id)
    return SummaryResponse(
        session_id=session_id,
        summary_ref=state.summary_ref,
        sections=summary.sections,
        patient_questions=summary.patient_questions,
        model=summary.model,
    )
