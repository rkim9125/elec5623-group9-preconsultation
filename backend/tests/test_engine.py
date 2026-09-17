import pytest

from app.core.engine import (
    ApplyOutcome,
    SlotNotFound,
    apply_candidate,
    confirm_slot,
    detect_contradiction,
    edit_slot,
    is_slot_active,
    mark_unknown,
    skip_slot,
    validate_value,
)
from app.core.models import SlotHistoryEvent, SlotSource, SlotStatus
from app.core.schema import get_slot_def
from app.llm.base import ExtractedCandidate


def _cand(slot_id, value, confidence=0.7):
    return ExtractedCandidate(slot_id=slot_id, value=value, confidence=confidence, model="test")


# --- validate_value -------------------------------------------------------- #

@pytest.mark.parametrize(
    "slot_id, raw, expected",
    [
        ("chief_complaint", "  sore throat ", "sore throat"),
        ("symptom_duration_days", "3", 3),
        ("symptom_duration_days", 2.0, 2),
        ("symptom_severity", "Moderate", "moderate"),
        ("allergies", "penicillin", ["penicillin"]),
        ("allergies", [], []),
    ],
)
def test_validate_value_ok(slot_id, raw, expected):
    ok, value, err = validate_value(get_slot_def(slot_id), raw)
    assert ok and err is None
    assert value == expected


@pytest.mark.parametrize(
    "slot_id, raw",
    [
        ("chief_complaint", "   "),
        ("symptom_duration_days", "a while"),
        ("symptom_duration_days", -1),
        ("symptom_severity", "extreme"),
    ],
)
def test_validate_value_rejected(slot_id, raw):
    ok, value, err = validate_value(get_slot_def(slot_id), raw)
    assert not ok and value is None and err


# --- apply_candidate ----------------------------------------------------- #

def test_apply_candidate_records_and_sets_status(state):
    res = apply_candidate(state, _cand("chief_complaint", "sore throat"))
    assert res.outcome == ApplyOutcome.ACCEPTED
    slot = state.slots["chief_complaint"]
    assert slot.status == SlotStatus.CANDIDATE
    assert slot.value is None
    assert slot.candidates[0].value == "sore throat"


def test_apply_candidate_rejects_invalid(state):
    res = apply_candidate(state, _cand("symptom_duration_days", "ages"))
    assert res.outcome == ApplyOutcome.REJECTED
    assert state.slots["symptom_duration_days"].status == SlotStatus.EMPTY


def test_apply_candidate_unknown_slot(state):
    res = apply_candidate(state, _cand("not_a_slot", "x"))
    assert res.outcome == ApplyOutcome.UNKNOWN_SLOT


def test_candidates_sorted_by_confidence(state):
    apply_candidate(state, _cand("chief_complaint", "low", confidence=0.2))
    apply_candidate(state, _cand("chief_complaint", "high", confidence=0.9))
    assert [c.value for c in state.slots["chief_complaint"].candidates] == ["high", "low"]


# --- confirm / edit / skip --------------------------------------------- #

def test_confirm_promotes_top_candidate(state):
    apply_candidate(state, _cand("symptom_severity", "mild"))
    res = confirm_slot(state, "symptom_severity")
    assert res.outcome == ApplyOutcome.ACCEPTED
    slot = state.slots["symptom_severity"]
    assert slot.status == SlotStatus.CONFIRMED
    assert slot.value == "mild"
    assert slot.source == SlotSource.PATIENT
    assert slot.candidates == []


def test_confirm_with_explicit_value(state):
    res = confirm_slot(state, "symptom_duration_days", value="5")
    assert res.outcome == ApplyOutcome.ACCEPTED
    assert state.slots["symptom_duration_days"].value == 5


def test_confirm_without_candidate_is_rejected(state):
    res = confirm_slot(state, "allergies")
    assert res.outcome == ApplyOutcome.REJECTED


def test_skip_marks_slot_addressed_but_unresolved(state):
    res = skip_slot(state, "past_conditions")
    assert res.outcome == ApplyOutcome.ACCEPTED
    assert state.slots["past_conditions"].status == SlotStatus.SKIPPED
    assert state.slots["past_conditions"].value is None


def test_mark_unknown_is_distinct_from_skip(state):
    res = mark_unknown(state, "current_medications")
    assert res.outcome == ApplyOutcome.ACCEPTED
    slot = state.slots["current_medications"]
    assert slot.status == SlotStatus.UNKNOWN
    assert slot.status != SlotStatus.SKIPPED
    assert slot.value is None


def test_new_candidate_reopens_a_skipped_or_unknown_slot(state):
    skip_slot(state, "allergies")
    apply_candidate(state, _cand("allergies", "penicillin"))
    assert state.slots["allergies"].status == SlotStatus.CANDIDATE

    mark_unknown(state, "past_conditions")
    apply_candidate(state, _cand("past_conditions", "asthma"))
    assert state.slots["past_conditions"].status == SlotStatus.CANDIDATE


def test_require_slot_raises_for_unknown(state):
    with pytest.raises(SlotNotFound):
        confirm_slot(state, "nope", value="x")


# --- contradiction / correction -------------------------------------- #

def test_contradiction_detected_and_candidate_kept(state):
    confirm_slot(state, "symptom_severity", value="mild")
    res = apply_candidate(state, _cand("symptom_severity", "severe"))
    assert res.outcome == ApplyOutcome.CONTRADICTION
    slot = state.slots["symptom_severity"]
    assert slot.value == "mild"  # unchanged
    assert slot.candidates[0].value == "severe"  # kept for the UI to resolve
    assert detect_contradiction(slot, "severe") is True


def test_edit_resolves_contradiction(state):
    confirm_slot(state, "symptom_severity", value="mild")
    apply_candidate(state, _cand("symptom_severity", "severe"))
    res = edit_slot(state, "symptom_severity", "severe")
    assert res.outcome == ApplyOutcome.ACCEPTED
    slot = state.slots["symptom_severity"]
    assert slot.value == "severe"
    assert slot.status == SlotStatus.CONFIRMED
    assert slot.candidates == []


def test_agreeing_candidate_on_confirmed_slot_is_accepted(state):
    confirm_slot(state, "symptom_severity", value="mild")
    res = apply_candidate(state, _cand("symptom_severity", "Mild"))
    assert res.outcome == ApplyOutcome.ACCEPTED
    assert "matches" in (res.detail or "")


# --- conditional activation ------------------------------------------ #

def test_conditional_slot_inactive_until_dependency_matches(state):
    fever_def = get_slot_def("fever_duration_days")
    assert is_slot_active(state, fever_def) is False

    res = apply_candidate(state, _cand("fever_duration_days", 2))
    assert res.outcome == ApplyOutcome.INACTIVE

    confirm_slot(state, "associated_symptoms", value=["fever", "cough"])
    assert is_slot_active(state, fever_def) is True
    res = apply_candidate(state, _cand("fever_duration_days", 2))
    assert res.outcome == ApplyOutcome.ACCEPTED


# --- correction / audit history --------------------------------------- #

def test_confirm_records_a_confirmed_history_entry(state):
    confirm_slot(state, "chief_complaint", value="sore throat")
    assert len(state.history) == 1
    entry = state.history[0]
    assert entry.slot_id == "chief_complaint"
    assert entry.event == SlotHistoryEvent.CONFIRMED
    assert entry.previous_value is None
    assert entry.previous_status == SlotStatus.EMPTY
    assert entry.new_value == "sore throat"
    assert entry.new_status == SlotStatus.CONFIRMED
    assert entry.source == SlotSource.PATIENT


def test_correction_records_previous_and_new_value(state):
    confirm_slot(state, "symptom_severity", value="mild")
    edit_slot(state, "symptom_severity", "severe")

    corrections = [e for e in state.history if e.event == SlotHistoryEvent.CORRECTED]
    assert len(corrections) == 1
    entry = corrections[0]
    assert entry.slot_id == "symptom_severity"
    assert entry.previous_value == "mild"
    assert entry.previous_status == SlotStatus.CONFIRMED
    assert entry.new_value == "severe"


def test_reconfirming_the_same_value_does_not_add_a_duplicate_entry(state):
    confirm_slot(state, "symptom_severity", value="mild")
    confirm_slot(state, "symptom_severity", value="mild")
    assert len(state.history) == 1


def test_skip_and_unknown_are_recorded_distinctly(state):
    skip_slot(state, "past_conditions")
    mark_unknown(state, "current_medications")

    skip_entry = next(e for e in state.history if e.slot_id == "past_conditions")
    unknown_entry = next(e for e in state.history if e.slot_id == "current_medications")
    assert skip_entry.event == SlotHistoryEvent.SKIPPED
    assert skip_entry.new_status == SlotStatus.SKIPPED
    assert unknown_entry.event == SlotHistoryEvent.MARKED_UNKNOWN
    assert unknown_entry.new_status == SlotStatus.UNKNOWN


def test_reopening_a_skipped_slot_is_recorded(state):
    skip_slot(state, "allergies")
    apply_candidate(state, _cand("allergies", "penicillin"))

    reopened = [e for e in state.history if e.event == SlotHistoryEvent.REOPENED]
    assert len(reopened) == 1
    assert reopened[0].slot_id == "allergies"
    assert reopened[0].previous_status == SlotStatus.SKIPPED
    assert reopened[0].source == SlotSource.LLM


def test_history_is_append_only_and_in_order(state):
    confirm_slot(state, "chief_complaint", value="a")
    edit_slot(state, "chief_complaint", "b")
    edit_slot(state, "chief_complaint", "c")

    values = [e.new_value for e in state.history if e.slot_id == "chief_complaint"]
    assert values == ["a", "b", "c"]


def test_history_across_slots_does_not_interfere(state):
    confirm_slot(state, "chief_complaint", value="x")
    skip_slot(state, "past_conditions")
    assert len(state.history) == 2
    assert {e.slot_id for e in state.history} == {"chief_complaint", "past_conditions"}
