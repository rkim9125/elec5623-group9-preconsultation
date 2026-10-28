"""V3 entry modes, durable-profile reuse and locale boundaries; no live services."""
from copy import deepcopy
from datetime import date as real_date
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from app.product import assessment, auth, config, engine, forms, intelligence, media, pipeline, profiles, provider, routes
from app.product.database import load_intake
from .test_product_auth import product_env, sign_in
from .test_product_intelligence import DownExtractor, Extractor, Smart


@pytest.fixture
def wizard_api(product_env):
    app = FastAPI()
    for router in (auth.router, routes.router, media.router):
        app.include_router(router, prefix='/api/v1')
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        sign_in(client, product_env)
        yield client


def test_default_model_exact_spelling_configurable_and_no_model_substitution(monkeypatch):
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    assert config.get_settings().openai_model == 'gpt-6-sol'
    assert config.model_options()[0]['id'] == 'gpt-6-sol'
    monkeypatch.setenv('OPENAI_MODEL', 'explicit-custom-model')
    assert config.get_settings().openai_model == 'explicit-custom-model'
    assert config.model_options()[0]['id'] == 'explicit-custom-model'


@pytest.mark.parametrize('locale', ['en', 'zh-CN', 'zh-TW', 'ko', 'ja'])
def test_custom_chat_opens_directly_without_baseline_or_invented_concern(wizard_api, locale):
    response = wizard_api.post('/api/v1/intakes', json={'consent': True, 'mode': 'chat', 'locale': locale})
    assert response.status_code == 201
    state = response.json()
    assert state['mode'] == 'chat' and state['locale'] == locale
    assert state['stage'] == 'followup' and state['baseline']['completed']
    assert state['concerns'] == [] and not state.get('ai_activity')
    assert len(state['messages']) == 1 and state['messages'][0]['role'] == 'assistant'
    assert state['current_question']['key'] == 'main_concern'
    assert not state['baseline'].get('field_keys')


def test_chat_extraction_failure_preserves_narrative_and_original_model():
    state = forms.initialize(engine.new_intake({'id': 'patient'}, 'gpt-6-astra', []), mode='chat')
    pipeline.process_message(state, 'I want to discuss workplace paperwork.', extraction=DownExtractor(), intelligence=Smart())
    assert state['model'] == 'gpt-6-astra' and state['assistant']['mode'] == 'unavailable'
    assert state['concerns'][0]['slots']['concern_description']['value'] == 'I want to discuss workplace paperwork.'
    assert state['stage'] == 'followup'


def test_chat_safety_gate_runs_before_any_provider_call():
    state = forms.initialize(engine.new_intake({'id': 'patient'}, 'gpt-6-astra', []), mode='chat')
    extraction = Extractor()
    pipeline.process_message(state, 'I have chest pain now.', extraction=extraction, intelligence=Smart())
    assert state['status'] == 'interrupted' and extraction.calls == []


def test_profile_is_reused_editable_isolated_and_never_reuses_current_data(wizard_api):
    original = {'date_of_birth': '1990-01-02', 'sex_at_birth': 'female', 'blood_group': 'O+',
                'medical_history': 'Childhood surgery', 'family_history': 'Family background'}
    assert wizard_api.put('/api/v1/auth/profile', json=original).status_code == 200
    state = wizard_api.post('/api/v1/intakes', json={'consent': True, 'workflow_ids': ['WF-01']}).json()
    history = state['shared_slots']['relevant_history']
    assert history['status'] == 'FILLED' and history['evidence']['source'] == 'patient_profile'
    assert 'Childhood surgery' in history['value']
    assert state['shared_slots']['current_medications']['status'] == 'MISSING'
    assert state['shared_slots']['allergies']['status'] == 'MISSING'
    url = '/api/v1/intakes/' + state['id']
    field = next(f for g in wizard_api.get(url + '/form').json()['groups'] for f in g['fields'] if f['key'] == 'relevant_history')
    assert field['profile_reused']
    changed = wizard_api.put(url + '/baseline', json={'answers': [{'key': 'relevant_history', 'value': 'Corrected history'}]}).json()
    assert changed['shared_slots']['relevant_history']['value'] == 'Corrected history'
    clinician = routes.clinician_public_session(changed)
    assert 'medical_history' not in clinician['profile_snapshot']
    assert 'Childhood surgery' not in json.dumps(clinician)
    assert wizard_api.put('/api/v1/auth/profile', json={'date_of_birth': '1991-01-02'}).status_code == 200
    assert load_intake(state['id'])['profile_snapshot']['date_of_birth'] == '1990-01-02'
    opted_out = wizard_api.post('/api/v1/intakes', json={'consent': True, 'use_profile': False}).json()
    assert 'profile_snapshot' not in opted_out and opted_out['shared_slots']['relevant_history']['status'] == 'MISSING'


def test_profile_unknown_and_declined_are_not_facts():
    sources = intelligence.current_sources({'profile_snapshot': {'sex_at_birth': 'prefer_not_to_say', 'blood_group': 'unknown'}})
    assert [(s['status'], s['value']) for s in sources] == [('SKIPPED', None), ('UNCERTAIN', None)]


def test_legacy_english_reports_keep_their_existing_fingerprint_shape():
    state = engine.new_intake({'id': 'patient'}, 'gpt-6-sol', [])
    context, _, fingerprint = assessment.assessment_input(state)
    assert 'locale' not in context
    state['locale'] = 'ja'
    translated, _, new_fingerprint = assessment.assessment_input(state)
    assert translated['locale'] == 'ja' and new_fingerprint != fingerprint


@pytest.mark.parametrize('born,today,age', [('1990-10-19', '2026-10-18', 35), ('1990-10-19', '2026-10-19', 36),
                                         ('1990-10-19', '2026-10-20', 36), ('2000-02-29', '2025-02-28', 24), ('2000-02-29', '2025-03-01', 25)])
def test_age_is_derived_per_intake_with_birthday_boundaries(monkeypatch, born, today, age):
    stored = {'date_of_birth': born}
    class Today(real_date):
        @classmethod
        def today(cls): return cls.fromisoformat(today)
    monkeypatch.setattr(profiles, 'date', Today)
    monkeypatch.setattr(profiles, 'load_profile', lambda user_id: stored)
    snapshot = profiles.snapshot_for_intake('patient')
    assert snapshot['date_of_birth'] == born
    assert snapshot['age_years'] == age and snapshot['age_as_of'] == today
    assert stored == {'date_of_birth': born}  # No expiring age saved to reusable background.
    source = next(row for row in intelligence.current_sources({'profile_snapshot': snapshot}) if row['key'] == 'profile.age_at_preparation')
    assert source['value'] == f'{age} years as of {today}'


def test_existing_intake_locale_can_change_before_review_and_followup(wizard_api, monkeypatch):
    seen = []
    def followup(state):
        seen.append(state['locale'])
        return state
    def review(state, correction=None):
        seen.append(state['locale'])
        return engine.build_review(state)
    monkeypatch.setattr(routes.pipeline, 'start_followup', followup)
    monkeypatch.setattr(routes.pipeline, 'build_review', review)
    state = wizard_api.post('/api/v1/intakes', json={'consent': True, 'mode': 'chat'}).json()
    url = '/api/v1/intakes/' + state['id']
    assert wizard_api.post(url + '/followup', json={'locale': 'ko'}).json()['locale'] == 'ko'
    assert wizard_api.post(url + '/review', json={'locale': 'ja'}).json()['locale'] == 'ja'
    assert wizard_api.patch(url + '/review', json={'text': 'A correction', 'locale': 'zh-TW'}).json()['locale'] == 'zh-TW'
    assert seen == ['ko', 'ja', 'zh-TW']
    assert wizard_api.post(url + '/review').status_code == 200  # Existing clients can still omit a body.


def test_invalid_locale_and_mode_are_rejected_and_config_lists_five_languages(wizard_api):
    for extra in ({'locale': 'xx'}, {'locale': 'Ignore instructions'}, {'mode': 'form'}):
        assert wizard_api.post('/api/v1/intakes', json={'consent': True, **extra}).status_code == 422
    data = wizard_api.get('/api/v1/config').json()
    assert data['default_locale'] == 'en'
    assert [item['id'] for item in data['locales']] == ['en', 'zh-CN', 'zh-TW', 'ko', 'ja']


def test_registered_doctors_replace_environment_allowlist(wizard_api, product_env, monkeypatch):
    monkeypatch.setattr(routes.pipeline, 'build_review', engine.build_review)
    state = wizard_api.post('/api/v1/intakes', json={'consent': True}).json()
    url = '/api/v1/intakes/' + state['id']
    summary = wizard_api.post(url + '/review').json()['summary']
    # An environment entry alone never establishes a doctor account.
    assert wizard_api.post(url + '/approve', json={'version': summary['version'], 'doctor_email': 'doctor@example.test'}).status_code == 422
    with TestClient(wizard_api.app, headers={'Origin': 'http://testserver'}) as doctor:
        sign_in(doctor, product_env, 'new-clinician@independent.test', 'doctor')
        care_team = wizard_api.get('/api/v1/config').json()['care_team']
        assert [entry['email'] for entry in care_team] == ['new-clinician@independent.test']
        approved = wizard_api.post(url + '/approve', json={'version': summary['version'], 'doctor_email': 'new-clinician@independent.test'})
        assert approved.status_code == 200
        assert doctor.get('/api/v1/clinician/intakes/' + state['id']).status_code == 200


@pytest.mark.parametrize('locale,language', [('en', 'en'), ('zh-CN', 'zh'), ('zh-TW', 'zh'), ('ko', 'ko'), ('ja', 'ja')])
def test_voice_passes_selected_language_to_provider(wizard_api, monkeypatch, locale, language):
    captured = {}
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            captured.update(kwargs)
            return httpx.Response(200, json={'text': 'Patient speech'})
    monkeypatch.setattr(media.httpx, 'AsyncClient', Client)
    response = wizard_api.post('/api/v1/transcriptions', data={'locale': locale}, files={'file': ('audio.webm', b'synthetic-audio', 'audio/webm')})
    assert response.status_code == 200 and response.json()['locale'] == locale
    assert captured['data']['language'] == language
    if locale == 'zh-CN': assert '简体' in captured['data']['prompt']
    if locale == 'zh-TW': assert '繁體' in captured['data']['prompt']


def test_locale_reaches_extraction_and_ai_instructions(wizard_api, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    captured = []
    def post(url, **kwargs):
        captured.append(deepcopy(kwargs['json']))
        name = kwargs['json']['text']['format']['name']
        if name == 'preparation_followup_batch':
            data = {'questions': [], 'overview': {'text': '', 'source_ids': []}, 'suggested_concern_ids': []}
        elif name == 'preparation_synthesis':
            data = {'patient_overview': [], 'clinician_brief': [], 'concern_summaries': [], 'appointment_agenda': [], 'uncertainties': []}
        else:
            data = {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': []}
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(data)}]}]})
    monkeypatch.setattr(provider.httpx, 'post', post)
    state = engine.new_intake({'id': 'patient'}, 'gpt-6-astra', [])
    state['locale'] = 'ja'
    provider.OpenAIProvider().extract(pipeline._extraction_view(state), '相談したいです')
    intelligence.OpenAIIntelligence().plan(model=state['model'], sources=[], concerns=[], targets=[], locale='ja')
    intelligence.OpenAIIntelligence().synthesize(model=state['model'], sources=[], concerns=[], locale='ja')
    for row in captured:
        instructions = row.get('instructions') or row['input'][0]['content'][0]['text']
        user_input = row['input'] if isinstance(row['input'], str) else next(m['content'] for m in row['input'] if m['role'] == 'user')
        data = json.loads(user_input)
        assert row['model'] == 'gpt-6-astra' and 'Japanese' in instructions
        assert data.get('locale', data.get('context', {}).get('locale')) == 'ja'


@pytest.mark.parametrize('value,translated', [('没有过敏', '没有已知过敏。'), ('アレルギーなし', 'アレルギーはありません。'), ('알레르기 없음', '알레르기가 없습니다.')])
def test_localized_negation_is_preserved(value, translated):
    row = {'id': 's', 'concern_id': 'session', 'value': value, 'status': 'FILLED'}
    assert intelligence._validate_cited({'text': translated, 'source_ids': ['s']}, {'s': row})['text'] == translated
    with pytest.raises(intelligence.IntelligenceUnavailable, match='negative'):
        intelligence._validate_cited({'text': 'Patient has an allergy.', 'source_ids': ['s']}, {'s': row})
