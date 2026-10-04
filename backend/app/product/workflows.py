"""Versioned preparation catalogue. These question templates are not clinical protocols.

The 30 source question banks are retained verbatim; deterministic conditions below
control eligibility. Shared fields are instantiated once per session.
"""
from __future__ import annotations

WORKFLOWS: list[dict] = [{'id': 'WF-01',
  'title': 'Leg pain',
  'category': 'Symptoms',
  'description': "Activate after an explicit report of leg pain or the patient's selection of this topic.",
  'questions': [{'key': 'leg.pain_site',
                 'label': 'Leg · pain site',
                 'question': 'Where in your leg do you feel the pain?'},
                {'key': 'leg.pain_character',
                 'label': 'Leg · pain character',
                 'question': 'How would you describe the pain in your own words?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do you notice the pain?'},
                {'key': 'leg.activity_context',
                 'label': 'Leg · activity context',
                 'question': 'What are you usually doing when you notice it?'},
                {'key': 'leg.change_factors',
                 'label': 'Leg · change factors',
                 'question': 'What have you noticed changes the pain?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does the pain affect your everyday activities?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss at your appointment?'}],
  'adaptation_notes': 'If the patient explicitly reports an injury, activate `leg.reported_event` and ask '
                      '“What happened when you injured your leg?” If the patient reports pain travelling '
                      'elsewhere, activate `leg.pain_spread` and ask “Where does the pain travel?” Otherwise '
                      'those targets remain inactive. Facts already supplied resolve their targets without '
                      'another question.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-02',
  'title': 'Lower back discomfort',
  'category': 'Symptoms',
  'description': 'Activate from explicitly reported lower back discomfort or patient selection.',
  'questions': [{'key': 'back.pain_site',
                 'label': 'Back · pain site',
                 'question': 'Where in your lower back is the discomfort?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this problem?'},
                {'key': 'back.pain_character',
                 'label': 'Back · pain character',
                 'question': 'What does the discomfort feel like?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often does it bother you?'},
                {'key': 'back.change_factors',
                 'label': 'Back · change factors',
                 'question': 'What have you noticed changes the discomfort?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does the discomfort affect your daily routine?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for this problem?'}],
  'adaptation_notes': 'If the patient explicitly reports lifting or another event around onset, activate '
                      '`back.reported_event` and ask “What happened around the time the discomfort began?” '
                      'If they report pain spreading, activate `back.pain_spread` and ask “Where does it '
                      'spread?” If they report a previous appointment, use '
                      '`previous_consultation.reported_explanation` to capture what they recall being told. '
                      'Do not create an inferred diagnosis from that recollection.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-03',
  'title': 'Neck and shoulder discomfort',
  'category': 'Symptoms',
  'description': 'Activate for explicitly described neck or shoulder discomfort, including patient-described '
                 'stiffness.',
  'questions': [{'key': 'neck_shoulder.main_site',
                 'label': 'Neck shoulder · main site',
                 'question': 'Which area bothers you most?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice the discomfort?'},
                {'key': 'neck_shoulder.character',
                 'label': 'Neck shoulder · character',
                 'question': 'How would you describe the discomfort?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do you experience it?'},
                {'key': 'neck_shoulder.movement_context',
                 'label': 'Neck shoulder · movement context',
                 'question': 'Which movements seem to change it?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does the discomfort affect everyday tasks?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried?'}],
  'adaptation_notes': 'If the patient explicitly says turning their head affects the discomfort, activate '
                      '`neck_shoulder.turning_detail` and ask “What do you notice when you turn your head?” '
                      'If they report a shoulder-specific task, activate `neck_shoulder.task_detail` and ask '
                      '“What happens during that task?” Activate these follow-ups only when the target '
                      'detail is still missing. If the patient explicitly describes two unrelated concerns, '
                      'retain two concern records and ask which they want to prepare first.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-04',
  'title': 'Hand, wrist or arm discomfort',
  'category': 'Symptoms',
  'description': 'Activate after an explicit report or selection of hand, wrist or arm discomfort.',
  'questions': [{'key': 'upper_limb.pain_site',
                 'label': 'Upper limb · pain site',
                 'question': 'Where do you feel the discomfort?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice it?'},
                {'key': 'upper_limb.character',
                 'label': 'Upper limb · character',
                 'question': 'What does the discomfort feel like?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do you notice it?'},
                {'key': 'upper_limb.task_context',
                 'label': 'Upper limb · task context',
                 'question': 'Which task makes the discomfort most noticeable?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'What have you had to change in your daily activities?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for it?'}],
  'adaptation_notes': 'If the patient explicitly reports an injury, activate `upper_limb.reported_event` and '
                      'ask “What happened when you injured the area?” If they describe a particular grip or '
                      'hand task, activate `upper_limb.task_detail` and ask “What happens when you do that '
                      'task?” If they mention using a support or brace, capture the item and their reported '
                      'experience through `previous_actions`, without endorsing it or evaluating '
                      'effectiveness clinically.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-05',
  'title': 'Recurring headaches',
  'category': 'Symptoms',
  'description': 'Activate when the patient explicitly reports recurring headaches or chooses this topic.',
  'questions': [{'key': 'headache.pain_site',
                 'label': 'Headache · pain site',
                 'question': 'Where do you usually feel the headache?'},
                {'key': 'headache.character',
                 'label': 'Headache · character',
                 'question': 'What does the headache feel like?'},
                {'key': 'headache.episode_length',
                 'label': 'Headache · episode length',
                 'question': 'How long does a usual headache last?'},
                {'key': 'headache.observed_context',
                 'label': 'Headache · observed context',
                 'question': 'What patterns have you noticed around your headaches?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How do the headaches affect your usual activities?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried when a headache occurs?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss about the headaches?'}],
  'adaptation_notes': 'If the patient reports keeping a diary, activate `headache.diary_details` and ask '
                      '“Which diary details would you like included?” If they explicitly report another '
                      'experience during episodes, activate `headache.reported_association` and ask “How '
                      'does that experience relate in time to the headache?” If medicine use is reported, '
                      'resolve missing details within shared `current_medications`; do not calculate an '
                      'overuse classification.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-06',
  'title': 'Recurring dizziness discussed at a planned appointment',
  'category': 'Symptoms',
  'description': 'Activate from explicitly reported recurring dizziness within the established '
                 'planned-consultation context.',
  'questions': [{'key': 'dizziness.description',
                 'label': 'Dizziness · description',
                 'question': 'What does “dizzy” feel like to you?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice these episodes?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do the episodes happen?'},
                {'key': 'dizziness.episode_length',
                 'label': 'Dizziness · episode length',
                 'question': 'How long does an episode usually last?'},
                {'key': 'dizziness.episode_context',
                 'label': 'Dizziness · episode context',
                 'question': 'What are you usually doing when an episode happens?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How do the episodes affect your usual activities?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like your clinician to understand?'}],
  'adaptation_notes': 'If the patient explicitly links episodes to changing position, activate '
                      '`dizziness.position_detail` and ask “Which change of position have you noticed before '
                      'an episode?” If they report a recent medicine change, capture the reported change '
                      'within `current_medications`, preserving temporal association without attribution. '
                      "The backend must run the document's global safety interrupt before selecting any "
                      'further target.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-07',
  'title': 'Persistent tiredness',
  'category': 'Symptoms',
  'description': 'Activate when the patient explicitly reports persistent tiredness or chooses this concern.',
  'questions': [{'key': 'fatigue.description',
                 'label': 'Fatigue · description',
                 'question': 'What does feeling tired mean for you?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has the tiredness changed since it began?'},
                {'key': 'fatigue.daily_pattern',
                 'label': 'Fatigue · daily pattern',
                 'question': 'When during the day do you notice it most?'},
                {'key': 'fatigue.rest_experience',
                 'label': 'Fatigue · rest experience',
                 'question': 'What do you notice after resting?'},
                {'key': 'fatigue.sleep_description',
                 'label': 'Fatigue · sleep description',
                 'question': 'How would you describe your sleep recently?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'Which usual activity has become hardest to manage?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss about the tiredness?'}],
  'adaptation_notes': 'If the patient explicitly reports difficulty sleeping and chooses to explore it, '
                      'offer WF-08 and reuse existing sleep facts. If they report an illness around onset, '
                      'activate `fatigue.reported_illness_timeline` and ask “When did that illness occur '
                      'compared with the tiredness?” If they describe a changed work or caring schedule, '
                      'activate `fatigue.routine_change` and ask “What changed in your routine?” None of '
                      'these associations establishes a cause.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-08',
  'title': 'Sleep difficulties',
  'category': 'Symptoms',
  'description': 'Activate after an explicit sleep concern or patient selection.',
  'questions': [{'key': 'sleep.main_difficulty',
                 'label': 'Sleep · main difficulty',
                 'question': 'What part of sleeping is most difficult for you?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How many nights are affected in a usual week?'},
                {'key': 'sleep.usual_bedtime',
                 'label': 'Sleep · usual bedtime',
                 'question': 'What time do you usually go to bed?'},
                {'key': 'sleep.usual_wake_time',
                 'label': 'Sleep · usual wake time',
                 'question': 'What time do you usually get up?'},
                {'key': 'sleep.observed_context',
                 'label': 'Sleep · observed context',
                 'question': 'What patterns have you noticed around the difficult nights?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does the sleep difficulty affect your day?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for your sleep?'}],
  'adaptation_notes': 'If night waking is reported, activate `sleep.waking_duration` and ask “About how long '
                      'are you awake during those episodes?” If the patient reports shift work, activate '
                      '`sleep.shift_pattern` and ask “How does your work schedule vary?” If they volunteer '
                      'an observation made by someone else, activate `sleep.reported_observation` and ask '
                      '“What did that person notice?” Attribute the observation to its source.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-09',
  'title': 'Persistent or recurring cough',
  'category': 'Symptoms',
  'description': 'Activate from an explicitly described persistent or recurring cough or patient selection.',
  'questions': [{'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this cough?'},
                {'key': 'cough.description',
                 'label': 'Cough · description',
                 'question': 'How would you describe the cough?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often are you coughing?'},
                {'key': 'cough.daily_pattern',
                 'label': 'Cough · daily pattern',
                 'question': 'When during the day is the cough most noticeable?'},
                {'key': 'cough.observed_context',
                 'label': 'Cough · observed context',
                 'question': 'What situations seem to bring on the cough?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'What does the cough interrupt in your daily life?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for the cough?'}],
  'adaptation_notes': 'If the patient explicitly reports bringing up mucus, activate `cough.reported_mucus` '
                      'and ask “How would you describe the mucus you have noticed?” If they report exposure '
                      'to smoke, vaping or workplace dust, activate `cough.reported_exposure` and ask “What '
                      'exposure would you like recorded for your clinician?” If sleep interruption is '
                      'reported, capture it in `functional_impact`; do not automatically start a separate '
                      'sleep workflow. The global interrupt always precedes further questioning.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-10',
  'title': 'Nasal symptoms and patient-reported allergy concerns',
  'category': 'Symptoms',
  'description': 'Activate for explicitly reported nasal symptoms or a patient-selected allergy concern.',
  'questions': [{'key': 'nasal.main_description',
                 'label': 'Nasal · main description',
                 'question': 'What nasal symptoms are bothering you most?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this problem?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do the symptoms occur?'},
                {'key': 'nasal.time_pattern',
                 'label': 'Nasal · time pattern',
                 'question': 'What pattern have you noticed over time?'},
                {'key': 'nasal.environment_context',
                 'label': 'Nasal · environment context',
                 'question': 'Where do you most often notice the symptoms?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How do the symptoms affect your usual activities?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for them?'}],
  'adaptation_notes': 'If the patient explicitly reports a seasonal pattern, activate `nasal.season_detail` '
                      'and ask “Which times of year have you noticed this?” If they report a particular '
                      'place or exposure, activate `nasal.exposure_detail` and ask “What do you notice when '
                      'you are in that situation?” If they report a previously diagnosed allergy, use shared '
                      '`allergies` and `relevant_history` to record the reported diagnosis and source; do '
                      'not reinterpret a suspected trigger as confirmation.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-11',
  'title': 'Throat discomfort or hoarseness',
  'category': 'Symptoms',
  'description': 'Activate after explicit reporting or selection of throat discomfort or a voice concern.',
  'questions': [{'key': 'throat_focus',
                 'label': 'Throat focus',
                 'question': 'Which throat or voice concern would you most like to describe?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has it changed since it first started?'},
                {'key': 'throat_sensation',
                 'label': 'Throat sensation',
                 'question': 'How would you describe the feeling in your throat?'},
                {'key': 'voice_change_description',
                 'label': 'Voice change description',
                 'question': 'How does your voice sound different from usual?'},
                {'key': 'voice_use_context',
                 'label': 'Voice use context',
                 'question': 'During which speaking activities do you notice the change?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does this affect your everyday activities?'}],
  'adaptation_notes': '- Explicit voice change activates `voice_change_description` and `voice_use_context`; '
                      'discomfort alone does not.\n'
                      '- Explicit throat discomfort activates `throat_sensation`. If both concerns are '
                      "reported, retain both and use the patient's stated priority to order the applicable "
                      'targets.\n'
                      '- An explicit account of an earlier appointment links to the existing '
                      '`previous_consultation` record; it does not start a second medical-history interview.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-12',
  'title': 'Ear discomfort or hearing concerns',
  'category': 'Symptoms',
  'description': 'Activate after an explicit ear-discomfort or hearing-concern report.',
  'questions': [{'key': 'ear_focus',
                 'label': 'Ear focus',
                 'question': 'Which ear or hearing concern would you most like to describe?'},
                {'key': 'ear_side', 'label': 'Ear side', 'question': 'Which ear seems affected?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has it changed over time?'},
                {'key': 'ear_discomfort_description',
                 'label': 'Ear discomfort description',
                 'question': 'How would you describe the discomfort?'},
                {'key': 'hearing_context',
                 'label': 'Hearing context',
                 'question': 'In which situations is hearing most difficult for you?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does this affect your everyday life?'}],
  'adaptation_notes': '- Reported discomfort activates `ear_discomfort_description`; a hearing concern '
                      'activates `hearing_context`. Both may apply when both are explicitly reported.\n'
                      '- “Both ears” completes `ear_side`; “I cannot tell” stores unknown. Neither response '
                      'triggers a comparison test or a request to test each ear.\n'
                      '- An explicitly reported existing hearing aid is linked to `relevant_history`; an '
                      'earlier hearing assessment is linked to `previous_tests`. Do not infer a diagnosis '
                      'from either fact.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-13',
  'title': 'Eye irritation or dryness',
  'category': 'Symptoms',
  'description': 'Activate after explicit reporting or selection of irritation or dryness.',
  'questions': [{'key': 'eye_side', 'label': 'Eye side', 'question': 'Which eye is affected?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this?'},
                {'key': 'eye_sensation',
                 'label': 'Eye sensation',
                 'question': 'How would you describe the feeling in your eye?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often does it happen?'},
                {'key': 'eye_context',
                 'label': 'Eye context',
                 'question': 'In what situations do you notice it most?'},
                {'key': 'eye_lens_context',
                 'label': 'Eye lens context',
                 'question': 'How does it vary while you are wearing your contact lenses?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does this affect your everyday activities?'}],
  'adaptation_notes': '- `eye_lens_context` applies only after explicit contact-lens use; eyesight concerns '
                      'or glasses do not activate it.\n'
                      '- A context already supplied in the opening completes `eye_context`; the agent does '
                      'not ask the patient to repeat “after computer work.”\n'
                      '- A reported eye product is linked to the shared `current_medications` or '
                      "`previous_actions` record according to the patient's account. Product use never "
                      'triggers instructions to continue, stop, or substitute it.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-14',
  'title': 'Recurrent abdominal discomfort',
  'category': 'Symptoms',
  'description': 'Activate for an explicitly reported recurring abdominal concern.',
  'questions': [{'key': 'abdominal_location',
                 'label': 'Abdominal location',
                 'question': 'Where in your tummy do you notice the discomfort?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice these episodes?'},
                {'key': 'abdominal_quality',
                 'label': 'Abdominal quality',
                 'question': 'How would you describe the discomfort?'},
                {'key': 'episode_length',
                 'label': 'Episode length',
                 'question': 'About how long does an episode last?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do the episodes happen?'},
                {'key': 'abdominal_context',
                 'label': 'Abdominal context',
                 'question': 'What seems to happen around the time an episode starts?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does an episode affect your everyday activities?'}],
  'adaptation_notes': '- Explicit intermittent episodes activate episode duration and frequency. If the '
                      'patient describes continuous symptoms, store that account and skip episode-specific '
                      'questions.\n'
                      '- A reported bowel-pattern concern may activate WF-16 or WF-17 only if the patient '
                      'chooses to include it. Reuse existing onset and context information for the same '
                      'concern.\n'
                      '- Include menstrual associations only when volunteered or selected. Sensitive detail '
                      'requires shared permission; abdominal location alone never opens a '
                      'reproductive-history branch.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-15',
  'title': 'Heartburn or indigestion concerns',
  'category': 'Symptoms',
  'description': 'Activate after explicit reporting or selection of heartburn or indigestion.',
  'questions': [{'key': 'indigestion_description',
                 'label': 'Indigestion description',
                 'question': 'What does “indigestion” or “heartburn” mean for you?'},
                {'key': 'indigestion_location',
                 'label': 'Indigestion location',
                 'question': 'Where do you notice the sensation?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice it?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often does it happen?'},
                {'key': 'indigestion_context',
                 'label': 'Indigestion context',
                 'question': 'In what situations do you notice it most?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for this concern?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does it affect your everyday activities?'}],
  'adaptation_notes': "- Render the patient's own reported term in the first question; do not ask them to "
                      'select a diagnostic label. If their opening already explains the sensation, skip this '
                      'target.\n'
                      '- An explicit meal, posture, or time-of-day association fills `indigestion_context`. '
                      'A response of “no pattern” completes it without further trigger hunting.\n'
                      '- A reported product fills `previous_actions` and links to `current_medications` if '
                      'currently used. Do not repeat the inventory or suggest changing use.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-16',
  'title': 'Constipation',
  'category': 'Symptoms',
  'description': 'Activate after an explicit constipation concern or selected bowel-movement difficulty.',
  'questions': [{'key': 'bowel_baseline',
                 'label': 'Bowel baseline',
                 'question': 'What was your usual bowel pattern before this change?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice the change?'},
                {'key': 'bowel_frequency',
                 'label': 'Bowel frequency',
                 'question': 'About how often are you having a bowel movement now?'},
                {'key': 'stool_description',
                 'label': 'Stool description',
                 'question': 'How would you describe your stools?'},
                {'key': 'bowel_difficulty',
                 'label': 'Bowel difficulty',
                 'question': 'What feels difficult about having a bowel movement?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for this concern?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How is this affecting your daily routine?'}],
  'adaptation_notes': '- A before-and-after account fills `bowel_baseline` and `bowel_frequency`. If the '
                      'pattern is explicitly longstanding and unchanged, record it without inventing a '
                      'recent change.\n'
                      '- A volunteered new medicine or altered routine is recorded with its timing. It does '
                      'not establish causation or activate advice about medicines, food, or fluids.\n'
                      '- If the patient explicitly reports alternating loose stools and wants to discuss '
                      'them, link WF-17 while preserving the shared bowel baseline. The patient chooses the '
                      'agenda order.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-17',
  'title': 'Recurrent loose stools',
  'category': 'Symptoms',
  'description': 'Activate for an explicitly reported recurring loose-stool concern.',
  'questions': [{'key': 'bowel_baseline',
                 'label': 'Bowel baseline',
                 'question': 'What is your usual bowel pattern between episodes?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did these episodes first start?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often do the episodes occur?'},
                {'key': 'episode_length',
                 'label': 'Episode length',
                 'question': 'About how long does an episode last?'},
                {'key': 'stool_description',
                 'label': 'Stool description',
                 'question': 'How would you describe your stools during an episode?'},
                {'key': 'loose_stool_context',
                 'label': 'Loose stool context',
                 'question': 'What tends to be happening around the time an episode occurs?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How do the episodes affect your daily activities?'}],
  'adaptation_notes': '- Explicit continuous symptoms replace episode applicability with the shared '
                      'continuous-course representation. Do not retain a false symptom-free interval.\n'
                      '- Reported travel, food, or medicine timing fills `loose_stool_context` as patient '
                      'observations. A negative or unknown pattern closes the target without an exposure '
                      'checklist.\n'
                      '- An explicitly reported earlier assessment links to `previous_consultation` or '
                      '`previous_tests`. An existing clinician diagnosis may be recorded in '
                      '`relevant_history`; the workflow never creates one.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-18',
  'title': 'Urinary symptoms or bladder-control concerns',
  'category': 'Symptoms',
  'description': 'Activate after explicit selection or reporting of urinary or bladder-control concerns.',
  'questions': [{'key': 'urinary_focus',
                 'label': 'Urinary focus',
                 'question': 'Which change in urination would you most like to discuss?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice this change?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has it changed over time?'},
                {'key': 'urination_pattern',
                 'label': 'Urination pattern',
                 'question': 'What is your current pattern of passing urine?'},
                {'key': 'leakage_context',
                 'label': 'Leakage context',
                 'question': 'In what situations does leakage happen?'},
                {'key': 'urinary_discomfort_description',
                 'label': 'Urinary discomfort description',
                 'question': 'How would you describe the discomfort when passing urine?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does this affect your daily activities?'}],
  'adaptation_notes': '- Explicit leakage activates `leakage_context`; explicit discomfort activates '
                      '`urinary_discomfort_description`. “When I laugh” already completes the former in the '
                      'example.\n'
                      '- A reported daytime or night-time pattern fills `urination_pattern`; measured '
                      'volumes or a new bladder diary are not required.\n'
                      '- Sensitive reproductive or sexual information is explored only when the patient '
                      'explicitly connects it to their concern and grants permission. Demographic data alone '
                      'never opens that branch.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-19',
  'title': 'Menstrual pattern or period-related concerns',
  'category': 'Symptoms',
  'description': 'Activate after explicit selection of a menstrual concern or a reported period association.',
  'questions': [{'key': 'menstrual_focus',
                 'label': 'Menstrual focus',
                 'question': 'Which change in your periods would you most like to discuss?'},
                {'key': 'menstrual_baseline',
                 'label': 'Menstrual baseline',
                 'question': 'What was your usual period pattern before this change?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice the change?'},
                {'key': 'menstrual_current_pattern',
                 'label': 'Menstrual current pattern',
                 'question': 'What is your period pattern like now?'},
                {'key': 'menstrual_flow_description',
                 'label': 'Menstrual flow description',
                 'question': 'How would you describe the bleeding compared with your usual periods?'},
                {'key': 'menstrual_symptom_timing',
                 'label': 'Menstrual symptom timing',
                 'question': 'When in relation to your period does the symptom occur?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does this affect your everyday life?'}],
  'adaptation_notes': '- A reported change in bleeding activates `menstrual_flow_description`. A reported '
                      'period-associated symptom activates `menstrual_symptom_timing`; do not assume pain or '
                      'mood changes.\n'
                      '- Supplied dates or an existing cycle record fill pattern targets. Accept approximate '
                      'intervals without calculating a diagnostic category.\n'
                      '- Retain explicit contraception or pregnancy concerns only with permission. Do not '
                      'initiate a sexual-history interview or interpret a missed period.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-20',
  'title': 'Localised rash or itching',
  'category': 'Symptoms',
  'description': 'Activate after an explicit localised-rash or itching report.',
  'questions': [{'key': 'skin_location', 'label': 'Skin location', 'question': 'Where is the affected area?'},
                {'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice it?'},
                {'key': 'skin_appearance',
                 'label': 'Skin appearance',
                 'question': 'What changes can you see in the skin?'},
                {'key': 'skin_sensation', 'label': 'Skin sensation', 'question': 'How does the area feel?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has the affected area changed over time?'},
                {'key': 'skin_context',
                 'label': 'Skin context',
                 'question': 'What do you notice happening around the time it appears?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How does it affect your usual activities?'}],
  'adaptation_notes': '- A visible skin change makes `skin_appearance` applicable. If the patient explicitly '
                      'reports itching with no visible change, record that fact and skip appearance '
                      'elaboration.\n'
                      '- A volunteered product, jewellery, clothing, or work exposure is stored in '
                      '`skin_context` as a temporal association. It does not automatically become an allergy '
                      'or a proven cause.\n'
                      '- A reported product links to `previous_actions` and, if currently used, '
                      '`current_medications`. Do not advise applying, removing, or replacing it.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-21',
  'title': 'Acne or ongoing skin-treatment review',
  'category': 'Symptoms',
  'description': 'The patient wants to prepare for an appointment about ongoing spots or an existing '
                 'skin-care approach.',
  'questions': [{'key': 'symptom_duration',
                 'label': 'Symptom duration',
                 'question': 'How long has this skin concern been present?'},
                {'key': 'skin_sites', 'label': 'Skin sites', 'question': 'Which areas of skin are affected?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has the skin concern changed over time?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried for this concern?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How, if at all, is this affecting your daily life?'},
                {'key': 'patient_worry',
                 'label': 'Patient worry',
                 'question': 'Is there anything about it that worries you?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss at the appointment?'}],
  'adaptation_notes': "1. If a previous consultation is mentioned, capture the clinician's explanation as "
                      'patient-reported; otherwise leave diagnosis unspecified.\n'
                      "2. If an existing approach is mentioned, capture the patient's observed response; "
                      'otherwise skip response questions.\n'
                      "3. If a product name is unknown, retain the patient's description and mark the name "
                      'unknown.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-22',
  'title': 'Stress or anxiety-related concerns',
  'category': 'Wellbeing',
  'description': 'The patient voluntarily seeks preparation for a non-emergency conversation about stress, '
                 'worry or anxiety-related experiences.',
  'questions': [{'key': 'symptom_onset',
                 'label': 'Symptom onset',
                 'question': 'When did you first notice these feelings?'},
                {'key': 'symptom_frequency',
                 'label': 'Symptom frequency',
                 'question': 'How often have these feelings been occurring?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How have these feelings changed over time?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How, if at all, have these feelings affected daily life?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What have you already tried to help yourself?'},
                {'key': 'previous_consultation.exists',
                 'label': 'Previous consultation · exists',
                 'question': 'Have you discussed this concern with a health professional before?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like help discussing with your GP?'}],
  'adaptation_notes': '1. If the patient identifies a situation connected with the feelings, retain that '
                      'connection as their account; otherwise do not infer a cause.\n'
                      '2. If previous professional support is reported, ask what they want included about '
                      'it; otherwise skip that detail.\n'
                      '3. If a topic is declined, mark it skipped and continue without rephrasing it to '
                      'obtain an answer.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-23',
  'title': 'Low mood or mental-health follow-up',
  'category': 'Wellbeing',
  'description': 'The patient voluntarily prepares to discuss low mood or follow-up care.',
  'questions': [{'key': 'symptom_duration',
                 'label': 'Symptom duration',
                 'question': 'How long has this period of low mood lasted?'},
                {'key': 'symptom_course',
                 'label': 'Symptom course',
                 'question': 'How has your mood changed recently?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'How, if at all, has your mood affected everyday activities?'},
                {'key': 'previous_consultation.reported_care',
                 'label': 'Previous consultation · reported care',
                 'question': 'What previous mental-health care would you like mentioned?'},
                {'key': 'previous_actions',
                 'label': 'Previous actions',
                 'question': 'What support have you already been using?'},
                {'key': 'patient_worry',
                 'label': 'Patient worry',
                 'question': 'What concern would you especially like the clinician to understand?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would make this appointment useful for you?'}],
  'adaptation_notes': '1. If a current mood concern is reported, record its timeline. For a confirmed '
                      'review-only visit without a symptom concern, set duration and severity to '
                      '`NOT_APPLICABLE`.\n'
                      '2. If an existing care plan is mentioned, record only voluntarily reported details; '
                      'otherwise leave the plan unspecified.\n'
                      '3. If medication concerns are volunteered, attach their account to the shared '
                      'medication record without recommending changes or assigning causation.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-24',
  'title': 'Established high blood pressure review',
  'category': 'Planned reviews',
  'description': 'The patient reports a clinician-established diagnosis and a planned review.',
  'questions': [{'key': 'relevant_history.blood_pressure_explanation',
                 'label': 'Relevant history · blood pressure explanation',
                 'question': 'What has a clinician told you about your blood pressure?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss at this review?'},
                {'key': 'previous_consultation.date',
                 'label': 'Previous consultation · date',
                 'question': 'When was your last blood pressure review?'},
                {'key': 'bp_readings',
                 'label': 'Bp readings',
                 'question': 'What existing blood pressure readings would you like included?'},
                {'key': 'current_medications',
                 'label': 'Current medications',
                 'question': 'Which medicines are you currently taking?'},
                {'key': 'medication_experience',
                 'label': 'Medication experience',
                 'question': 'What would you like the clinician to know about taking these medicines?'},
                {'key': 'review_changes',
                 'label': 'Review changes',
                 'question': 'What changes, if any, would you like mentioned at this review?'}],
  'adaptation_notes': '- If an existing reading is supplied, retain its value. Ask separately for missing '
                      'provenance: “Where did that reading come from?”, “What unit is shown?” and “When was '
                      'it taken?” Preserve the stated date/time or its uncertainty.\n'
                      '- If no readings are available, mark them unavailable and continue. Do not request a '
                      'new measurement, infer units, calculate targets or interpret values.\n'
                      '- For a confirmed review-only visit without a symptom concern, set `symptom_duration` '
                      'and `severity` to `NOT_APPLICABLE`. Offer a separate module for another volunteered '
                      'concern.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-25',
  'title': 'Established diabetes review',
  'category': 'Planned reviews',
  'description': 'The patient reports clinician-diagnosed diabetes and a planned follow-up.',
  'questions': [{'key': 'relevant_history.diabetes_explanation',
                 'label': 'Relevant history · diabetes explanation',
                 'question': 'What has your clinician told you about your diabetes?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like to discuss at this review?'},
                {'key': 'previous_tests',
                 'label': 'Previous tests',
                 'question': 'What existing diabetes-related test results would you like included?'},
                {'key': 'glucose_readings',
                 'label': 'Glucose readings',
                 'question': 'What existing glucose records would you like included?'},
                {'key': 'current_medications',
                 'label': 'Current medications',
                 'question': 'Which medicines are you currently taking?'},
                {'key': 'diabetes_care_experience',
                 'label': 'Diabetes care experience',
                 'question': 'What part of your usual diabetes care would you like to discuss?'},
                {'key': 'review_changes',
                 'label': 'Review changes',
                 'question': 'What changes, if any, would you like mentioned at this review?'}],
  'adaptation_notes': '- For supplied readings, use fixed single-field follow-ups for missing source, '
                      'displayed unit and date/time. Distinguish patient-entered recollection from an '
                      'existing device record or report; retain any patient-reported meal context without '
                      'inventing it.\n'
                      '- When records are unavailable, accept that state. Do not ask the patient to measure '
                      'glucose, estimate missing values or interpret a target range.\n'
                      '- For a confirmed review-only visit without a symptom concern, set `symptom_duration` '
                      'and `severity` to `NOT_APPLICABLE`. Offer separate preparation for another concern.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-26',
  'title': 'Established asthma review',
  'category': 'Planned reviews',
  'description': 'The patient reports clinician-diagnosed asthma and a planned review.',
  'questions': [{'key': 'review_period',
                 'label': 'Review period',
                 'question': 'What period would you like this update to cover?'},
                {'key': 'asthma.review_experience',
                 'label': 'Asthma · review experience',
                 'question': 'What would you like to mention about your breathing over that period?'},
                {'key': 'sleep_impact',
                 'label': 'Sleep impact',
                 'question': 'Have breathing symptoms affected your sleep during that period?'},
                {'key': 'functional_impact',
                 'label': 'Functional impact',
                 'question': 'Have breathing symptoms affected your usual activities during that period?'},
                {'key': 'current_medications',
                 'label': 'Current medications',
                 'question': 'Which inhalers or other asthma medicines are you using?'},
                {'key': 'medication_experience',
                 'label': 'Medication experience',
                 'question': 'What would you like the clinician to know about using your inhalers?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What is your main question for this asthma review?'}],
  'adaptation_notes': '- For a confirmed review-only visit without a symptom concern, preserve the stated '
                      'period and set `symptom_duration` and `severity` to `NOT_APPLICABLE`.\n'
                      '- Reported breathing concerns activate the relevant frequency, sleep-impact and '
                      'functional-impact targets. If episodes are reported, ask the missing '
                      '`symptom_frequency` target separately. If no symptom concern is reported, keep those '
                      'symptom-detail targets inapplicable. Do not score control or compare answers with '
                      'treatment thresholds. Inhaler-experience details activate only after inhaler use is '
                      'reported.\n'
                      '- If an existing action plan is mentioned, offer to record its reported date or '
                      'title. Do not interpret, activate, replace or modify its instructions.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-27',
  'title': 'Medication review or repeat-prescription discussion',
  'category': 'Planned reviews',
  'description': 'The patient plans a consultation about existing medicines or a repeat prescription.',
  'questions': [{'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you like to achieve in the medication discussion?'},
                {'key': 'medication_focus',
                 'label': 'Medication focus',
                 'question': 'Which medicine would you like to discuss first?'},
                {'key': 'medication_actual_use',
                 'label': 'Medication actual use',
                 'question': 'How are you currently taking this medicine?'},
                {'key': 'medication_experience',
                 'label': 'Medication experience',
                 'question': 'What would you like the clinician to know about your experience with it?'},
                {'key': 'medication_supply',
                 'label': 'Medication supply',
                 'question': 'How much of this medicine do you currently have?'},
                {'key': 'previous_consultation.reviewing_clinician',
                 'label': 'Previous consultation · reviewing clinician',
                 'question': 'Who last reviewed this medicine with you?'},
                {'key': 'clinician_questions',
                 'label': 'Clinician questions',
                 'question': 'What question would you like to ask about this medicine?'}],
  'adaptation_notes': '- For a confirmed prescription-only discussion, ask relevant supply information. '
                      'Symptom duration and severity are `NOT_APPLICABLE` unless a symptom concern is '
                      'raised.\n'
                      '- If the patient describes a problem they associate with a medicine, preserve that '
                      'association as their account. Ask when they noticed it, without labelling it a '
                      'confirmed adverse effect or advising a medication change.\n'
                      '- If several medicines need discussion, let the patient choose the order. Deduplicate '
                      'the global list and keep unreviewed items visibly marked “not explored”.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-28',
  'title': 'Existing test-results follow-up',
  'category': 'Planned reviews',
  'description': 'The patient reports completed tests and a planned results discussion, including when '
                 'results are unavailable.',
  'questions': [{'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you most like clarified at the results appointment?'},
                {'key': 'previous_tests.test_name',
                 'label': 'Previous tests · test name',
                 'question': 'Which completed test would you like to discuss?'},
                {'key': 'previous_tests.test_date',
                 'label': 'Previous tests · test date',
                 'question': 'When was that test done?'},
                {'key': 'previous_tests.ordering_clinician',
                 'label': 'Previous tests · ordering clinician',
                 'question': 'Who arranged the test?'},
                {'key': 'previous_tests.reason_given',
                 'label': 'Previous tests · reason given',
                 'question': 'What reason were you given for having the test?'},
                {'key': 'previous_tests.result_source',
                 'label': 'Previous tests · result source',
                 'question': 'What result information do you already have?'},
                {'key': 'patient_worry',
                 'label': 'Patient worry',
                 'question': 'Is there anything about the results that particularly concerns you?'}],
  'adaptation_notes': '- If the patient has a report, offer to record the exact passage they want discussed. '
                      'Keep its source and supplied date, values and units. Do not convert flags or '
                      'reference ranges into a diagnosis.\n'
                      '- If results are inaccessible or pending, record that state and continue with the '
                      "patient's questions. Never substitute an expected or “normal” result.\n"
                      '- Offer separate preparation for a volunteered symptom concern. For a confirmed '
                      'results-only agenda without a symptom concern, duration and severity are '
                      '`NOT_APPLICABLE`.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-29',
  'title': 'Planned preventive-health or screening discussion',
  'category': 'Planned reviews',
  'description': 'The patient plans a conversation about prevention, screening or a previously suggested '
                 'health check.',
  'questions': [{'key': 'prevention_topic',
                 'label': 'Prevention topic',
                 'question': 'Which preventive health topic would you like to discuss?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you like to understand by the end of the appointment?'},
                {'key': 'previous_consultation.reported_explanation',
                 'label': 'Previous consultation · reported explanation',
                 'question': 'What has a clinician already discussed with you about this topic?'},
                {'key': 'previous_tests',
                 'label': 'Previous tests',
                 'question': 'What previous checks related to this topic would you like included?'},
                {'key': 'relevant_history.family_history',
                 'label': 'Relevant history · family history',
                 'question': 'What family health history would you like the clinician to know?'},
                {'key': 'patient_worry',
                 'label': 'Patient worry',
                 'question': 'What concerns do you have about discussing this topic?'},
                {'key': 'clinician_questions',
                 'label': 'Clinician questions',
                 'question': 'What question would you most like to ask the clinician?'}],
  'adaptation_notes': '- If a check or invitation is mentioned, ask its known name or date separately when '
                      'useful. Mark unavailable records; do not calculate due dates.\n'
                      '- If the patient selects a particular topic, use only its approved history prompts. '
                      'Do not infer anatomy, pregnancy status, sexual history or screening eligibility from '
                      'name, age or gender.\n'
                      '- For a confirmed prevention-only discussion without a symptom concern, duration and '
                      'severity are `NOT_APPLICABLE`. Offer separate preparation for a volunteered symptom '
                      'concern.',
  'version': 'catalogue-1.0-integration-1'},
 {'id': 'WF-30',
  'title': 'Preparing an appointment with multiple concerns',
  'category': 'Your agenda',
  'description': 'The patient lists multiple concerns or requests agenda preparation.',
  'questions': [{'key': 'agenda_items',
                 'label': 'Agenda items',
                 'question': 'What would you like to discuss at this appointment?'},
                {'key': 'priority_concern',
                 'label': 'Priority concern',
                 'question': 'Which concern is most important for you to discuss?'},
                {'key': 'appointment_goal',
                 'label': 'Appointment goal',
                 'question': 'What would you like to achieve for that concern?'},
                {'key': 'preparation_focus',
                 'label': 'Preparation focus',
                 'question': 'Which concern would you like to prepare in more detail now?'},
                {'key': 'clinician_questions',
                 'label': 'Clinician questions',
                 'question': 'What questions would you like to take to the appointment?'},
                {'key': 'summary_review',
                 'label': 'Summary review',
                 'question': 'What would you like to change in this draft?'}],
  'adaptation_notes': "- After the patient chooses, run that concern's module with separately namespaced "
                      'symptom slots. Do not merge timelines or assume a shared cause.\n'
                      '- Collect medications, allergies and general history once; clarify concrete '
                      'contradictions or missing relevant details. Merge apparently duplicate concerns only '
                      'with patient confirmation.\n'
                      '- On finish or the shared question limit, retain every remaining concern labelled '
                      '“not explored”. Otherwise, offer the next concern in patient-chosen order. Never '
                      'silently omit it.',
  'version': 'catalogue-1.0-integration-1'}]
# Only these session-level keys may be shared between concerns.
SHARED_QUESTIONS = {
    'main_concern': 'What would you like to prepare for your appointment?',
    'current_medications': 'What medicines or supplements do you currently use?',
    'allergies': 'What allergies or past medicine reactions would you like recorded?',
    'relevant_history': 'What medical history would you like the clinician to know?',
    'patient_worry': 'What concerns you most about the appointment?',
    'appointment_goal': 'What would you most like to get from the appointment?',
    'clinician_questions': 'What would you like to ask the clinician?',
    'agenda_items': 'What would you like to discuss at this appointment?',
    'priority_concern': 'Which concern is most important for you to discuss?',
    'preparation_focus': 'Which concern would you like to prepare in more detail now?',
}
CORE_QUESTIONS = {
    'concern_description': 'What would you like the clinician to know about this concern?',
    'symptom_onset': 'When did you first notice this?',
    'symptom_course': 'How has it changed since you first noticed it?',
    'symptom_pattern': 'Is it present all the time, or does it come and go?',
    'symptom_frequency': 'How often does it happen?',
    'severity': 'How strong or troublesome does it feel to you?',
    'functional_impact': 'How does it affect your usual activities?',
    'previous_actions': 'What have you already tried for this concern?',
    'previous_actions.response': 'What did you notice after trying that approach?',
    'previous_consultation.exists': 'Have you discussed this concern with a healthcare professional before?',
    'previous_consultation.date': 'When did that consultation take place?',
    'previous_consultation.reviewing_clinician': 'Who did you discuss this concern with?',
    'previous_consultation.reported_explanation': 'What do you recall being told about this concern?',
    'previous_tests': 'What tests have already been done for this concern, if any?',
    'sensitive_permission': 'Would you like to include optional personal details about this topic? You can decline and still prepare your appointment.',
    'optional_personal_detail': 'What personal detail related to this concern would you like included?',
}
# Flags are extraction proposals, never clinical findings. Each activation needs a
# validated verbatim patient span; age, sex, diagnosis guesses and absence of a
# mention are never activation evidence.
SIGNALS = {
    'current_symptom': 'The patient explicitly reports a current symptom concern.',
    'episodes': 'The patient reports recurring or intermittent episodes, not continuous symptoms.',
    'injury': 'The patient explicitly reports an injury or onset event.',
    'spreading': 'The patient explicitly reports discomfort travelling or spreading.',
    'head_turning': 'The patient reports discomfort associated with turning their head.',
    'specific_task': 'The patient explicitly describes a specific grip, shoulder or hand task.',
    'diary': 'The patient explicitly reports an existing diary they want included.',
    'associated_experience': 'The patient volunteers another experience during headache episodes.',
    'position_change': 'The patient explicitly links dizzy episodes with a position change.',
    'illness': 'The patient reports an illness around the onset of tiredness.',
    'routine_change': 'The patient reports a changed work, caring or other routine.',
    'night_waking': 'The patient explicitly reports waking during the night.',
    'shift_work': 'The patient explicitly reports shift work.',
    'other_observer': 'The patient reports an observation made by another person.',
    'mucus': 'The patient explicitly reports bringing up mucus; a dry cough does not qualify.',
    'exposure': 'The patient explicitly reports an environmental exposure relevant to this concern.',
    'seasonal': 'The patient explicitly reports a seasonal pattern.',
    'voice_change': 'The patient explicitly reports a change in their voice.',
    'throat_discomfort': 'The patient explicitly reports throat discomfort.',
    'ear_discomfort': 'The patient explicitly reports ear discomfort.',
    'hearing_concern': 'The patient explicitly reports a hearing concern.',
    'contact_lenses': 'The patient explicitly reports wearing contact lenses, not glasses.',
    'leakage': 'The patient explicitly reports urine leakage.',
    'urinary_discomfort': 'The patient explicitly reports discomfort when passing urine.',
    'bleeding_change': 'The patient explicitly reports a change in menstrual bleeding.',
    'period_association': 'The patient explicitly connects a symptom with their period.',
    'visible_skin_change': 'The patient explicitly reports a visible skin change, not itching alone.',
    'previous_consultation': 'The patient explicitly reports a previous professional consultation for this concern.',
    'previous_tests': 'The patient explicitly reports completed tests for this concern.',
    'previous_actions': 'The patient explicitly reports an action or approach already tried.',
    'medication_use': 'The patient explicitly reports current medicine, supplement or inhaler use.',
    'prescription_goal': 'The patient explicitly requests a repeat-prescription or supply discussion.',
    'medication_problem': 'The patient explicitly reports a problem they associate with a medicine.',
    'records_available': 'The patient explicitly reports available existing readings or records.',
    'report_available': 'The patient explicitly reports an available test report.',
    'breathing_concern': 'The patient explicitly reports breathing symptoms during the review period.',
    'action_plan': 'The patient explicitly reports an existing asthma action plan.',
    'invitation': 'The patient explicitly reports a screening invitation or an existing check.',
    'sensitive_connection': 'The patient explicitly connects optional sexual, reproductive, or other personal detail to this concern.',
    'sensitive_permission': 'The patient explicitly agrees to include optional personal detail for this topic.',
}

# Extra fields (key, question, activation signal), in catalogue order.
EXTRAS = {
    'WF-01': [('leg.reported_event', 'What happened when you injured your leg?', 'injury'), ('leg.pain_spread', 'Where does the pain travel?', 'spreading')],
    'WF-02': [('back.reported_event', 'What happened around the time the discomfort began?', 'injury'), ('back.pain_spread', 'Where does it spread?', 'spreading')],
    'WF-03': [('neck_shoulder.turning_detail', 'What do you notice when you turn your head?', 'head_turning'), ('neck_shoulder.task_detail', 'What happens during that task?', 'specific_task')],
    'WF-04': [('upper_limb.reported_event', 'What happened when you injured the area?', 'injury'), ('upper_limb.task_detail', 'What happens when you do that task?', 'specific_task')],
    'WF-05': [('headache.diary_details', 'Which diary details would you like included?', 'diary'), ('headache.reported_association', 'How does that experience relate in time to the headache?', 'associated_experience')],
    'WF-06': [('dizziness.position_detail', 'Which change of position have you noticed before an episode?', 'position_change')],
    'WF-07': [('fatigue.reported_illness_timeline', 'When did that illness occur compared with the tiredness?', 'illness'), ('fatigue.routine_change', 'What changed in your routine?', 'routine_change')],
    'WF-08': [('sleep.waking_duration', 'About how long are you awake during those episodes?', 'night_waking'), ('sleep.shift_pattern', 'How does your work schedule vary?', 'shift_work'), ('sleep.reported_observation', 'What did that person notice?', 'other_observer')],
    'WF-09': [('cough.reported_mucus', 'How would you describe the mucus you have noticed?', 'mucus'), ('cough.reported_exposure', 'What exposure would you like recorded for your clinician?', 'exposure')],
    'WF-10': [('nasal.season_detail', 'Which times of year have you noticed this?', 'seasonal'), ('nasal.exposure_detail', 'What do you notice when you are in that situation?', 'exposure')],
    'WF-21': [('skin_treatment.response', 'What have you noticed since using that approach?', 'previous_actions')],
    'WF-22': [('previous_consultation.reported_support', 'What would you like included about previous professional support?', 'previous_consultation')],
    'WF-23': [('existing_care_plan', 'What voluntarily shared details of your existing care plan would you like included?', 'action_plan')],
    'WF-24': [('bp_readings.source', 'Where did that reading come from?', 'records_available'), ('bp_readings.unit', 'What unit is shown?', 'records_available'), ('bp_readings.date', 'When was it taken?', 'records_available')],
    'WF-25': [('glucose_readings.source', 'Where did that reading come from?', 'records_available'), ('glucose_readings.unit', 'What unit is shown?', 'records_available'), ('glucose_readings.date', 'When was it taken?', 'records_available')],
    'WF-26': [('asthma.action_plan', 'What date or title is shown on your existing action plan?', 'action_plan')],
    'WF-27': [('medication_problem.onset', 'When did you first notice the problem you associate with this medicine?', 'medication_problem')],
    'WF-28': [('previous_tests.report_passage', 'Which exact passage from your existing report would you like to discuss?', 'report_available')],
    'WF-29': [('prevention_invitation.name', 'What is the known name of that check or invitation?', 'invitation'), ('prevention_invitation.date', 'What date is shown on that check or invitation?', 'invitation')],
}
CONDITIONS = {
    'symptom_frequency': 'episodes', 'episode_length': 'episodes',
    'headache.episode_length': 'episodes', 'dizziness.episode_length': 'episodes',
    'throat_sensation': 'throat_discomfort', 'voice_change_description': 'voice_change',
    'voice_use_context': 'voice_change', 'ear_discomfort_description': 'ear_discomfort',
    'hearing_context': 'hearing_concern', 'eye_lens_context': 'contact_lenses',
    'leakage_context': 'leakage', 'urinary_discomfort_description': 'urinary_discomfort',
    'menstrual_flow_description': 'bleeding_change', 'menstrual_symptom_timing': 'period_association',
    'skin_appearance': 'visible_skin_change', 'previous_actions.response': 'previous_actions',
    'medication_experience': 'medication_use', 'medication_actual_use': 'medication_use',
    'medication_supply': 'prescription_goal', 'previous_consultation.reported_care': 'previous_consultation',
}
SYMPTOM_FIELDS = {'symptom_onset', 'symptom_duration', 'symptom_course', 'symptom_pattern', 'severity', 'functional_impact'}


def get_workflow(workflow_id: str) -> dict | None:
    return next((w for w in WORKFLOWS if w['id'] == workflow_id), None)


def question_definitions(workflow_id: str) -> list[dict]:
    """Fully expanded leaf schema; session keys are filtered by the engine."""
    workflow = get_workflow(workflow_id)
    rows = list(workflow['questions']) if workflow else []
    keys = {q['key'] for q in rows}
    for key, question in CORE_QUESTIONS.items():
        if key not in keys:
            rows.append({'key': key, 'label': key.replace('.', ' · ').replace('_', ' ').capitalize(), 'question': question})
    for key, question, signal in EXTRAS.get(workflow_id, []):
        if key not in {q['key'] for q in rows}:
            rows.append({'key': key, 'label': key.replace('.', ' · ').replace('_', ' ').capitalize(), 'question': question, 'condition': signal})
    return rows

# Public workflow responses expose full schemas as well as source question banks.
for _workflow in WORKFLOWS:
    _workflow['slot_definitions'] = question_definitions(_workflow['id'])
    _workflow['shared_modules'] = ['medicines_and_allergies', 'relevant_background', 'patient_agenda']
    _workflow['clinical_validation'] = 'Proposed preparation templates; clinical review is pending.'
