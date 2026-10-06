"""The blockers the frontend listed in docs/frontend-rest-api.md §8.

Each test is one of the "this doesn't map onto the backend" items, written the
way the UI actually supplies the data, so if the backend regresses on any of
them the frontend finds out here rather than during integration.
"""

from app.core.engine import confirm_slot, mark_unknown, skip_slot, validate_value
from app.core.models import SlotStatus, SlotType
from app.core.schema import get_slot_def


def test_visit_reasons_are_an_ordered_list_not_a_single_string(state):
    # The UI collects several reasons and the order is the patient's priority.
    reasons = ["knee pain", "poor sleep", "repeat prescription"]
    confirm_slot(state, "chief_complaint", value=reasons)
    assert state.slots["chief_complaint"].value == reasons  # order preserved


def test_a_single_reason_still_works(state):
    # Extraction (and older callers) send bare text; it becomes one reason.
    confirm_slot(state, "chief_complaint", value="sore throat")
    assert state.slots["chief_complaint"].value == ["sore throat"]


def test_onset_keeps_the_patients_own_words(state):
    # "며칠 전부터" / "about three weeks ago" must survive as written. The
    # catalogue forbids converting an approximate onset into an exact number.
    for phrase in ["about three weeks ago", "며칠 전부터", "since Monday"]:
        confirm_slot(state, "symptom_onset", value=phrase)
        assert state.slots["symptom_onset"].value == phrase


def test_onset_is_required_and_duration_in_days_is_not(state):
    # The question the patient must be able to answer is "when did it start",
    # not "how many days" — which they often cannot give.
    assert get_slot_def("symptom_onset").required is True
    assert get_slot_def("symptom_onset").type == SlotType.STRING
    assert get_slot_def("symptom_duration_days").required is False


def test_the_five_ui_answer_states_are_all_representable(state):
    # unasked / unanswered -> empty, none -> confirmed with an empty list,
    # not sure -> unknown, prefer not to answer -> skipped.
    assert state.slots["allergies"].status == SlotStatus.EMPTY

    confirm_slot(state, "allergies", value=[])
    assert state.slots["allergies"].status == SlotStatus.CONFIRMED
    assert state.slots["allergies"].value == []  # "none" is an answer, not a gap

    mark_unknown(state, "current_medications")
    assert state.slots["current_medications"].status == SlotStatus.UNKNOWN

    skip_slot(state, "past_conditions")
    assert state.slots["past_conditions"].status == SlotStatus.SKIPPED

    # and the two refusals stay distinguishable from each other
    assert (
        state.slots["current_medications"].status
        != state.slots["past_conditions"].status
    )


def test_course_frequency_and_impact_all_have_slots():
    assert get_slot_def("symptom_progression").options == [
        "improving",
        "worsening",
        "unchanged",
    ]
    assert get_slot_def("symptom_frequency").type == SlotType.STRING
    assert get_slot_def("functional_impact").type == SlotType.STRING


def test_frequency_accepts_plain_language_not_a_count():
    ok, value, err = validate_value(get_slot_def("symptom_frequency"), "comes and goes")
    assert ok and value == "comes and goes" and err is None


def test_patient_questions_are_a_list_the_patient_owns(state):
    mine = ["Do I need antibiotics?", "Can I keep working?"]
    confirm_slot(state, "clinician_questions", value=mine)
    assert state.slots["clinician_questions"].value == mine
