"""OLD CARTS across saved narrative, planning, approved projection and PDF.

These are deterministic product tests, not clinical or live-model validation.
"""
from copy import deepcopy
from io import BytesIO
import json

from pypdf import PdfReader
import pytest

from app.product import engine, forms, pipeline, routes, report_pdf
from .test_product_intelligence import PATIENT, Extractor, DownExtractor, Smart, fact
from .test_product_wizard import wizard_api
from .test_product_auth import product_env


def draft():
    state = forms.initialize(engine.new_intake(PATIENT, 'gpt-6-astra', ['WF-01']))
    return state, state['concerns'][0]['id']


def test_saved_description_prefills_grounded_gaps_without_starting_followup():
    state, owner = draft()
    text = 'My left calf aches for three days. Walking makes it worse.'
    forms.apply_baseline(state, [{'concern_id': owner, 'key': 'concern_description', 'value': text},
                                 {'concern_id': owner, 'key': 'severity', 'status': 'UNCERTAIN'},
                                 {'concern_id': owner, 'key': 'relieving_factors', 'status': 'SKIPPED'}])
    extractor = Extractor(facts=[fact(owner, 'leg.pain_site', 'left calf'),
                                 fact(owner, 'symptom_onset', 'three days'),
                                 fact(owner, 'aggravating_factors', 'Walking makes it worse.'),
                                 fact(owner, 'severity', 'aches'),
                                 fact(owner, 'relieving_factors', 'Walking makes it worse.'),
                                 fact(owner, 'symptom_onset_character', 'Suddenly')])
    pipeline.organize_baseline(state, extraction=extractor)
    slots = state['concerns'][0]['slots']
    assert slots['leg.pain_site']['value'] == 'left calf'
    assert slots['aggravating_factors']['value'] == 'Walking makes it worse.'
    assert slots['symptom_onset_character']['status'] == 'MISSING'
    assert slots['severity']['status'] == 'UNCERTAIN'
    assert slots['relieving_factors']['status'] == 'SKIPPED'
    assert slots['leg.pain_site']['evidence']['source'] == 'saved_baseline_form'
    assert state['stage'] == 'baseline' and not state['baseline']['completed']
    assert state['_followup']['rounds_created'] == 0 and not state['_followup']['asked_targets']
    pipeline.organize_baseline(state, extraction=extractor)
    assert len(extractor.calls) == 1


def test_prefill_never_moves_evidence_between_concerns():
    state = forms.initialize(engine.new_intake(PATIENT, 'gpt-6-astra', ['WF-01', 'WF-02']))
    leg, back = state['concerns']
    forms.apply_baseline(state, [{'concern_id': leg['id'], 'key': 'concern_description', 'value': 'My left calf aches.'},
                                 {'concern_id': back['id'], 'key': 'concern_description', 'value': 'My lower back feels stiff.'}])
    pipeline.organize_baseline(state, extraction=Extractor(facts=[fact(back['id'], 'back.pain_site', 'left calf')]))
    assert back['slots']['back.pain_site']['status'] == 'MISSING'


def test_prefill_failure_keeps_manual_wizard_and_all_answers():
    state, owner = draft()
    forms.apply_baseline(state, [{'concern_id': owner, 'key': 'concern_description', 'value': 'A calf ache.'}])
    pipeline.organize_baseline(state, extraction=DownExtractor())
    assert state['stage'] == 'baseline' and state['status'] == 'active'
    assert state['ai_status']['mode'] == 'unavailable'
    assert state['concerns'][0]['slots']['concern_description']['value'] == 'A calf ache.'
    assert state['_followup']['rounds_created'] == 0


def test_changed_description_removes_old_derived_fact_before_refilling():
    state, owner = draft()
    forms.apply_baseline(state, [{'concern_id': owner, 'key': 'concern_description', 'value': 'My left calf aches.'}])
    pipeline.organize_baseline(state, extraction=Extractor(facts=[fact(owner, 'leg.pain_site', 'left calf')]))
    forms.apply_baseline(state, [{'concern_id': owner, 'key': 'concern_description', 'value': 'My right knee aches.'}])
    pipeline.organize_baseline(state, extraction=Extractor(facts=[fact(owner, 'leg.pain_site', 'right knee')]))
    public = routes.public_session(state)
    assert 'left calf' not in json.dumps(public['symptom_history'])
    assert 'right knee' in json.dumps(public['symptom_history'])


def test_review_and_pdf_use_snapshot_with_explicit_gaps():
    state, owner = draft()
    forms.apply_baseline(state, [{'concern_id': owner, 'key': 'leg.pain_site', 'value': 'Left calf'},
                                 {'concern_id': owner, 'key': 'severity', 'status': 'UNCERTAIN'},
                                 {'concern_id': owner, 'key': 'relieving_factors', 'status': 'SKIPPED'}], complete=True)
    pipeline.build_review(state, intelligence=Smart())
    snapshot = deepcopy(state['summary']['symptom_history'])
    assert snapshot[0]['applicable']
    statuses = {row['id']: row['status'] for row in snapshot[0]['dimensions']}
    assert statuses['L'] == 'FILLED' and statuses['S'] == 'UNCERTAIN' and statuses['R'] == 'SKIPPED'
    state['status'] = 'approved'
    state['concerns'][0]['slots']['leg.pain_site']['value'] = 'Changed after snapshot'
    assert routes.public_session(state)['symptom_history'] == snapshot
    assert routes.clinician_public_session(state)['symptom_history'] == snapshot
    pdf = report_pdf._main_document(state, None, [])
    text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert 'Your symptom story' in text and 'Not yet recorded' in text
    assert 'Chose not to answer' in text and 'Not sure' in text


def test_organize_endpoint_revision_csrf_and_saved_projection(wizard_api, monkeypatch):
    state = wizard_api.post('/api/v1/intakes', json={'consent': True, 'workflow_ids': ['WF-01']}).json()
    owner = state['concerns'][0]['id']
    url = f"/api/v1/intakes/{state['id']}"
    saved = wizard_api.put(url + '/baseline', json={'revision': state['revision'], 'answers': [
        {'concern_id': owner, 'key': 'concern_description', 'value': 'A left calf ache.'}]}).json()
    extractor = Extractor(facts=[fact(owner, 'leg.pain_site', 'left calf')])
    monkeypatch.setattr(pipeline, 'get_provider', lambda: extractor)
    body = {'revision': saved['revision'], 'locale': 'en'}
    assert wizard_api.post(url + '/baseline/organize', json=body, headers={'Origin': 'https://evil.test'}).status_code == 403
    response = wizard_api.post(url + '/baseline/organize', json=body)
    assert response.status_code == 200
    result = response.json()
    assert result['stage'] == 'baseline' and result['symptom_history'][0]['dimensions'][1]['status'] == 'FILLED'
    assert wizard_api.post(url + '/baseline/organize', json=body).status_code == 409
    assert len(extractor.calls) == 1
