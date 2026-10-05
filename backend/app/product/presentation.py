"""Optional patient-authored answer aids for the fixed preparation forms.

This is presentation metadata, not a clinical decision tree. Nothing here is a
default answer or an inferred fact. The server continues accepting and retaining
the patient's exact text, including answers outside these suggestions.
"""
from __future__ import annotations

from copy import deepcopy


def choices(*values: str | tuple[str, str], multiple: bool = True,
            helper: str | None = None, question: str | None = None) -> dict:
    options = [{"label": v[0], "value": v[1]} if isinstance(v, tuple)
               else {"label": v, "value": v} for v in values]
    result = {"kind": "choices", "options": options, "multiple": multiple,
              "helper": helper or ("Choose any that fit, or describe your experience in your own words."
                                   if multiple else "Choose one that fits, or describe your experience in your own words.")}
    if question:
        result["question"] = question
    return result


def body_map(illustration: str, regions: tuple[tuple[str, str], ...], *,
             multiple: bool = True) -> dict:
    return {"kind": "body_map", "illustration": illustration, "multiple": multiple,
            "options": [{"region": region, "label": label, "value": label}
                        for region, label in regions],
            "helper": "Select an area on the picture or use the labels. Left and right refer to your own body. You can describe another area below."}


LEG_REGIONS = tuple((f"{side}_{part}", f"{side.title()} {part}")
                    for part in ("thigh", "knee", "shin", "calf", "ankle", "foot")
                    for side in ("left", "right"))
ARM_REGIONS = tuple((f"{side}_{part}", f"{side.title()} {part.replace('_', ' ')}")
                    for part in ("upper_arm", "elbow", "forearm", "wrist", "hand")
                    for side in ("left", "right"))
BACK_REGIONS = (("lower_back_left", "Left lower back"),
                ("lower_back_centre", "Centre of lower back"),
                ("lower_back_right", "Right lower back"))
NECK_REGIONS = (("neck", "Neck"), ("left_shoulder", "Left shoulder"),
                ("right_shoulder", "Right shoulder"))
HEAD_REGIONS = (("forehead", "Forehead"), ("left_temple", "Left temple"),
                ("right_temple", "Right temple"), ("top_head", "Top of head"),
                ("back_head", "Back of head"))
ABDOMEN_REGIONS = (("upper_abdomen_left", "Upper left abdomen"),
                   ("upper_abdomen_centre", "Upper central abdomen"),
                   ("upper_abdomen_right", "Upper right abdomen"),
                   ("middle_abdomen_left", "Middle left abdomen"),
                   ("around_navel", "Around the belly button"),
                   ("middle_abdomen_right", "Middle right abdomen"),
                   ("lower_abdomen_left", "Lower left abdomen"),
                   ("lower_abdomen_centre", "Lower central abdomen"),
                   ("lower_abdomen_right", "Lower right abdomen"))
BODY_REGIONS = (("face", "Face"), ("scalp", "Scalp"), ("neck", "Neck"),
                ("chest", "Chest"), ("back", "Back"), ("abdomen", "Abdomen"),
                ("left_arm", "Left arm"), ("right_arm", "Right arm"),
                ("left_hand", "Left hand"), ("right_hand", "Right hand"),
                ("left_leg", "Left leg"), ("right_leg", "Right leg"),
                ("left_foot", "Left foot"), ("right_foot", "Right foot"))

SENSATION = choices("Aching", "Sharp", "Throbbing", "Burning", "Tight", "Stiff", "Tender")
DAY_PATTERN = choices("On waking", "In the morning", "In the afternoon", "In the evening", "During the night", "Varies through the day")
EPISODE_LENGTH = choices("Less than a minute", "A few minutes", "Up to an hour", "Several hours", "Most of the day", "More than a day", multiple=False,
                         helper="Choose the closest description if you can. Add a more precise duration or a different pattern below.")

# Shared and recurring keys use the same neutral prompt only when their meaning
# is the same across workflows. Topic-specific alternatives take precedence.
COMMON = {
    "appointment_goal": choices(("Understand my symptoms", "I would like to understand my symptoms."),
                                ("Discuss next steps", "I would like to discuss next steps."),
                                ("Review an existing concern", "I would like to review an existing health concern."),
                                ("Discuss results", "I would like to discuss existing test results."),
                                ("Discuss medicines", "I would like to discuss my medicines."),
                                ("Ask about everyday impact", "I would like to discuss the impact on my everyday life."),
                                question="What would you like to get from your appointment?"),
    "clinician_questions": choices(("What might explain this?", "What might explain what I have noticed?"),
                                  ("What information would help?", "What other information would help you understand my concern?"),
                                  ("What are my options?", "What options can we discuss?"),
                                  ("What happens next?", "What happens after this appointment?"),
                                  question="Which questions would you like to take to your clinician?"),
    "symptom_frequency": choices("Several times a day", "About once a day", "Several days a week", "About once a week", "Less than once a week", "Present all the time", "No regular pattern", multiple=False),
    "symptom_course": choices("Improving overall", "Worsening overall", "About the same", "Comes and goes", "Varies without a clear pattern", multiple=False),
    "functional_impact": choices(("Daily tasks", "My usual daily tasks are affected."),
                                 ("Work or study", "My work or study is affected."),
                                 ("Sleep", "My sleep is affected."),
                                 ("Exercise or movement", "My exercise or usual movement is affected."),
                                 ("Social activities", "My social activities are affected."),
                                 ("Personal care", "My personal care is affected."),
                                 helper="Choose activities that are affected, then add how they have changed. If nothing is affected, you can say so in your own words."),
    "previous_consultation.exists": choices(("Yes", "Yes"), ("No", "No"), multiple=False),
    "episode_length": EPISODE_LENGTH,
    "ear_side": choices("Left ear", "Right ear", "Both ears", multiple=False),
    "eye_side": choices("Left eye", "Right eye", "Both eyes", multiple=False),
    "review_changes": choices(("Symptoms", "I would like to discuss changes in my symptoms."),
                              ("Medicines", "I would like to discuss changes in my medicines."),
                              ("Daily routine", "I would like to discuss changes in my daily routine."),
                              ("Home records", "I would like to discuss changes in my home records.")),
    "medication_experience": choices(("Remembering doses", "I would like to discuss remembering doses."),
                                     ("Using the medicine", "I would like to discuss how I use this medicine."),
                                     ("My experience after taking it", "I would like to describe my experience after taking this medicine."),
                                     ("Questions about the medicine", "I have questions about this medicine.")),
}

TOPICS = {
    "WF-01": {
        "leg.pain_site": body_map("legs", LEG_REGIONS),
        "leg.pain_character": SENSATION,
        "leg.activity_context": choices("Walking", "Running", "Climbing stairs", "Standing", "Sitting", "Resting", "Lying in bed"),
        "leg.change_factors": choices(("Changes with movement", "The pain changes with movement."),
                                      ("Changes with rest", "The pain changes with rest."),
                                      ("Changes with position", "The pain changes when I change position."),
                                      helper="Choose anything you have noticed, then describe whether it helps, worsens or otherwise changes the pain."),
    },
    "WF-02": {
        "back.pain_site": body_map("back", BACK_REGIONS),
        "back.pain_character": SENSATION,
        "back.change_factors": choices(("Bending", "The discomfort changes when I bend."),
                                       ("Sitting", "The discomfort changes when I sit."),
                                       ("Standing", "The discomfort changes when I stand."),
                                       ("Walking", "The discomfort changes when I walk."),
                                       ("Lying down", "The discomfort changes when I lie down."),
                                       helper="Add whether each movement or position helps, worsens or otherwise changes the discomfort."),
    },
    "WF-03": {
        "neck_shoulder.main_site": body_map("neck_shoulders", NECK_REGIONS, multiple=False),
        "neck_shoulder.character": SENSATION,
        "neck_shoulder.movement_context": choices("Turning my head", "Looking up or down", "Lifting my arm", "Reaching overhead", "Carrying something", helper="Choose movements you have noticed, then describe how the discomfort changes."),
    },
    "WF-04": {
        "upper_limb.pain_site": body_map("arms_hands", ARM_REGIONS),
        "upper_limb.character": SENSATION,
        "upper_limb.task_context": choices("Typing or using a mouse", "Writing", "Gripping objects", "Lifting or carrying", "Reaching", "Repetitive hand movements", multiple=False),
    },
    "WF-05": {
        "headache.pain_site": body_map("head", HEAD_REGIONS),
        "headache.character": choices("Throbbing", "Aching", "Pressure", "Tight band feeling", "Sharp"),
        "headache.episode_length": EPISODE_LENGTH,
    },
    "WF-06": {
        "dizziness.description": choices("A spinning sensation", "Feeling light-headed", "Feeling unsteady", "Feeling as if I might faint"),
        "dizziness.episode_length": EPISODE_LENGTH,
        "dizziness.episode_context": choices("Standing up", "Turning my head", "Walking", "Sitting", "Lying down", "During activity", "At rest", helper="Choose what you are doing when it happens. This records timing, not a cause."),
    },
    "WF-07": {
        "fatigue.description": choices("Feeling sleepy", "Low energy", "Feeling physically worn out", "Difficulty concentrating", "Finding it hard to get started"),
        "fatigue.daily_pattern": DAY_PATTERN,
        "fatigue.rest_experience": choices("I feel more rested afterwards", "I still feel tired afterwards", "It varies", multiple=False),
        "fatigue.sleep_description": choices("Difficulty falling asleep", "Waking during the night", "Waking earlier than intended", "Sleeping more than usual", "Sleeping less than usual", "Not feeling refreshed on waking"),
    },
    "WF-08": {
        "sleep.main_difficulty": choices("Falling asleep", "Waking during the night", "Waking too early", "Keeping a regular sleep routine", "Not feeling refreshed on waking"),
        "symptom_frequency": choices("About 1 night a week", "About 2–3 nights a week", "About 4–5 nights a week", "About 6–7 nights a week", "It varies from week to week", multiple=False),
        "sleep.observed_context": choices(("Changes in routine", "I notice difficult nights around changes in my routine."),
                                          ("Busy or stressful days", "I notice difficult nights around busy or stressful days."),
                                          ("Noise or light", "I notice noise or light on difficult nights."),
                                          helper="Include only patterns you have noticed. These options do not establish what causes the difficulty."),
    },
    "WF-09": {
        "cough.description": choices("Dry cough", "Cough with mucus", "Tickling cough", "Coughing in bouts"),
        "cough.daily_pattern": DAY_PATTERN,
    },
    "WF-10": {
        "nasal.main_description": choices("Blocked nose", "Runny nose", "Sneezing", "Itchy nose"),
        "nasal.time_pattern": choices("Throughout the year", "At particular times of year", "In separate episodes", "No clear pattern", multiple=False),
        "nasal.environment_context": choices("At home", "At work or study", "Outdoors", "In bed", "In several places", helper="Choose where you notice symptoms; this does not identify an allergy or a cause."),
    },
    "WF-11": {
        "throat_focus": choices("Throat discomfort", "A change in my voice", "Both throat discomfort and voice changes", multiple=False),
        "throat_sensation": choices("Dry", "Scratchy", "Sore", "Burning", "A lump-like feeling"),
        "voice_change_description": choices("Hoarse", "Raspy", "Quieter", "Voice breaks", "Different pitch", "Losing my voice"),
        "voice_use_context": choices("Ordinary conversation", "Speaking for a long time", "Phone or video calls", "Singing", "Speaking loudly"),
    },
    "WF-12": {
        "ear_focus": choices("Ear discomfort", "A change in hearing", "Ringing or another sound", "A blocked feeling"),
        "ear_discomfort_description": choices("Aching", "Pressure", "Itching", "Fullness", "Sharp discomfort"),
        "hearing_context": choices("Conversation in a quiet room", "Conversation with background noise", "Phone calls", "Television or music", "Group conversations"),
    },
    "WF-13": {
        "eye_sensation": choices("Dry", "Gritty", "Itchy", "Burning", "Watery", "Sore"),
        "eye_context": choices("Using screens", "Reading", "Outdoors", "In air conditioning", "On waking", "Toward the end of the day"),
    },
    "WF-14": {
        "abdominal_location": body_map("abdomen", ABDOMEN_REGIONS),
        "abdominal_quality": choices("Cramping", "Aching", "Sharp", "Burning", "Pressure", "Bloated feeling"),
        "abdominal_context": choices("Before eating", "After eating", "Around a bowel movement", "During activity", "At rest", helper="Choose any timing you have noticed, then describe it. This does not establish a cause."),
    },
    "WF-15": {
        "indigestion_description": choices("Burning sensation", "Uncomfortable fullness", "Bloating", "Belching", "Sour taste"),
        "indigestion_context": choices("After a meal", "When lying down", "When bending", "During the night", helper="Choose situations when you notice it. Describe other patterns or differences below."),
    },
    "WF-16": {
        "bowel_frequency": choices("More than once a day", "About once a day", "Every 2–3 days", "Less often than every 3 days", "No regular pattern", multiple=False),
        "stool_description": choices("Separate hard lumps", "Firm and lumpy", "Formed", "Soft", "Loose", "Watery"),
        "bowel_difficulty": choices("Straining", "Hard stools", "Feeling I have not finished", "Discomfort during a bowel movement"),
    },
    "WF-17": {
        "stool_description": choices("Soft pieces", "Mushy", "Loose", "Watery", "Varies during an episode"),
        "loose_stool_context": choices("Around meals", "After waking", "During travel", "During busy or stressful periods", helper="Choose timing or situations you have noticed, without assuming they are the cause."),
    },
    "WF-18": {
        "urinary_focus": choices("Passing urine more often", "A sudden need to pass urine", "Leakage", "Discomfort when passing urine", "A change in urine flow"),
        "urination_pattern": choices("Frequent daytime trips", "Waking at night to pass urine", "An urgent need to go", "Small amounts at a time", "An irregular pattern"),
        "leakage_context": choices("Coughing or sneezing", "Laughing", "Exercise or movement", "On the way to the toilet", "During sleep"),
        "urinary_discomfort_description": choices("Burning", "Stinging", "Aching", "Pressure"),
    },
    "WF-19": {
        "menstrual_focus": choices("Timing or regularity", "Amount of bleeding", "Period-related discomfort", "Other period-related symptoms"),
        "menstrual_current_pattern": choices("More frequent than my usual pattern", "Less frequent than my usual pattern", "Less predictable than usual", "My periods have stopped", "Timing is similar to my usual pattern", multiple=False),
        "menstrual_flow_description": choices("Lighter than usual", "Heavier than usual", "Similar to usual", "Varies between periods", multiple=False),
        "menstrual_symptom_timing": choices("Before my period", "During my period", "After my period", "Between periods", "No clear timing pattern"),
    },
    "WF-20": {
        "skin_location": body_map("body", BODY_REGIONS),
        "skin_appearance": choices("Redness or a colour change", "Small bumps", "Dry or flaky areas", "Raised patches", "Blisters", "Cracked skin"),
        "skin_sensation": choices("Itchy", "Sore", "Burning", "Tender", "Dry or tight"),
    },
    "WF-21": {"skin_sites": body_map("body", BODY_REGIONS)},
    "WF-22": {},  # Course, frequency, daily impact and previous discussion above.
    "WF-23": {
        "previous_actions": choices(("Support from someone I know", "I have been using support from someone I know."),
                                    ("Professional support", "I have been using support from a health professional."),
                                    ("An existing care plan", "I have been using an existing care plan."),
                                    ("My own routines", "I have been using my own routines for support."),
                                    helper="Choose support you are already using, if you want to include it. These are not suggestions to start a treatment."),
    },
    "WF-24": {},  # Medicine experience and review changes above; readings stay exact.
    "WF-25": {
        "diabetes_care_experience": choices(("Keeping records", "I would like to discuss keeping my usual records."),
                                           ("My medicines", "I would like to discuss my medicines."),
                                           ("Daily routine", "I would like to discuss how my usual care fits into daily life."),
                                           ("Appointments or support", "I would like to discuss my appointments or support.")),
    },
    "WF-26": {
        "asthma.review_experience": choices(("Breathing symptoms", "I would like to describe my breathing symptoms over this period."),
                                           ("Changes over time", "I would like to describe changes in my breathing over this period."),
                                           ("Patterns I have noticed", "I would like to describe patterns I have noticed in my breathing over this period.")),
        "sleep_impact": choices(("Falling asleep", "Breathing symptoms have affected falling asleep."),
                                ("Waking during sleep", "Breathing symptoms have woken me during sleep."),
                                ("Waking earlier", "Breathing symptoms have made me wake earlier than intended."),
                                helper="Choose only experiences you have had during this review period, or describe your sleep in your own words."),
    },
    "WF-27": {
        "concern_description": choices(("Review how I take my medicine", "I would like to review how I take my medicine."),
                                       ("Discuss my experience", "I would like to discuss my experience with my medicine."),
                                       ("Discuss an existing prescription", "I would like to discuss an existing prescription."),
                                       helper="Choose a starting point if helpful. Enter the actual medicine name in the medicine field below."),
        "medication_supply": choices("I have run out", "I have a few days left", "I have about a week left", "I have several weeks left", "I have more than a month left", multiple=False,
                                     helper="Choose an estimate if helpful, or enter the amount you have. This does not arrange a prescription."),
    },
    "WF-28": {
        "previous_tests.result_source": choices("A copy of a written report", "Results in a patient portal", "Information from a clinician", "A message or letter about the result", helper="Choose information you already have. You can upload a copy separately and describe what it says in your own words."),
    },
    "WF-29": {
        "prevention_topic": choices("Vaccination questions", "Screening questions", "Family history", "General health checks", "Lifestyle and wellbeing questions", helper="Choose topics to discuss. These options do not mean a check or screening test is recommended for you."),
    },
    # Agenda mode uses shared appointment goal and clinician question aids.
    # Its actual topics are individual GENERAL or selected workflow concerns.
    "WF-30": {},
}


def for_field(workflow_id: str | None, key: str) -> dict | None:
    """Return an independent payload so request-specific changes cannot leak."""
    presentation = TOPICS.get(workflow_id, {}).get(key, COMMON.get(key))
    return deepcopy(presentation) if presentation else None
