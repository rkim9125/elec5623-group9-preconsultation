"""Concise preparation and explicit reuse of the patient's own prior answers."""
from copy import deepcopy

import pytest

from app.product import engine, forms, intelligence
from app.product.database import load_intake
from .test_product_wizard import wizard_api  # noqa: F401
from .test_product_auth import product_env, sign_in  # noqa: F401


def create(client):
    response = client.post('/api/v1/intakes', json={'consent': True, 'workflow_ids': ['WF-01']})
    assert response.status_code == 201, response.text
    return response.json()


def save(client, intake, **values):
    response = client.put(f'/api/v1/intakes/{intake["id"]}/baseline', json={
        'answers': [{'key': key, 'value': value, 'status': 'FILLED' if value else 'MISSING'}
                    for key, value in values.items()]})
    assert response.status_code == 200, response.text
    return response.json()


def test_first_question_is_specific_and_repeated_context_is_one_optional_step():
    state = forms.initialize(engine.new_intake({'id': 'test'}, 'gpt-6-astra', ['WF-01']))
    fields = [f for g in forms.get_form(state)['groups'] for f in g['fields']]
    description = next(f for f in fields if f['key'] == 'concern_description')
    assert description['question'] == 'Please briefly describe your leg discomfort.'
    assert 'left calf' in description['hint']
    visible = [f['key'] for f in fields if not f.get('review_only')]
    assert 'additional_information' in visible
    assert not {'relevant_history', 'patient_worry', 'clinician_questions'} & set(visible)
    assert not next(f for f in fields if f['key'] == 'additional_information')['required']
    forms.apply_baseline(state, [{'key': 'additional_information', 'value': 'I want to discuss my work schedule.'}], complete=True)
    assert any(s['value'] == 'I want to discuss my work schedule.' for s in intelligence.current_sources(state))
    assert all(state['shared_slots'][key]['baseline'] for key in forms.REVIEW_ONLY_FIELDS)


def test_older_drafts_keep_existing_context_and_accept_merged_field():
    state = forms.initialize(engine.new_intake({'id': 'test'}, 'gpt-6-astra', ['WF-01']))
    forms.apply_baseline(state, [{'key': 'patient_worry', 'value': 'I am worried about missing work.'}])
    previous = deepcopy(state['shared_slots']['patient_worry'])
    state['shared_slots'].pop('additional_information')
    forms.apply_baseline(state, [{'key': 'additional_information', 'value': 'Please also discuss travel.'}])
    assert state['shared_slots']['patient_worry'] == previous
    assert state['shared_slots']['additional_information']['value'] == 'Please also discuss travel.'


def test_previous_medicines_and_allergies_are_suggestions_until_chosen(wizard_api):
    prior = save(wizard_api, create(wizard_api), current_medications='A daily supplement.', allergies='A rash after a medicine.')
    current = create(wizard_api)
    before = load_intake(current['id'])
    data = wizard_api.get(f'/api/v1/intakes/{current["id"]}/form').json()
    assert data['previous_answers']['current_medications']['value'] == 'A daily supplement.'
    assert data['previous_answers']['allergies']['value'] == 'A rash after a medicine.'
    assert all(v['requires_confirmation'] and v['recorded_at'] for v in data['previous_answers'].values())
    assert load_intake(current['id']) == before
    assert current['shared_slots']['current_medications']['status'] == 'MISSING'
    updated = save(wizard_api, current, current_medications=data['previous_answers']['current_medications']['value'])
    assert updated['shared_slots']['current_medications']['evidence']['source'] == 'patient_form'
    assert updated['shared_slots']['allergies']['status'] == 'MISSING'
    # A newer consultation is never suggested back into an older one.
    assert wizard_api.get(f'/api/v1/intakes/{prior["id"]}/form').json()['previous_answers'] == {}


@pytest.mark.parametrize('status', ['MISSING', 'UNCERTAIN', 'SKIPPED'])
def test_cleared_or_declined_recent_answer_does_not_resurrect_old_history(wizard_api, status):
    save(wizard_api, create(wizard_api), allergies='An old answer.')
    recent = save(wizard_api, create(wizard_api), allergies='A newer answer.')
    response = wizard_api.put(f'/api/v1/intakes/{recent["id"]}/baseline', json={
        'answers': [{'key': 'allergies', 'status': status, 'value': None}]})
    assert response.status_code == 200
    current = create(wizard_api)
    suggestions = wizard_api.get(f'/api/v1/intakes/{current["id"]}/form').json()['previous_answers']
    assert 'allergies' not in suggestions


def test_history_suggestions_never_cross_patient_accounts(wizard_api, product_env):
    patient_a = save(wizard_api, create(wizard_api), current_medications='Private prior answer.')
    sign_in(wizard_api, product_env, 'another-patient@example.test')
    patient_b = create(wizard_api)
    assert wizard_api.get(f'/api/v1/intakes/{patient_b["id"]}/form').json()['previous_answers'] == {}
    assert wizard_api.get(f'/api/v1/intakes/{patient_a["id"]}/form').status_code == 404
