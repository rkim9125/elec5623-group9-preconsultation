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

SCHEMA_VERSION = "0.3"


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
    # -- History of presenting complaint -------------------------------- #
    # Domain split follows a standard clinical history-taking checklist
    # (onset/location/character/severity/progression/triggers/relieving
    # factors/treatments-tried) — see docs/implementation-status.md for the
    # references this was checked against (v0.2).
    SlotDef(
        slot_id="chief_complaint",
        label="Main reason for the visit",
        type=SlotType.STRING,
        required=True,
        prompt_hint="In your own words, what is the main reason for this visit?",
    ),
    SlotDef(
        slot_id="symptom_onset",
        label="How the symptoms started",
        type=SlotType.ENUM,
        required=False,
        options=["sudden", "gradual"],
        prompt_hint="Did this come on suddenly, or build up gradually?",
    ),
    SlotDef(
        slot_id="symptom_duration_days",
        label="How long symptoms have lasted (days)",
        type=SlotType.NUMBER,
        required=True,
        prompt_hint="How many days have you had these symptoms?",
    ),
    SlotDef(
        slot_id="symptom_location",
        label="Where the symptoms are located",
        type=SlotType.STRING,
        required=False,
        prompt_hint="Where on your body do you notice this?",
    ),
    SlotDef(
        slot_id="symptom_character",
        label="What the symptoms feel like",
        type=SlotType.STRING,
        required=False,
        prompt_hint="How would you describe it (e.g. sharp, dull, throbbing)?",
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
        slot_id="symptom_progression",
        label="How the symptoms are changing over time",
        type=SlotType.ENUM,
        required=False,
        options=["improving", "worsening", "unchanged"],
        prompt_hint="Is it getting better, getting worse, or staying about the same?",
    ),
    SlotDef(
        slot_id="symptom_triggers",
        label="Things that bring it on or make it worse",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Does anything seem to bring this on or make it worse?",
    ),
    SlotDef(
        slot_id="symptom_relieving_factors",
        label="Things that make it better",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Does anything make it feel better?",
    ),
    SlotDef(
        slot_id="treatments_tried",
        label="Treatments already tried",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Have you tried anything already (medication, rest, etc.)?",
    ),
    SlotDef(
        slot_id="functional_impact",
        label="Effect on everyday activities",
        type=SlotType.STRING,
        required=False,
        prompt_hint="How does it affect your usual activities?",
    ),
    # -- Associated symptoms --------------------------------------------- #
    SlotDef(
        slot_id="associated_symptoms",
        label="Other symptoms noticed",
        type=SlotType.LIST,
        required=True,
        prompt_hint="Have you noticed any other symptoms alongside this?",
    ),
    SlotDef(
        slot_id="denied_symptoms",
        label="Symptoms explicitly ruled out",
        type=SlotType.LIST,
        required=False,
        prompt_hint=(
            "Is there anything you specifically have NOT noticed "
            "(e.g. no fever, no shortness of breath)?"
        ),
    ),
    SlotDef(
        slot_id="fever_duration_days",
        label="How long the fever has lasted (days)",
        type=SlotType.NUMBER,
        required=False,
        activation=SlotActivation(when_slot="associated_symptoms", contains="fever"),
        prompt_hint="How many days have you had a fever?",
    ),
    # -- Past medical history / medications ------------------------------ #
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
    SlotDef(
        slot_id="hospitalizations",
        label="Past hospitalisations or surgeries",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Have you been hospitalised or had any surgeries before?",
    ),
    SlotDef(
        slot_id="specialist_care",
        label="Ongoing specialist care",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Are you currently under the care of any specialists?",
    ),
    # -- Family history ---------------------------------------------------#
    SlotDef(
        slot_id="family_history",
        label="Relevant family history",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Does this run in your family, or any related family history?",
    ),
    # -- Social history --------------------------------------------------- #
    SlotDef(
        slot_id="smoking_status",
        label="Smoking status",
        type=SlotType.ENUM,
        required=False,
        options=["never", "former", "current"],
        prompt_hint="Do you currently smoke, used to, or never have?",
    ),
    SlotDef(
        slot_id="alcohol_use",
        label="Alcohol use",
        type=SlotType.ENUM,
        required=False,
        options=["none", "occasional", "regular"],
        prompt_hint="How would you describe your alcohol use?",
    ),
    SlotDef(
        slot_id="occupation",
        label="Occupation",
        type=SlotType.STRING,
        required=False,
        prompt_hint="What's your occupation?",
    ),
    # -- Other contextual information -------------------------------------#
    SlotDef(
        slot_id="travel_history",
        label="Recent travel",
        type=SlotType.LIST,
        required=False,
        prompt_hint="Have you travelled anywhere recently?",
    ),
    SlotDef(
        slot_id="additional_notes",
        label="Anything else for the doctor",
        type=SlotType.STRING,
        required=False,
        prompt_hint="Is there anything else you'd like the doctor to know?",
    ),
    # -- Patient agenda ---------------------------------------------------- #
    # The catalogue (docs/workflow-catalogue.md §3.2) lists these as
    # "every session" targets, and the proposal's stated output is the
    # patient's own questions and goals for the consultation — so they are
    # required, like the other every-session fields. The patient can still
    # skip or answer "I don't know"; requiring them only means the planner
    # will actually ask.
    SlotDef(
        slot_id="patient_worry",
        label="What worries the patient most",
        type=SlotType.STRING,
        required=True,
        prompt_hint="What concerns you most about this?",
    ),
    SlotDef(
        slot_id="appointment_goal",
        label="What the patient wants from the appointment",
        type=SlotType.STRING,
        required=True,
        prompt_hint="What would you most like to get from the appointment?",
    ),
    SlotDef(
        slot_id="clinician_questions",
        label="Questions for the clinician",
        type=SlotType.LIST,
        required=True,
        prompt_hint="What would you like to ask the clinician?",
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
