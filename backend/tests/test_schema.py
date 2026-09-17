from app.core.models import SlotStatus, SlotType
from app.core.schema import (
    CONSULTATION_SCHEMA,
    SCHEMA_VERSION,
    build_initial_slots,
    get_slot_def,
)


def test_schema_version_set():
    assert SCHEMA_VERSION == "0.2"


def test_initial_slots_cover_every_definition_and_start_empty():
    slots = build_initial_slots()
    assert set(slots) == {d.slot_id for d in CONSULTATION_SCHEMA}
    assert all(s.status == SlotStatus.EMPTY for s in slots.values())
    assert all(s.value is None for s in slots.values())


def test_enum_slots_carry_options():
    for d in CONSULTATION_SCHEMA:
        if d.type == SlotType.ENUM:
            assert d.options, f"{d.slot_id} is enum but has no options"


def test_conditional_slot_declared():
    fever = get_slot_def("fever_duration_days")
    assert fever.activation is not None
    assert fever.activation.when_slot == "associated_symptoms"
    assert fever.activation.contains == "fever"


def test_every_slot_has_a_prompt_hint():
    assert all(d.prompt_hint for d in CONSULTATION_SCHEMA)


def test_slot_ids_are_unique():
    ids = [d.slot_id for d in CONSULTATION_SCHEMA]
    assert len(ids) == len(set(ids))


def test_covers_the_six_history_taking_domains():
    # Sanity check against the checklist this schema was expanded from
    # (history of presenting complaint, associated symptoms, past medical
    # history, family history, social history, other context) — see
    # docs/implementation-status.md v0.2 entry for the sources.
    ids = {d.slot_id for d in CONSULTATION_SCHEMA}
    assert {"symptom_onset", "symptom_progression", "treatments_tried"} <= ids  # HPC
    assert {"associated_symptoms", "denied_symptoms"} <= ids  # associated symptoms
    assert {"past_conditions", "hospitalizations", "specialist_care"} <= ids  # PMH
    assert "family_history" in ids  # family history
    assert {"smoking_status", "alcohol_use", "occupation"} <= ids  # social history
    assert {"travel_history", "additional_notes"} <= ids  # other context


def test_associated_symptoms_is_required_but_richness_fields_are_optional():
    # Deliberate: only the "did you notice anything else" question is
    # mandatory. Family/social history and symptom-detail fields stay
    # optional per the project boundary (coverage of chosen fields, not an
    # exhaustive history) — see planner.should_stop's docstring.
    assert get_slot_def("associated_symptoms").required is True
    for slot_id in ["family_history", "smoking_status", "alcohol_use",
                     "symptom_onset", "hospitalizations", "travel_history"]:
        assert get_slot_def(slot_id).required is False
