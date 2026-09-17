"""Deterministic state engine for a pre-consultation session.

This module owns *what enters session state*. LLM output is only ever a
candidate; nothing here calls a model. Every value is validated against the
consultation schema before it can touch a slot.

Pure-ish: functions mutate the passed `SessionState` in place and return a
result describing what happened. Planning (next question, stopping,
completeness) lives in app/core/planner.py; safety rules in app/core/safety.py.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.core.models import (
    Candidate,
    SessionState,
    Slot,
    SlotSource,
    SlotStatus,
    SlotType,
)
from app.core.schema import SlotDef, all_slot_ids, get_slot_def
from app.llm.base import ExtractedCandidate


class SlotNotFound(KeyError):
    """Raised when a slot_id is not part of the consultation schema."""


class ApplyOutcome(str, Enum):
    ACCEPTED = "accepted"  # candidate recorded (or agrees with a confirmed value)
    REJECTED = "rejected"  # failed schema validation
    CONTRADICTION = "contradiction"  # conflicts with an already-confirmed value
    INACTIVE = "inactive"  # slot's activation condition is not met yet
    UNKNOWN_SLOT = "unknown_slot"


class ApplyResult(BaseModel):
    slot_id: str
    outcome: ApplyOutcome
    detail: str | None = None


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"false", "no", "n", "0"}


def validate_value(slot_def: SlotDef, raw: Any) -> tuple[bool, Any, str | None]:
    """Return (ok, coerced_value, error). Never raises for bad input."""
    t = slot_def.type

    if t == SlotType.STRING:
        if not isinstance(raw, str) or not raw.strip():
            return False, None, "expected non-empty text"
        return True, raw.strip(), None

    if t == SlotType.NUMBER:
        if isinstance(raw, bool):
            return False, None, "expected a number, got a boolean"
        try:
            num = float(raw)
        except (TypeError, ValueError):
            return False, None, f"expected a number, got {raw!r}"
        if num < 0:
            return False, None, "expected a non-negative number"
        return True, int(num) if num.is_integer() else num, None

    if t == SlotType.BOOLEAN:
        if isinstance(raw, bool):
            return True, raw, None
        if isinstance(raw, str):
            low = raw.strip().lower()
            if low in _TRUE:
                return True, True, None
            if low in _FALSE:
                return True, False, None
        return False, None, f"expected yes/no, got {raw!r}"

    if t == SlotType.ENUM:
        options = slot_def.options or []
        if isinstance(raw, str):
            match = next((o for o in options if o.lower() == raw.strip().lower()), None)
            if match is not None:
                return True, match, None
        return False, None, f"expected one of {options}, got {raw!r}"

    if t == SlotType.LIST:
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, (list, tuple)):
            return False, None, f"expected a list, got {raw!r}"
        items = [str(x).strip() for x in raw if str(x).strip()]
        return True, items, None  # [] is valid: means "none"

    if t == SlotType.DATE:
        if isinstance(raw, date):
            return True, raw.isoformat(), None
        if isinstance(raw, str):
            try:
                return True, date.fromisoformat(raw.strip()).isoformat(), None
            except ValueError:
                return False, None, f"expected an ISO date (YYYY-MM-DD), got {raw!r}"
        return False, None, f"expected a date, got {raw!r}"

    return False, None, f"unhandled slot type {t}"


# --------------------------------------------------------------------------- #
# Conditional-slot activation
# --------------------------------------------------------------------------- #


def is_slot_active(state: SessionState, slot_def: SlotDef) -> bool:
    """A slot with no activation is always active; a conditional slot is active
    only once its dependency is confirmed and matches."""
    act = slot_def.activation
    if act is None:
        return True
    dep = state.slots.get(act.when_slot)
    if dep is None or dep.status != SlotStatus.CONFIRMED:
        return False
    if act.contains is not None:
        return isinstance(dep.value, list) and act.contains in dep.value
    if act.equals is not None:
        return dep.value == act.equals
    return True


def active_slot_defs(state: SessionState) -> list[SlotDef]:
    defs = (get_slot_def(sid) for sid in all_slot_ids())
    return [d for d in defs if is_slot_active(state, d)]


# --------------------------------------------------------------------------- #
# Applying candidates and patient actions
# --------------------------------------------------------------------------- #


def _touch(state: SessionState, slot: Slot) -> None:
    from app.core.models import _now

    slot.updated_at = _now()
    state.updated_at = _now()


def detect_contradiction(slot: Slot, coerced_value: Any) -> bool:
    return slot.status == SlotStatus.CONFIRMED and slot.value != coerced_value


def apply_candidate(state: SessionState, cand: ExtractedCandidate) -> ApplyResult:
    """Validate one LLM candidate and record it. Does not confirm anything."""
    slot = state.slots.get(cand.slot_id)
    if slot is None:
        return ApplyResult(slot_id=cand.slot_id, outcome=ApplyOutcome.UNKNOWN_SLOT)

    slot_def = get_slot_def(cand.slot_id)
    if not is_slot_active(state, slot_def):
        return ApplyResult(
            slot_id=cand.slot_id,
            outcome=ApplyOutcome.INACTIVE,
            detail=f"activation condition on {slot_def.activation.when_slot} not met",
        )

    ok, value, error = validate_value(slot_def, cand.value)
    if not ok:
        return ApplyResult(slot_id=cand.slot_id, outcome=ApplyOutcome.REJECTED, detail=error)

    if slot.status == SlotStatus.CONFIRMED:
        if slot.value == value:
            return ApplyResult(
                slot_id=cand.slot_id,
                outcome=ApplyOutcome.ACCEPTED,
                detail="matches confirmed value",
            )
        slot.candidates.append(_as_candidate(cand, value))
        _touch(state, slot)
        return ApplyResult(
            slot_id=cand.slot_id,
            outcome=ApplyOutcome.CONTRADICTION,
            detail=f"confirmed value {slot.value!r} vs proposed {value!r}",
        )

    slot.candidates.append(_as_candidate(cand, value))
    slot.candidates.sort(key=lambda c: c.confidence, reverse=True)
    if slot.status in (SlotStatus.EMPTY, SlotStatus.SKIPPED, SlotStatus.UNKNOWN):
        # A previously skipped/unknown slot gets reopened for confirmation if
        # new information about it shows up later in the conversation.
        slot.status = SlotStatus.CANDIDATE
    _touch(state, slot)
    return ApplyResult(slot_id=cand.slot_id, outcome=ApplyOutcome.ACCEPTED)


def apply_extraction(
    state: SessionState, candidates: list[ExtractedCandidate]
) -> list[ApplyResult]:
    return [apply_candidate(state, c) for c in candidates]


def _as_candidate(cand: ExtractedCandidate, coerced_value: Any) -> Candidate:
    return Candidate(
        value=coerced_value,
        confidence=cand.confidence,
        evidence_span=cand.evidence_span,
        rationale=cand.rationale,
        model=cand.model,
        extracted_at=cand.extracted_at,
    )


def _require_slot(state: SessionState, slot_id: str) -> Slot:
    slot = state.slots.get(slot_id)
    if slot is None:
        raise SlotNotFound(slot_id)
    return slot


def confirm_slot(
    state: SessionState,
    slot_id: str,
    value: Any = None,
    source: SlotSource = SlotSource.PATIENT,
) -> ApplyResult:
    """Confirm a slot. With `value`, that value is used; otherwise the
    highest-confidence candidate is promoted."""
    slot = _require_slot(state, slot_id)
    slot_def = get_slot_def(slot_id)

    if value is None:
        if not slot.candidates:
            return ApplyResult(
                slot_id=slot_id, outcome=ApplyOutcome.REJECTED, detail="no candidate to confirm"
            )
        value = slot.candidates[0].value

    ok, coerced, error = validate_value(slot_def, value)
    if not ok:
        return ApplyResult(slot_id=slot_id, outcome=ApplyOutcome.REJECTED, detail=error)

    slot.value = coerced
    slot.status = SlotStatus.CONFIRMED
    slot.source = source
    slot.candidates = []
    _touch(state, slot)
    return ApplyResult(slot_id=slot_id, outcome=ApplyOutcome.ACCEPTED)


def edit_slot(
    state: SessionState,
    slot_id: str,
    value: Any,
    source: SlotSource = SlotSource.PATIENT,
) -> ApplyResult:
    """Patient/clinician correction. Resolves a contradiction by overwriting."""
    return confirm_slot(state, slot_id, value=value, source=source)


def skip_slot(state: SessionState, slot_id: str) -> ApplyResult:
    """Patient declined to answer. Distinct from `mark_unknown`: this means
    'I'd rather not say', not 'I don't know'. Slot is addressed but unresolved."""
    slot = _require_slot(state, slot_id)
    slot.status = SlotStatus.SKIPPED
    slot.value = None
    slot.source = SlotSource.PATIENT
    slot.candidates = []
    _touch(state, slot)
    return ApplyResult(slot_id=slot_id, outcome=ApplyOutcome.ACCEPTED)


def mark_unknown(state: SessionState, slot_id: str) -> ApplyResult:
    """Patient answered 'I don't know'. Distinct from `skip_slot`: this is an
    affirmative answer (they tried and don't have the information), which the
    clinician summary should present differently from a declined answer.
    Slot is addressed but unresolved, same as skip for completeness purposes."""
    slot = _require_slot(state, slot_id)
    slot.status = SlotStatus.UNKNOWN
    slot.value = None
    slot.source = SlotSource.PATIENT
    slot.candidates = []
    _touch(state, slot)
    return ApplyResult(slot_id=slot_id, outcome=ApplyOutcome.ACCEPTED)
