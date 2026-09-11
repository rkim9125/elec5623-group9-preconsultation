"""Versioned consultation schema: the set of fields a pre-consultation collects.

C3 owns this definition. C4 (extraction) and C6 (persistence) consume it, so any
change here is an interface change: bump SCHEMA_VERSION, update
docs/api-contract.md in the same PR, and tag C4 + C6.

`SlotDef` is the static *definition*. `build_initial_slots()` turns the defs into
runtime `Slot` objects (all EMPTY) for a fresh session.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.core.models import Slot, SlotStatus, SlotType

SCHEMA_VERSION = "0.1"


class SlotActivation(BaseModel):
    """A conditional slot becomes askable only when another slot's value matches.

    `contains` matches membership in a LIST slot; `equals` matches a scalar slot.
    A slot with no activation is always askable.
    """

    when_slot: str
    equals: object | None = None
    contains: object | None = None


class SlotDef(BaseModel):
    slot_id: str
    label: str
    type: SlotType
    required: bool = False
    options: list[str] | None = None
    activation: SlotActivation | None = None
    prompt_hint: str | None = None  # fallback wording if the LLM is unavailable


CONSULTATION_SCHEMA: list[SlotDef] = [
    SlotDef(
        slot_id="chief_complaint",
        label="Main reason for the visit",
        type=SlotType.STRING,
        required=True,
        prompt_hint="In your own words, what is the main reason for this visit?",
    ),
    SlotDef(
        slot_id="symptom_duration_days",
        label="How long symptoms have lasted (days)",
        type=SlotType.NUMBER,
        required=True,
        prompt_hint="How many days have you had these symptoms?",
    ),
    SlotDef(
        slot_id="symptom_severity",
        label="Current severity",
        type=SlotType.ENUM,
        required=True,
        options=["mild", "moderate", "severe"],
        prompt_hint="Right now, would you say it is mild, moderate or severe?",
    ),
    SlotDef(
        slot_id="associated_symptoms",
        label="Other symptoms noticed",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Have you noticed any other symptoms alongside this?",
    ),
    SlotDef(
        slot_id="fever_duration_days",
        label="How long the fever has lasted (days)",
        type=SlotType.NUMBER,
        required=False,
        activation=SlotActivation(when_slot="associated_symptoms", contains="fever"),
        prompt_hint="How many days have you had a fever?",
    ),
    SlotDef(
        slot_id="current_medications",
        label="Current medications",
        type=SlotType.LIST,
        required=True,
        prompt_hint="What medications are you currently taking, if any?",
    ),
    SlotDef(
        slot_id="allergies",
        label="Known allergies",
        type=SlotType.LIST,
        required=True,
        prompt_hint="Do you have any known allergies?",
    ),
    SlotDef(
        slot_id="past_conditions",
        label="Relevant past medical conditions",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Any past medical conditions the clinician should know about?",
    ),
]

_BY_ID: dict[str, SlotDef] = {d.slot_id: d for d in CONSULTATION_SCHEMA}


def get_slot_def(slot_id: str) -> SlotDef:
    return _BY_ID[slot_id]


def all_slot_ids() -> list[str]:
    return [d.slot_id for d in CONSULTATION_SCHEMA]


def build_initial_slots() -> dict[str, Slot]:
    """Runtime slots for a fresh session: one per definition, all EMPTY."""
    return {
        d.slot_id: Slot(
            slot_id=d.slot_id,
            label=d.label,
            type=d.type,
            required=d.required,
            options=d.options,
            status=SlotStatus.EMPTY,
        )
        for d in CONSULTATION_SCHEMA
    }
