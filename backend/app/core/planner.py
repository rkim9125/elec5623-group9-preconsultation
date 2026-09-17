"""Deterministic planning: coverage vs resolution, next-question selection,
stopping rules. No LLM calls.

Definitions (see the proposal's coverage/resolution distinction):
- **coverage**  - active slots that have been *addressed* (confirmed, skipped,
                  or answered "I don't know") over all active slots. "Have we
                  been through it?"
- **resolution** - active *required* slots that are *confirmed* over all active
                  required slots. "Did we actually get the answer?"
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from app.core.engine import active_slot_defs
from app.core.models import SessionState, SlotStatus
from app.core.schema import all_slot_ids

_SCHEMA_ORDER = {slot_id: i for i, slot_id in enumerate(all_slot_ids())}

_ADDRESSED = {SlotStatus.CONFIRMED, SlotStatus.SKIPPED, SlotStatus.UNKNOWN}
_PENDING = {SlotStatus.EMPTY, SlotStatus.CANDIDATE}

DEFAULT_MAX_QUESTIONS = 12


class Completeness(BaseModel):
    coverage: float
    resolution: float
    active_total: int
    addressed: int
    required_total: int
    required_confirmed: int
    unresolved_required: list[str]


class StopReason(str, Enum):
    ALL_REQUIRED_ADDRESSED = "all_required_addressed"
    QUESTION_LIMIT = "question_limit"
    SESSION_ABANDONED = "session_abandoned"


class StopDecision(BaseModel):
    stop: bool
    reason: StopReason | None = None


def compute_completeness(state: SessionState) -> Completeness:
    active = active_slot_defs(state)
    active_ids = [d.slot_id for d in active]
    addressed = [sid for sid in active_ids if state.slots[sid].status in _ADDRESSED]

    required_ids = [d.slot_id for d in active if d.required]
    required_confirmed = [
        sid for sid in required_ids if state.slots[sid].status == SlotStatus.CONFIRMED
    ]
    unresolved_required = [
        sid for sid in required_ids if state.slots[sid].status != SlotStatus.CONFIRMED
    ]

    return Completeness(
        coverage=len(addressed) / len(active_ids) if active_ids else 1.0,
        resolution=len(required_confirmed) / len(required_ids) if required_ids else 1.0,
        active_total=len(active_ids),
        addressed=len(addressed),
        required_total=len(required_ids),
        required_confirmed=len(required_confirmed),
        unresolved_required=unresolved_required,
    )


def select_next_slot(state: SessionState) -> str | None:
    """First unresolved active slot, required before optional, then schema order."""
    pending = [
        d for d in active_slot_defs(state) if state.slots[d.slot_id].status in _PENDING
    ]
    if not pending:
        return None
    pending.sort(key=lambda d: (not d.required, _SCHEMA_ORDER[d.slot_id]))
    return pending[0].slot_id


def should_stop(state: SessionState, asked_count: int = 0) -> StopDecision:
    from app.core.models import SessionStatus

    if state.status == SessionStatus.ABANDONED:
        return StopDecision(stop=True, reason=StopReason.SESSION_ABANDONED)

    required_pending = [
        d
        for d in active_slot_defs(state)
        if d.required and state.slots[d.slot_id].status in _PENDING
    ]
    if not required_pending:
        return StopDecision(stop=True, reason=StopReason.ALL_REQUIRED_ADDRESSED)

    if asked_count >= DEFAULT_MAX_QUESTIONS:
        return StopDecision(stop=True, reason=StopReason.QUESTION_LIMIT)

    return StopDecision(stop=False)
