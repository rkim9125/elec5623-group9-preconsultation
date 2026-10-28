"""Symptom-history coverage must reflect answers, not template completion."""
from copy import deepcopy

import pytest

from app.product import engine, forms, oldcarts, presentation
from app.product.workflows import WORKFLOWS


def new(workflows=('WF-01',)):
    return forms.initialize(engine.new_intake({'id': 'patient'}, 'unused', list(workflows)))


def dimensions(session, index=0):
    return {d['id']: d for d in oldcarts.coverage_for_session(session)[index]['dimensions']}


def record(session, key, value=None, status='FILLED', index=0):
    slot = session['concerns'][index]['slots'][key]
    engine._update_slot(slot, value, status, {'source': 'patient_text', 'span': value or ''}, correction=True)
    return slot


def test_leg_wizard_has_explicit_direction_and_severity_without_duplicate_context():
    session = new()
    fields = forms.get_form(session)['groups'][1]['fields']
    by_key = {f['key']: f for f in fields}
    assert {'symptom_onset', 'leg.pain_site', 'leg.pain_character', 'aggravating_factors',
            'relieving_factors', 'severity'} <= set(by_key)
    assert not {'leg.activity_context', 'leg.change_factors'} & set(by_key)
    assert by_key['symptom_onset']['oldcarts_dimension'] == 'O'
    assert by_key['aggravating_factors']['oldcarts_dimension'] == 'A'
    assert by_key['relieving_factors']['oldcarts_dimension'] == 'R'
    assert by_key['severity']['oldcarts_dimension'] == 'S'
    assert not by_key['severity']['required']
    assert [o['value'] for o in by_key['severity']['presentation']['options']] == ['Mild', 'Moderate', 'Severe']


def test_leg_direct_answers_have_real_coverage_and_keep_exact_provenance():
    session = new()
    owner = session['concerns'][0]['id']
    answers = {'symptom_onset': 'Last Monday', 'leg.pain_site': 'Both knees',
               'leg.pain_character': 'Aching', 'aggravating_factors': 'Stairs make it worse.',
               'relieving_factors': 'Rest eases it.', 'symptom_frequency': 'Each evening', 'severity': 'Moderate'}
    forms.apply_baseline(session, [{'concern_id': owner, 'key': k, 'value': v, 'status': 'FILLED'} for k, v in answers.items()])
    before = deepcopy(session['concerns'][0]['slots']['aggravating_factors'])
    coverage = oldcarts.coverage_for_session(session)[0]
    assert coverage['supplied_count'] == 7 and coverage['applicable_count'] == 8
    assert dimensions(session)['D']['status'] == 'MISSING'
    assert session['concerns'][0]['slots']['aggravating_factors'] == before
    assert before['evidence']['span'] == 'Stairs make it worse.'
    assert 'evidence' not in repr(coverage)


def test_onset_is_not_a_duration_or_onset_character_answer():
    session = new()
    record(session, 'symptom_onset', 'Monday')
    engine._apply_conditions(session)
    slots = session['concerns'][0]['slots']
    assert slots['symptom_duration']['status'] == 'MISSING'
    assert slots['symptom_onset_character']['status'] == 'MISSING'
    assert dimensions(session)['D']['status'] == 'MISSING'


def test_episode_duration_activates_only_for_reported_episodes_and_is_distinct():
    session = new()
    concern = session['concerns'][0]
    assert concern['slots']['symptom_episode_duration']['status'] == 'NOT_APPLICABLE'
    record(session, 'symptom_duration', 'Three weeks')
    assert dimensions(session)['D']['status'] == 'FILLED'
    concern['signals']['episodes'] = {'present': True, 'evidence': {'span': 'It comes and goes.'}}
    engine._apply_conditions(session)
    assert concern['slots']['symptom_episode_duration']['status'] == 'MISSING'
    assert dimensions(session)['D']['status'] == 'PARTIAL'
    record(session, 'symptom_episode_duration', 'Twenty minutes each time')
    assert dimensions(session)['D']['status'] == 'FILLED'
    assert dimensions(session)['D']['values'][0]['value'] == 'Twenty minutes each time'


@pytest.mark.parametrize('workflow,key', [('WF-05', 'headache.episode_length'), ('WF-06', 'dizziness.episode_length'),
                                         ('WF-14', 'episode_length'), ('WF-17', 'episode_length')])
def test_existing_episode_fields_are_reused(workflow, key):
    session = new((workflow,))
    assert 'symptom_episode_duration' not in session['concerns'][0]['slots']
    record(session, key, 'About ten minutes')
    assert dimensions(session)['D']['status'] == 'FILLED'
    assert dimensions(session)['D']['keys'][0] == key


@pytest.mark.parametrize('status,value', [('UNCERTAIN', 'I cannot tell.'), ('SKIPPED', None)])
def test_explicit_unknown_and_refusal_are_not_supplied_or_relabelled_missing(status, value):
    session = new()
    record(session, 'symptom_pattern', value, status)
    record(session, 'severity', value, status)
    coverage = oldcarts.coverage_for_session(session)[0]
    assert dimensions(session)['T']['status'] == status
    assert dimensions(session)['S']['status'] == status
    assert coverage['supplied_count'] == 0
    if status == 'SKIPPED':
        assert dimensions(session)['S']['values'] == []


def test_legacy_draft_keeps_answer_and_provenance_without_inventing_direction():
    session = new()
    concern = session['concerns'][0]
    for key in ('aggravating_factors', 'relieving_factors', 'symptom_duration'):
        concern['slots'].pop(key)
    legacy = engine._slot('leg.change_factors', question='What have you noticed changes the pain?')
    legacy.update(status='FILLED', value='Changes with rest', evidence={'source': 'patient_form', 'span': 'Changes with rest'})
    concern['slots']['leg.change_factors'] = deepcopy(legacy)
    fields = forms.get_form(session)['groups'][1]['fields']
    assert concern['slots']['leg.change_factors'] == legacy
    old = next(f for f in fields if f['key'] == 'leg.change_factors')
    assert old['review_only'] and old['legacy_context']
    assert dimensions(session)['A']['status'] == 'PARTIAL'
    assert dimensions(session)['R']['status'] == 'PARTIAL'
    assert dimensions(session)['A']['values'] == []


def test_excluded_or_old_alias_values_never_appear_in_coverage():
    session = new()
    record(session, 'severity', 'Private text')['exclude_from_handoff'] = True
    record(session, 'symptom_duration', 'Monday')['reused_from'] = 'symptom_onset'
    legacy = engine._slot('leg.change_factors')
    legacy.update(status='FILLED', value='Private legacy text', exclude_from_handoff=True)
    session['concerns'][0]['slots']['leg.change_factors'] = legacy
    payload = oldcarts.coverage_for_session(session)
    assert 'Private' not in repr(payload) and 'Monday' not in repr(payload)
    assert dimensions(session)['S']['status'] == 'MISSING'
    assert dimensions(session)['D']['status'] == 'MISSING'


def test_explicit_direction_refusal_takes_precedence_over_legacy_context():
    session = new()
    legacy = engine._slot('leg.change_factors')
    legacy.update(status='FILLED', value='Changes with rest')
    session['concerns'][0]['slots']['leg.change_factors'] = legacy
    record(session, 'aggravating_factors', None, 'SKIPPED')
    record(session, 'relieving_factors', 'I cannot tell', 'UNCERTAIN')
    assert dimensions(session)['A']['status'] == 'SKIPPED'
    assert dimensions(session)['R']['status'] == 'UNCERTAIN'


@pytest.mark.parametrize('workflow', ['WF-24', 'WF-25', 'WF-26', 'WF-27', 'WF-28', 'WF-29'])
def test_review_only_visits_have_no_symptom_burden(workflow):
    session = new((workflow,))
    coverage = oldcarts.coverage_for_session(session)[0]
    assert not coverage['applicable'] and coverage['applicable_count'] == 0
    assert all(d['status'] == 'NOT_APPLICABLE' for d in coverage['dimensions'])
    keys = {f['key'] for f in forms.get_form(session)['groups'][1]['fields']}
    assert not {'aggravating_factors', 'relieving_factors', 'severity', 'symptom_onset_character'} & keys


def test_custom_concern_only_activates_after_explicit_symptom_signal():
    session = new(())
    assert not oldcarts.coverage_for_session(session)[0]['applicable']
    concern = session['concerns'][0]
    concern['signals']['current_symptom'] = {'present': True, 'evidence': {'span': 'I have an ache.'}}
    engine._apply_conditions(session)
    assert oldcarts.coverage_for_session(session)[0]['applicable_count'] == 8
    assert concern['slots']['symptom_location']['status'] == 'MISSING'


def test_radiation_is_separate_from_relief_and_not_assumed():
    session = new()
    row = oldcarts.coverage_for_session(session)[0]
    assert row['radiation']['status'] == 'NOT_APPLICABLE'
    assert oldcarts.dimension_for_key('WF-01', 'leg.pain_spread') is None
    session['concerns'][0]['signals']['spreading'] = {'present': True}
    engine._apply_conditions(session)
    record(session, 'leg.pain_spread', 'Towards my ankle')
    row = oldcarts.coverage_for_session(session)[0]
    assert row['radiation']['status'] == 'FILLED'
    assert dimensions(session)['R']['status'] == 'MISSING'


def test_priority_respects_patient_concern_order_before_dimension_order():
    session = new(('WF-01', 'WF-02'))
    first, second = [c['id'] for c in session['concerns']]
    session['priority_order'] = [second, first]
    targets = [{'concern_id': first, 'key': 'symptom_onset'}, {'concern_id': second, 'key': 'severity'},
               {'concern_id': second, 'key': 'symptom_onset'}]
    assert oldcarts.priority_targets(session, targets) == [targets[2], targets[1], targets[0]]


@pytest.mark.parametrize('workflow', WORKFLOWS, ids=lambda w: w['id'])
def test_mapped_keys_exist_in_real_schema(workflow):
    session = new((workflow['id'],))
    for concern, row in zip(session['concerns'], oldcarts.coverage_for_session(session)):
        for dimension in row['dimensions']:
            assert all(key in concern['slots'] for key in dimension['keys'])


def test_explicit_none_options_are_exclusive_and_never_defaults():
    for key in ('aggravating_factors', 'relieving_factors'):
        options = presentation.for_field('WF-01', key)['options']
        assert next(o for o in options if o['label'] == 'Nothing noticed')['exclusive'] is True
        assert all('selected' not in o for o in options)
