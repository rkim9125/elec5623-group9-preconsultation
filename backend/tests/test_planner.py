from app.core.engine import apply_candidate, confirm_slot, skip_slot
from app.core.models import SessionStatus
from app.core.planner import (
    DEFAULT_MAX_QUESTIONS,
    StopReason,
    compute_completeness,
    select_next_slot,
    should_stop,
)
from app.llm.base import ExtractedCandidate

REQUIRED = ["chief_complaint", "symptom_duration_days", "symptom_severity",
            "current_medications", "allergies"]


def _cand(slot_id, value):
    return ExtractedCandidate(slot_id=slot_id, value=value, confidence=0.8, model="test")


def _confirm_all_required(state):
    confirm_slot(state, "chief_complaint", value="sore throat")
    confirm_slot(state, "symptom_duration_days", value=3)
    confirm_slot(state, "symptom_severity", value="mild")
    confirm_slot(state, "current_medications", value=[])
    confirm_slot(state, "allergies", value=[])


# --- completeness ------------------------------------------------------- #

def test_fresh_state_completeness_is_zero(state):
    c = compute_completeness(state)
    assert c.coverage == 0.0
    assert c.resolution == 0.0
    assert set(c.unresolved_required) == set(REQUIRED)
    # 8 slots in the schema, but fever_duration_days is inactive → 7 active
    assert c.active_total == 7


def test_skipped_counts_for_coverage_not_resolution(state):
    skip_slot(state, "chief_complaint")
    c = compute_completeness(state)
    assert c.addressed == 1
    assert c.coverage > 0
    assert c.resolution == 0.0
    assert "chief_complaint" in c.unresolved_required


def test_full_required_gives_resolution_one(state):
    _confirm_all_required(state)
    c = compute_completeness(state)
    assert c.resolution == 1.0
    assert c.unresolved_required == []


def test_activating_conditional_slot_expands_active_total(state):
    before = compute_completeness(state).active_total
    confirm_slot(state, "associated_symptoms", value=["fever"])
    after = compute_completeness(state).active_total
    assert after == before + 1  # fever_duration_days became active


# --- next-slot selection --------------------------------------------- #

def test_next_slot_is_first_required_in_schema_order(state):
    assert select_next_slot(state) == "chief_complaint"


def test_next_slot_skips_resolved_and_prefers_required(state):
    confirm_slot(state, "chief_complaint", value="x")
    skip_slot(state, "symptom_duration_days")
    # symptom_severity is the next required, optional associated_symptoms comes later
    assert select_next_slot(state) == "symptom_severity"


def test_candidate_slot_still_counts_as_pending(state):
    confirm_slot(state, "chief_complaint", value="x")
    apply_candidate(state, _cand("symptom_duration_days", 3))  # candidate, not confirmed
    assert select_next_slot(state) == "symptom_duration_days"


def test_next_slot_none_when_all_addressed(state):
    for sid in ["chief_complaint", "symptom_duration_days", "symptom_severity",
                "associated_symptoms", "current_medications", "allergies",
                "past_conditions"]:
        skip_slot(state, sid)
    assert select_next_slot(state) is None


# --- stopping -------------------------------------------------------- #

def test_does_not_stop_with_required_pending(state):
    assert should_stop(state).stop is False


def test_stops_when_all_required_addressed(state):
    _confirm_all_required(state)
    d = should_stop(state)
    assert d.stop is True
    assert d.reason == StopReason.ALL_REQUIRED_ADDRESSED


def test_stops_on_question_limit(state):
    d = should_stop(state, asked_count=DEFAULT_MAX_QUESTIONS)
    assert d.stop is True
    assert d.reason == StopReason.QUESTION_LIMIT


def test_stops_when_abandoned(state):
    state.status = SessionStatus.ABANDONED
    d = should_stop(state)
    assert d.stop is True
    assert d.reason == StopReason.SESSION_ABANDONED


def test_skipping_required_still_allows_stop(state):
    for sid in REQUIRED:
        skip_slot(state, sid)
    assert should_stop(state).stop is True
