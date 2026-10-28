"""Patient-reported symptom-history coverage, not a clinical score.

OLDCARTS uses R for relieving factors here; radiation is recorded separately.
The map reuses topic fields, preserves unknown/refused states, and never treats
an unasked question or an unselected suggestion as a negative finding.
"""
from __future__ import annotations

DIMENSIONS = (
    ('O', 'Onset'), ('L', 'Location'), ('D', 'Duration'),
    ('C', 'Character'), ('A', 'Aggravating factors'),
    ('R', 'Relieving factors'), ('T', 'Timing'), ('S', 'Severity'),
)

LOCATIONS = {
    'WF-01': 'leg.pain_site', 'WF-02': 'back.pain_site',
    'WF-03': 'neck_shoulder.main_site', 'WF-04': 'upper_limb.pain_site',
    'WF-05': 'headache.pain_site', 'WF-12': 'ear_side', 'WF-13': 'eye_side',
    'WF-14': 'abdominal_location', 'WF-15': 'indigestion_location',
    'WF-20': 'skin_location', 'WF-21': 'skin_sites',
}
CHARACTERS = {
    'WF-01': ('leg.pain_character',), 'WF-02': ('back.pain_character',),
    'WF-03': ('neck_shoulder.character',), 'WF-04': ('upper_limb.character',),
    'WF-05': ('headache.character',), 'WF-06': ('dizziness.description',),
    'WF-07': ('fatigue.description',), 'WF-08': ('sleep.main_difficulty',),
    'WF-09': ('cough.description',), 'WF-10': ('nasal.main_description',),
    'WF-11': ('throat_focus', 'throat_sensation', 'voice_change_description'),
    'WF-12': ('ear_focus', 'ear_discomfort_description'),
    'WF-13': ('eye_sensation',), 'WF-14': ('abdominal_quality',),
    'WF-15': ('indigestion_description',), 'WF-16': ('stool_description', 'bowel_difficulty'),
    'WF-17': ('stool_description',), 'WF-18': ('urinary_focus', 'urinary_discomfort_description'),
    'WF-19': ('menstrual_focus', 'menstrual_flow_description'),
    'WF-20': ('skin_sensation', 'skin_appearance'),
}
TIMINGS = {
    'WF-05': ('headache.observed_context',), 'WF-07': ('fatigue.daily_pattern',),
    'WF-08': ('sleep.usual_bedtime', 'sleep.usual_wake_time'),
    'WF-09': ('cough.daily_pattern',), 'WF-10': ('nasal.time_pattern',),
    'WF-16': ('bowel_frequency',), 'WF-18': ('urination_pattern',),
    'WF-19': ('menstrual_current_pattern', 'menstrual_symptom_timing'),
}
EPISODES = {'WF-05': 'headache.episode_length', 'WF-06': 'dizziness.episode_length',
            'WF-14': 'episode_length', 'WF-17': 'episode_length'}
LEGACY_FACTORS = {'WF-01': 'leg.change_factors', 'WF-02': 'back.change_factors',
                  'WF-03': 'neck_shoulder.movement_context'}
RADIATION = {'WF-01': 'leg.pain_spread', 'WF-02': 'back.pain_spread'}

NEW_QUESTIONS = {
    'symptom_onset_character': ('How it started', 'Did this symptom start suddenly or gradually?'),
    'symptom_duration': ('Overall duration', 'How long has this symptom been present?'),
    'symptom_episode_duration': ('Episode duration', 'How long does each episode last?'),
    'aggravating_factors': ('What makes it worse', 'What makes this symptom worse, if anything?'),
    'relieving_factors': ('What helps', 'What eases this symptom, if anything?'),
    'symptom_location': ('Location', 'Where do you notice this symptom?'),
    'symptom_character': ('What it feels like', 'How would you describe what this symptom feels like?'),
}


def _generic_location(workflow_id: str) -> bool:
    # A location prompt is useful for an explicitly reported new/custom symptom,
    # but not a forced question for systemic symptoms, sleep or mental health.
    return workflow_id == 'GENERAL' or workflow_id not in {f'WF-{n:02}' for n in range(1, 31)}


def additional_questions(workflow_id: str) -> list[dict]:
    keys = ['symptom_onset_character', 'symptom_duration', 'aggravating_factors', 'relieving_factors']
    if workflow_id not in EPISODES:
        keys.append('symptom_episode_duration')
    if _generic_location(workflow_id):
        keys.append('symptom_location')
    if workflow_id not in CHARACTERS:
        keys.append('symptom_character')
    return [{'key': key, 'label': NEW_QUESTIONS[key][0], 'question': NEW_QUESTIONS[key][1],
             'condition': 'episodes' if key == 'symptom_episode_duration' else 'current_symptom'} for key in keys]


def dimension_for_key(workflow_id: str, key: str) -> str | None:
    if key in {'symptom_onset', 'symptom_onset_character'}:
        return 'O'
    if key in {'symptom_duration', 'symptom_episode_duration', EPISODES.get(workflow_id)}:
        return 'D'
    if key == 'symptom_location' or key == LOCATIONS.get(workflow_id):
        return 'L'
    if key == 'symptom_character' or key in CHARACTERS.get(workflow_id, ()):
        return 'C'
    if key == 'aggravating_factors':
        return 'A'
    if key == 'relieving_factors':
        return 'R'
    if key in {'symptom_pattern', 'symptom_frequency'} or key in TIMINGS.get(workflow_id, ()):
        return 'T'
    if key == 'severity':
        return 'S'
    return None


def _signal(concern: dict, signal: str) -> bool:
    return concern.get('signals', {}).get(signal, {}).get('present') is True


def _visible(slot: dict) -> bool:
    return not slot.get('exclude_from_handoff') and not slot.get('reused_from')


def _values(slots: dict, keys: list[str]) -> list[dict]:
    return [{'key': key, 'value': slots[key].get('value'), 'status': slots[key]['status']}
            for key in keys if key in slots and _visible(slots[key])
            and slots[key]['status'] in {'FILLED', 'UNCERTAIN'} and slots[key].get('value')]


def _status(slots: dict, keys: list[str], *, applicable: bool, partial_keys: list[str] = ()) -> str:
    if not applicable:
        return 'NOT_APPLICABLE'
    active = [slots[k] for k in keys if k in slots and _visible(slots[k]) and slots[k]['status'] != 'NOT_APPLICABLE']
    statuses = [slot['status'] for slot in active]
    # Alternatives within a dimension (e.g. frequency or a day pattern) do not
    # create mandatory duplicate questions. Only actual supplied text counts.
    if any(slot['status'] == 'FILLED' and slot.get('value') for slot in active):
        return 'FILLED'
    if 'UNCERTAIN' in statuses:
        return 'UNCERTAIN'
    if 'SKIPPED' in statuses:
        return 'SKIPPED'
    if any(slots.get(k, {}).get('status') == 'FILLED' and slots[k].get('value') and _visible(slots[k]) for k in partial_keys):
        return 'PARTIAL'
    if 'MISSING' in statuses or not statuses:
        return 'MISSING'
    return 'MISSING'


def coverage_for_session(session: dict) -> list[dict]:
    result = []
    for concern in session.get('concerns', []):
        wf, slots = concern['workflow_id'], concern.get('slots', {})
        applicable = _signal(concern, 'current_symptom')
        if wf == 'WF-19' and not _signal(concern, 'sensitive_permission'):
            applicable = False
        episodic = _signal(concern, 'episodes')
        dimension_keys = {
            'O': ['symptom_onset'],
            'L': [LOCATIONS[wf]] if wf in LOCATIONS else (['symptom_location'] if _generic_location(wf) else []),
            'D': [EPISODES.get(wf, 'symptom_episode_duration')] if episodic else ['symptom_duration'],
            'C': list(CHARACTERS.get(wf, ('symptom_character',))),
            'A': ['aggravating_factors'], 'R': ['relieving_factors'],
            'T': ['symptom_pattern', 'symptom_frequency', *TIMINGS.get(wf, ())],
            'S': ['severity'],
        }
        dimensions = []
        for identifier, label in DIMENSIONS:
            keys = dimension_keys[identifier]
            supplementary = ['symptom_onset_character'] if identifier == 'O' else []
            if identifier == 'D' and episodic:
                supplementary = ['symptom_duration']
            partial = [LEGACY_FACTORS[wf]] if identifier in {'A', 'R'} and wf in LEGACY_FACTORS else []
            active = applicable and bool(keys)
            status = _status(slots, keys, applicable=active, partial_keys=partial + supplementary)
            dimensions.append({'id': identifier, 'label': label, 'applicable': active,
                               'status': status,
                               'keys': list(dict.fromkeys(keys + supplementary)),
                               'values': _values(slots, list(dict.fromkeys(keys + supplementary))) if active else [],
                               'legacy_context': _values(slots, partial) if active and status != 'SKIPPED' else []})
        radiation_key = RADIATION.get(wf)
        radiation_active = bool(applicable and radiation_key and _signal(concern, 'spreading'))
        radiation = {'id': 'radiation', 'label': 'Radiation or spread', 'applicable': radiation_active,
                     'keys': [radiation_key] if radiation_key else [],
                     'status': _status(slots, [radiation_key] if radiation_key else [], applicable=radiation_active),
                     'values': _values(slots, [radiation_key]) if radiation_active else []}
        result.append({'concern_id': concern['id'], 'workflow_id': wf, 'applicable': applicable,
                       'dimensions': dimensions, 'radiation': radiation,
                       'supplied_count': sum(d['status'] == 'FILLED' for d in dimensions),
                       'applicable_count': sum(d['applicable'] for d in dimensions)})
    return result


def priority_targets(session: dict, targets: list[dict]) -> list[dict]:
    """Stable symptom-history priority; no urgency score or hidden diagnosis."""
    concerns = {c['id']: c for c in session.get('concerns', [])}
    agenda = list(dict.fromkeys(session.get('priority_order', []) + list(concerns)))
    coverage = {row['concern_id']: {d['id']: d for d in row['dimensions']} for row in coverage_for_session(session)}
    order = {key: n for n, key in enumerate(('O', 'L', 'D', 'C', 'A', 'R', 'T', 'S'))}
    def rank(target: dict) -> tuple:
        concern = concerns.get(target.get('concern_id'))
        if not concern:
            # Shared medication/allergy preparation keeps its original early
            # position; symptom dimensions do not become a clinical priority.
            return (-1, 0, 0)
        agenda_index = agenda.index(concern['id'])
        dimension = dimension_for_key(concern['workflow_id'], target['key'])
        status = coverage.get(concern['id'], {}).get(dimension, {}).get('status')
        if status in {'MISSING', 'PARTIAL'}:
            return (agenda_index, 0, order[dimension])
        return (agenda_index, 1, 0)
    return sorted(targets, key=rank)
