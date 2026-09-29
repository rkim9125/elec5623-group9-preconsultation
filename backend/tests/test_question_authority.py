"""Whose questions reach the clinician.

The proposal's output is the patient's own questions. The workflow catalogue is
explicit: `clinician_questions` must "retain the patient's wording" (§3.2), and
a generated draft "must not be silently attributed to the patient" (§3.5).

That is a business rule, so C3 enforces it in app/core/flow.py rather than
trusting every LLM adapter to remember. These tests use an adapter that ignores
the patient entirely — the same shape of mistake a real provider can make — and
pin that the patient's questions survive anyway.
"""

from app.core.engine import confirm_slot, skip_slot
from app.core.flow import finalise, patient_supplied_questions
from app.llm.base import GeneratedSummary

INVENTED = ["A question the patient never asked"]


class IgnoresThePatientLLM:
    """Returns its own questions regardless of what the patient wrote."""

    def extract_candidates(self, message, slots, schema_version):
        return []

    def phrase_question(self, slot, state):
        return "?"

    def generate_summary(self, state) -> GeneratedSummary:
        return GeneratedSummary(
            sections={}, patient_questions=list(INVENTED), model="ignores-patient"
        )


def test_patient_questions_override_whatever_the_adapter_returns(state):
    mine = ["Do I need antibiotics?", "Can I keep working?"]
    confirm_slot(state, "clinician_questions", value=mine)

    summary = finalise(state, IgnoresThePatientLLM())

    assert summary.patient_questions == mine
    assert INVENTED[0] not in summary.patient_questions


def test_generated_questions_are_kept_when_the_patient_gave_none(state):
    # Suggestions are fine as a fallback — they just can't displace the patient.
    summary = finalise(state, IgnoresThePatientLLM())
    assert summary.patient_questions == INVENTED


def test_skipping_the_question_slot_leaves_the_suggestions(state):
    skip_slot(state, "clinician_questions")
    assert patient_supplied_questions(state) is None
    assert finalise(state, IgnoresThePatientLLM()).patient_questions == INVENTED


def test_empty_list_is_not_treated_as_the_patients_questions(state):
    # "no questions" must not blank out the summary's question list entirely.
    confirm_slot(state, "clinician_questions", value=[])
    assert patient_supplied_questions(state) is None
