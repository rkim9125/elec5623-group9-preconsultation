from app.core.models import SlotStatus, SlotType
from app.core.schema import (
    CONSULTATION_SCHEMA,
    SCHEMA_VERSION,
    build_initial_slots,
    get_slot_def,
)


def test_schema_version_set():
    assert SCHEMA_VERSION == "0.1"


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
