"""Language changes preserve patient facts, revisions and sharing boundaries."""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.product import assessment, auth, engine, forms, pipeline, routes
from app.product.database import load_intake, save_intake
from app.product.intelligence import IntelligenceUnavailable
from app.product.locales import field_label, language_instruction, translate_text, workflow_title
from .test_product_auth import product_env, sign_in


@pytest.fixture
def locale_api(product_env):
    app = FastAPI()
    app.include_router(auth.router, prefix='/api/v1')
    app.include_router(routes.router, prefix='/api/v1')
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        sign_in(client, product_env)
        yield client


def create(client):
    response = client.post('/api/v1/intakes', json={'consent': True, 'workflow_ids': ['WF-01']})
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize('locale,title', [('en', 'Leg pain'), ('zh-CN', '腿痛'), ('zh-TW', '腿痛'), ('ko', '다리 통증'), ('ja', '脚の痛み')])
def test_structured_summary_localizes_labels_and_titles_not_original_evidence(locale, title):
    state = forms.initialize(engine.new_intake({'id': 'patient'}, 'gpt-6-astra', ['WF-01']))
    state['locale'] = locale
    cid = state['concerns'][0]['id']
    original = 'My original words: Vitamin C, 500 mg, unknown strength.'
    forms.apply_baseline(state, [{'concern_id': cid, 'key': 'concern_description', 'value': original}])
    slots = deepcopy(state['concerns'][0]['slots'])
    engine.build_review(state)
    summary = state['summary']
    assert summary['locale'] == locale
    assert summary['sections'][1]['title'] == title
    assert original in summary['text']
    assert state['concerns'][0]['slots'] == slots
    if locale != 'en':
        assert 'PATIENT PREPARATION NOTES' not in summary['text']
        assert 'Not yet collected' not in summary['text']
        assert 'Reason, priorities and shared background' not in summary['text']
        assert 'not explored' not in summary['text']


def test_canonical_titles_translate_in_both_directions_without_rewriting_custom_title():
    assert workflow_title('WF-01', 'Leg pain', 'zh-CN') == '腿痛'
    assert workflow_title('WF-01', '腿痛', 'en') == 'Leg pain'
    assert workflow_title('WF-01', 'My running questions', 'ja') == 'My running questions'
    assert translate_text('This is my own narrative.', 'ko') == 'This is my own narrative.'
    instruction = language_instruction('zh-TW')
    assert 'Traditional Chinese' in instruction and 'suggested-answer label AND value' in instruction
    assert 'supplied concern titles unchanged' not in instruction
    assert 'verbatim' in language_instruction('zh-CN', verbatim=True)


@pytest.mark.parametrize('locale', ['zh-CN', 'zh-TW', 'ko', 'ja'])
def test_legacy_and_dynamic_source_labels_translate_without_changing_item_names(locale):
    for label in ['Location', 'Current medication', 'Appointment goals']:
        assert field_label('legacy', label, locale) != label
    for field in ['dose', 'frequency', 'actual_use', 'ordering_clinician']:
        prefix = 'Vitamin C 500 mg · Frequency'
        label = field_label('medication.1.' + field, prefix + ' · ' + field, locale)
        assert label.startswith(prefix + ' · ')
        assert not label.endswith(' · ' + field)
    assert field_label('medication.1.dose', 'Vitamin C 500 mg · dose', 'en') == 'Vitamin C 500 mg · dose'


def test_locale_update_without_summary_or_batch_and_revision_boundary(locale_api):
    state = create(locale_api)
    url = f"/api/v1/intakes/{state['id']}/locale"
    response = locale_api.post(url, json={'locale': 'zh-CN', 'revision': state['revision']})
    assert response.status_code == 200, response.text
    assert response.json()['locale'] == 'zh-CN'
    assert response.json()['revision'] > state['revision']
    assert locale_api.post(url, json={'locale': 'ja', 'revision': state['revision']}).status_code == 409
    assert load_intake(state['id'])['locale'] == 'zh-CN'
    assert locale_api.post(url, json={'locale': 'unsupported'}).status_code == 422
    assert locale_api.post(url, json={'locale': 'ja'}, headers={'Origin': 'https://outside.test'}).status_code == 403


def test_locale_change_preserves_summary_version_and_marks_old_synthesis_language(locale_api):
    state = create(locale_api)
    state = load_intake(state['id'])
    engine.build_review(state)
    state['summary']['synthesis'] = {'status': 'live', 'patient_overview': [{'text': 'Original English summary.'}]}
    save_intake(state)
    before = load_intake(state['id'])
    result = locale_api.post(f"/api/v1/intakes/{state['id']}/locale", json={'locale': 'ja'}).json()
    assert result['locale'] == result['summary']['locale'] == 'ja'
    assert result['summary']['version'] == before['summary']['version']
    assert result['summary']['synthesis']['locale'] == 'en'
    assert result['summary']['synthesis']['patient_overview'] == before['summary']['synthesis']['patient_overview']
    assert result['summary']['sections'][1]['title'] == '脚の痛み'


def test_failed_question_translation_is_atomic(locale_api, monkeypatch):
    state = create(locale_api)
    before = load_intake(state['id'])
    def fail(session):
        session['title'] = 'partial result that must not be saved'
        raise IntelligenceUnavailable('Synthetic translation failure')
    monkeypatch.setattr(pipeline, 'relocalize_pending_followup', fail)
    response = locale_api.post(f"/api/v1/intakes/{state['id']}/locale", json={'locale': 'ko'})
    assert response.status_code == 409
    assert load_intake(state['id']) == before


def test_cannot_share_generated_summary_in_previous_language(locale_api):
    state = load_intake(create(locale_api)['id'])
    engine.build_review(state)
    state['locale'] = 'zh-CN'
    state['summary']['synthesis'] = {'status': 'live', 'locale': 'en'}
    save_intake(state)
    before = load_intake(state['id'])
    response = locale_api.post(f"/api/v1/intakes/{state['id']}/approve",
                               json={'version': state['summary']['version']})
    assert response.status_code == 409
    assert response.json()['detail'] == 'Refresh the summary in your selected language before sharing.'
    assert load_intake(state['id']) == before


def test_localized_public_summary_does_not_restore_superseded_private_notes():
    state = forms.initialize(engine.new_intake({'id': 'patient'}, 'gpt-6-astra', ['WF-01']))
    state['locale'] = 'zh-CN'
    state['_has_corrections'] = True
    state['unclassified_notes'] = [{'text': 'Superseded private information.'}]
    engine.build_review(state)
    before = deepcopy(state)
    public = routes.public_session(state)
    assert 'Superseded private information.' not in public['summary']['text']
    assert '_has_corrections' not in public
    assert state == before


@pytest.mark.parametrize('report_locale', ['en', 'zh-CN'])
def test_cannot_share_legacy_or_different_language_assessment(locale_api, report_locale):
    state = load_intake(create(locale_api)['id'])
    state['locale'] = 'zh-CN'
    engine.build_review(state)
    _, _, fingerprint = assessment.assessment_input(state, include_bytes=False)
    state['ai_report'] = {'status': 'ready', 'locale': report_locale, 'input_fingerprint': fingerprint}
    save_intake(state)
    before = load_intake(state['id'])
    response = locale_api.post(f"/api/v1/intakes/{state['id']}/approve",
                               json={'version': state['summary']['version']})
    assert response.status_code == 409
    assert response.json()['detail'] == 'Refresh the summary and assessment in your selected language before sharing.'
    assert load_intake(state['id']) == before


def test_locale_route_cannot_modify_approved_record_or_other_patient(locale_api, product_env):
    state = create(locale_api)
    stored = load_intake(state['id'])
    engine.build_review(stored)
    stored['status'] = 'approved'
    stored['summary']['approved_at'] = '2026-10-21T00:00:00Z'
    save_intake(stored)
    before = load_intake(state['id'])
    url = f"/api/v1/intakes/{state['id']}/locale"
    assert locale_api.post(url, json={'locale': 'zh-CN'}).status_code == 409
    assert load_intake(state['id']) == before
    sign_in(locale_api, product_env, 'another-patient@example.test')
    assert locale_api.post(url, json={'locale': 'zh-CN'}).status_code == 404
