from app.core.models import SessionState
from app.core.schema import SCHEMA_VERSION, build_initial_slots
from app.llm.base import GeneratedSummary, LLMClient
from app.llm.fake import FakeLLM


def _state() -> SessionState:
    return SessionState(session_id="s1", schema_version=SCHEMA_VERSION, slots=build_initial_slots())


def test_fake_llm_satisfies_protocol():
    assert isinstance(FakeLLM(), LLMClient)


def test_extract_returns_candidates_targeting_known_slots():
    slots = build_initial_slots()
    cands = FakeLLM().extract_candidates(
        "I've had a fever and sore throat for 3 days", slots, SCHEMA_VERSION
    )
    by_slot = {c.slot_id for c in cands}
    assert "associated_symptoms" in by_slot
    assert "symptom_duration_days" in by_slot
    assert all(c.slot_id in slots for c in cands)
    assert all(0.0 <= c.confidence <= 1.0 for c in cands)


def test_fever_triggers_fever_duration_candidate():
    cands = FakeLLM().extract_candidates(
        "fever for 2 days", build_initial_slots(), SCHEMA_VERSION
    )
    assert any(c.slot_id == "fever_duration_days" and c.value == 2 for c in cands)


def test_weeks_are_converted_to_days():
    cands = FakeLLM().extract_candidates(
        "cough for 2 weeks", build_initial_slots(), SCHEMA_VERSION
    )
    dur = next(c for c in cands if c.slot_id == "symptom_duration_days")
    assert dur.value == 14


def test_phrase_question_returns_text():
    slots = build_initial_slots()
    q = FakeLLM().phrase_question(slots["allergies"], _state())
    assert isinstance(q, str) and q.strip()


def test_generate_summary_shape():
    out = FakeLLM().generate_summary(_state())
    assert isinstance(out, GeneratedSummary)
    assert len(out.patient_questions) >= 1


def test_summary_prefers_the_patients_own_questions():
    from app.core.engine import confirm_slot

    state = _state()
    mine = ["Do I need a scan?", "Can I keep running?"]
    confirm_slot(state, "clinician_questions", value=mine)
    assert FakeLLM().generate_summary(state).patient_questions == mine


def test_summary_distinguishes_skipped_from_unknown():
    from app.core.engine import mark_unknown, skip_slot

    state = _state()
    skip_slot(state, "occupation")
    mark_unknown(state, "allergies")
    sections = FakeLLM().generate_summary(state).sections
    assert sections["Occupation"] != sections["Known allergies"]
    assert "not to answer" in sections["Occupation"]
    assert "did not know" in sections["Known allergies"]
