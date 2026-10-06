"""Assessment authorization, source isolation, provider contracts and stale-output tests."""
from copy import deepcopy
from io import BytesIO
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
import pytest

from app.product import assessment, database, media, routes
from app.product.auth import require_user


def valid_report(context):
    source = next(s['id'] for s in context['sources'] if s['concern_id'] != 'attachments')
    cite = lambda text: {'text': text, 'source_ids': [source]}
    return {
        'overview': cite('Patient reports leg discomfort; the cause remains uncertain without examination.'),
        'possible_diagnoses': [{'name': 'Possible muscle strain', 'explanation': 'Activity-related discomfort may fit strain, but this is unconfirmed.',
            'supporting_evidence': ['Reported discomfort'], 'uncertainties': ['No examination or verified imaging'], 'source_ids': [source]}],
        'care_guidance': {'urgency': 'uncertain', 'timeframe': 'Seek prompt in-person advice if pain is severe or worsening.',
                          'reason': 'Severity and examination findings remain uncertain.', 'source_ids': [source]},
        'next_steps': [cite('Discuss the timeline, activity and medication history with a clinician.')],
        'red_flags': [{'text': 'If severe pain or sudden difficulty breathing develops, seek emergency help.', 'source_ids': []}],
        'missing_information': [cite('An examination has not been performed.')],
        'attachment_reviews': [{'attachment_id': f['id'], 'filename': f['filename'], 'status': 'limited',
            'findings': 'The uploaded file is available for clinician review.', 'limitations': 'No diagnostic image interpretation.',
            'source_ids': ['attachment_' + f['id']]} for f in context['attachments']],
        'limitations': ['This is a provisional AI suggestion; examination is needed.'],
    }


@pytest.fixture
def report_app(tmp_path, monkeypatch):
    monkeypatch.setenv('PRODUCT_DB_PATH', str(tmp_path / 'report.sqlite3'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('APP_BASE_URL', 'http://testserver')
    monkeypatch.setenv('DOCTOR_EMAILS', 'doctor@example.test')
    monkeypatch.setenv('OPENAI_API_KEY', '')
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO users VALUES ('p1','patient@example.test','Patient','now')")
    record = {'id': 'i1', 'patient_id': 'p1', 'status': 'review', 'consent': True, 'model': 'gpt-6-sol',
              'summary': {'version': 1, 'text': 'Current patient-reported leg discomfort.'}, 'attachments': [],
              'shared_slots': {'goal': {'status': 'FILLED', 'value': 'Discuss leg discomfort', 'label': 'Goal',
                  'history': ['PRIVATE OLD HISTORY'], 'evidence': {'text': 'PRIVATE EVIDENCE'}}},
              'concerns': [{'id': 'c1', 'title': 'Leg discomfort', 'workflow_id': 'leg_pain', 'slots': {
                  'location': {'status': 'FILLED', 'value': 'Left lower leg', 'label': 'Location'},
                  'private': {'status': 'SKIPPED', 'value': 'PRIVATE REFUSAL', 'label': 'Private topic'},
                  'hidden': {'status': 'FILLED', 'value': 'PRIVATE HIDDEN', 'exclude_from_handoff': True}}}],
              'messages': [{'text': 'PRIVATE CONVERSATION'}]}
    database.save_intake(record)
    identity = {'id': 'p1', 'email': 'patient@example.test', 'role': 'patient'}
    captures = []
    class Provider:
        def generate(self, **kwargs):
            captures.append(kwargs)
            return valid_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: Provider())
    app = FastAPI()
    app.include_router(assessment.router, prefix='/api/v1')
    app.include_router(media.router, prefix='/api/v1')
    app.dependency_overrides[require_user] = lambda: identity
    client = TestClient(app, headers={'Origin': 'http://testserver'})
    return client, identity, captures


def upload_documents(client):
    png = BytesIO()
    Image.new('RGB', (12, 20), 'white').save(png, format='PNG')
    pdf = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.write(pdf)
    for filename, data, media_type in [('image.png', png.getvalue(), 'image/png'), ('record.pdf', pdf.getvalue(), 'application/pdf')]:
        response = client.post('/api/v1/intakes/i1/attachments', files={'file': (filename, data, media_type)})
        assert response.status_code == 201, response.text
    record = database.load_intake('i1')
    record.update(status='review', summary={'version': 2, 'text': 'Current patient-reported leg discomfort.'})
    database.save_intake(record)


def test_report_uses_current_projected_sources_only_and_preserves_summary(report_app):
    client, _, captures = report_app
    before = deepcopy(database.load_intake('i1')['summary'])
    response = client.post('/api/v1/intakes/i1/ai-report')
    assert response.status_code == 200, response.text
    report = response.json()
    assert report['status'] == 'ready' and report['summary_version'] == 1
    assert assessment.DISCLAIMER in report['limitations']
    assert assessment.IMAGING_LIMITATION in report['limitations']
    assert 'PRIVATE' not in json.dumps(captures[0]['context'])
    assert 'storage_path' not in json.dumps(report)
    saved = database.load_intake('i1')
    assert saved['summary'] == before
    assert saved['ai_activity'][-1]['operation'] == 'assessment'
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] == report
    assert routes.public_session(saved)['ai_report'] == report


def test_all_supported_attachments_reach_provider_with_actual_bytes(report_app):
    client, _, captures = report_app
    upload_documents(client)
    response = client.post('/api/v1/intakes/i1/ai-report')
    assert response.status_code == 200, response.text
    files = captures[-1]['files']
    assert len(files) == 2 and files[0]['data'].startswith(b'\x89PNG') and files[1]['data'].startswith(b'%PDF')
    assert len(response.json()['attachment_reviews']) == 2
    assert all('storage_path' not in f for f in files)


def test_file_change_or_missing_file_immediately_invalidates_report(report_app):
    client, _, _ = report_app
    upload_documents(client)
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 200
    record = database.load_intake('i1')
    path = media.attachment_path(record['attachments'][0])
    original = path.read_bytes()
    path.write_bytes(original + b'changed')
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] is None
    path.write_bytes(original)
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] is not None
    path.unlink()
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] is None
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 404


def test_approval_does_not_invalidate_identical_clinical_input(report_app):
    client, identity, _ = report_app
    report = client.post('/api/v1/intakes/i1/ai-report').json()
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary'].update(approved_at='now', approved_version=1)
    database.save_intake(record)
    identity.update(id='d1', email='doctor@example.test', role='doctor')
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] == report
    assert routes.clinician_public_session(record)['ai_report'] == report
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 200
    record = database.load_intake('i1')
    record.update(status='withdrawn', doctor_email=None)
    database.save_intake(record)
    assert client.get('/api/v1/intakes/i1/ai-report').status_code == 404
    identity.update(id='p1', email='patient@example.test', role='patient')
    assert client.get('/api/v1/intakes/i1/ai-report').json()['ai_report'] is None


@pytest.mark.parametrize('identity', [
    {'id': 'p2', 'email': 'other@example.test', 'role': 'patient'},
    {'id': 'd1', 'email': 'doctor@example.test', 'role': 'doctor'},
    {'id': 'd2', 'email': 'other-doctor@example.test', 'role': 'doctor'},
])
def test_unapproved_or_unrelated_users_cannot_read_or_generate(report_app, identity):
    client, actual, captures = report_app
    actual.update(identity)
    assert client.get('/api/v1/intakes/i1/ai-report').status_code == 404
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 404
    assert not captures


@pytest.mark.parametrize('change', [
    {'consent': False}, {'status': 'interrupted'}, {'status': 'active'},
    {'summary': {'version': 1, 'needs_reconciliation': True}}, {'summary': None},
])
def test_unready_record_rejected_without_call(report_app, change):
    client, _, captures = report_app
    record = database.load_intake('i1')
    record.update(change)
    database.save_intake(record)
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 409
    assert not captures


def test_wrong_origin_rejected(report_app):
    client, _, captures = report_app
    assert client.post('/api/v1/intakes/i1/ai-report', headers={'Origin': 'https://attacker.test'}).status_code == 403
    assert not captures


@pytest.mark.parametrize('mutator', [
    lambda s: s['shared_slots']['goal'].update(value='Changed concern'),
    lambda s: s.update(consent=False),
    lambda s: s.update(status='withdrawn', doctor_email=None),
    lambda s: s.update(summary={'version': 2, 'text': 'Corrected summary'}),
])
def test_record_change_during_ai_never_commits_outdated_result(report_app, monkeypatch, mutator):
    client, _, _ = report_app
    class RaceProvider:
        def generate(self, **kwargs):
            database.mutate_intake('i1', mutator)
            return valid_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: RaceProvider())
    response = client.post('/api/v1/intakes/i1/ai-report')
    assert response.status_code == 409, response.text
    assert 'ai_report' not in database.load_intake('i1')


def test_clinician_sharing_withdrawn_during_generation_returns_no_report(report_app, monkeypatch):
    client, identity, _ = report_app
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    database.save_intake(record)
    identity.update(id='d1', email='doctor@example.test', role='doctor')
    class RaceProvider:
        def generate(self, **kwargs):
            database.mutate_intake('i1', lambda current: current.update(status='withdrawn', doctor_email=None))
            return valid_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: RaceProvider())
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 404
    assert 'ai_report' not in database.load_intake('i1')


@pytest.mark.parametrize('mutator', [
    lambda r: r['overview'].update(source_ids=['invented-source']),
    lambda r: r['overview'].update(text='It is safe to wait.'),
    lambda r: r.update(possible_diagnoses=[{'name': 'Definitely broken'}]),
    lambda r: r.update(overview={'text': 'x', 'source_ids': 'wrong'}),
    lambda r: r.update(attachment_reviews=[]),
    lambda r: r.update(extra_untrusted_field='bad'),
])
def test_invalid_or_incomplete_output_never_saved(report_app, monkeypatch, mutator):
    client, _, _ = report_app
    upload_documents(client)
    class BadProvider:
        def generate(self, **kwargs):
            result = valid_report(kwargs['context'])
            mutator(result)
            return result
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: BadProvider())
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 502
    assert 'ai_report' not in database.load_intake('i1')


def test_stale_report_removed_on_persist_and_attachment_change(report_app):
    client, _, _ = report_app
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 200
    record = database.load_intake('i1')
    record['shared_slots']['goal']['value'] = 'New goal'
    assert routes.persist(record)['ai_report'] is None
    assert 'ai_report' not in database.load_intake('i1')
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 200
    upload_documents(client)
    assert 'ai_report' not in database.load_intake('i1')


def test_provider_sends_strict_schema_and_both_media_types(report_app, monkeypatch):
    client, _, _ = report_app
    upload_documents(client)
    context, files, _ = assessment.assessment_input(database.load_intake('i1'))
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    calls = []
    class Response:
        status_code = 200
        def json(self):
            return {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(valid_report(context))}]}]}
    def post(*args, **kwargs):
        calls.append(kwargs['json'])
        return Response()
    monkeypatch.setattr(assessment.httpx, 'post', post)
    result = assessment.OpenAIAssessment().generate(model='gpt-6-sol', context=context, files=files)
    assert result['attachment_reviews']
    body = calls[0]
    assert body['store'] is False and body['model'] == 'gpt-6-sol'
    assert body['text']['format']['strict'] is True
    content = body['input'][0]['content']
    assert len([p for p in content if p['type'] == 'input_image']) == 1
    assert len([p for p in content if p['type'] == 'input_file']) == 1
    assert 'PRIVATE' not in json.dumps(body)


@pytest.mark.parametrize('body', [
    {'status': 'incomplete', 'output': []},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'Cannot help'}]}]},
    {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'not json'}]}]},
])
def test_provider_refusal_or_truncation_is_honest_failure(report_app, monkeypatch, body):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-test-key')
    class Response:
        status_code = 200
        def json(self): return body
    monkeypatch.setattr(assessment.httpx, 'post', lambda *args, **kwargs: Response())
    context, files, _ = assessment.assessment_input(database.load_intake('i1'))
    with pytest.raises(assessment.HTTPException) as error:
        assessment.OpenAIAssessment().generate(model='gpt-6-sol', context=context, files=files)
    assert error.value.status_code == 502


def test_large_combined_uploads_read_every_file_before_synthesis(report_app, monkeypatch):
    client, _, _ = report_app
    upload_documents(client)
    context, files, _ = assessment.assessment_input(database.load_intake('i1'))
    # Exercise threshold without allocating tens of megabytes in a unit test.
    for item in files:
        item['size_bytes'] = 20 * 1024 * 1024
    observed, syntheses = [], []
    def request(self, model, content, schema, name, prompt, max_output):
        if name == 'attachment_observations':
            metadata = json.loads(content[0]['text'])
            observed.append((metadata['id'], content[1]['type']))
            return next(row for row in valid_report(context)['attachment_reviews'] if row['attachment_id'] == metadata['id'])
        syntheses.append(content)
        return valid_report(context)
    monkeypatch.setattr(assessment.OpenAIAssessment, '_request', request)
    output = assessment.OpenAIAssessment().generate(model='gpt-6-sol', context=context, files=files)
    assert len(observed) == 2
    assert {kind for _, kind in observed} == {'input_image', 'input_file'}
    assert len(syntheses) == 1
    notes = json.loads(syntheses[0][-1]['text'])['attachment_observations']
    assert {row['attachment_id'] for row in notes} == {file['id'] for file in files}
    assert len(output['attachment_reviews']) == 2


def test_large_upload_bad_observation_aborts_without_final_synthesis(report_app, monkeypatch):
    client, _, _ = report_app
    upload_documents(client)
    context, files, _ = assessment.assessment_input(database.load_intake('i1'))
    for item in files:
        item['size_bytes'] = 20 * 1024 * 1024
    def request(self, model, content, schema, name, prompt, max_output):
        assert name == 'attachment_observations'
        row = deepcopy(valid_report(context)['attachment_reviews'][0])
        row['source_ids'] = ['made-up']
        return row
    monkeypatch.setattr(assessment.OpenAIAssessment, '_request', request)
    with pytest.raises(assessment.HTTPException) as error:
        assessment.OpenAIAssessment().generate(model='gpt-6-sol', context=context, files=files)
    assert error.value.status_code == 502


def test_same_size_attachment_changed_during_generation_rejected(report_app, monkeypatch):
    client, _, _ = report_app
    upload_documents(client)
    class RaceProvider:
        def generate(self, **kwargs):
            path = media.attachment_path(database.load_intake('i1')['attachments'][0])
            data = path.read_bytes()
            path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            return valid_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: RaceProvider())
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 409
    assert 'ai_report' not in database.load_intake('i1')


def test_clinician_allowlist_revoked_during_generation_rejected(report_app, monkeypatch):
    client, identity, _ = report_app
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    database.save_intake(record)
    identity.update(id='d1', email='doctor@example.test', role='doctor')
    class RaceProvider:
        def generate(self, **kwargs):
            monkeypatch.setenv('DOCTOR_EMAILS', '')
            return valid_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: RaceProvider())
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 404
    assert 'ai_report' not in database.load_intake('i1')


@pytest.mark.parametrize('section,text', [
    ('overview', 'The X-ray confirms a tibial fracture.'),
    ('overview', 'The CT shows intracranial bleeding.'),
    ('overview', 'The ECG indicates atrial fibrillation.'),
    ('overview', 'The MRI proves the diagnosis.'),
    ('overview', 'A fracture is confirmed by the X-ray.'),
    ('overview', 'A diagnosis was proven on the uploaded CT.'),
    ('overview', 'It is safe for the patient to wait.'),
    ('overview', 'The ultrasound reveals a blood clot.'),
    ('overview', 'The patient can wait safely.'),
    ('overview', 'You can safely delay medical review.'),
    ('overview', 'Serious conditions have been ruled out.'),
    ('overview', 'Infection is excluded.'),
    ('overview', 'The findings rule out serious disease.'),
    ('overview', 'There is nothing serious.'),
    ('overview', 'There is no need to see a doctor.'),
    ('next_steps', 'Start amoxicillin 500 mg three times daily.'),
    ('next_steps', 'Start taking amoxicillin 500 mg three times daily.'),
    ('next_steps', 'Reduce your prescribed dose.'),
    ('next_steps', 'Take 2 tablets of the antibiotic now.'),
    ('next_steps', 'Stop your anticoagulant.'),
    ('next_steps', 'Increase your insulin dose tonight.'),
    ('next_steps', 'Reduce warfarin to 2 mg daily.'),
    ('next_steps', 'Change the medication dose.'),
    ('next_steps', 'Begin prednisolone tomorrow.'),
    ('next_steps', 'Switch to ibuprofen.'),
    ('next_steps', 'You should take novelmedicine 20 mg daily.'),
    ('next_steps', 'Do not change your tablets without advice, but start amoxicillin today.'),
    ('overview', 'The X-ray does not confirm a fracture, but the CT confirms a fracture.'),
])
def test_explicit_scope_contradictions_reject_entire_report(report_app, section, text):
    context, _, _ = assessment.assessment_input(database.load_intake('i1'))
    report = valid_report(context)
    target = report['overview'] if section == 'overview' else report['next_steps'][0]
    target['text'] = text
    with pytest.raises(assessment.HTTPException) as error:
        assessment._validate(report, context)
    assert error.value.status_code == 502


@pytest.mark.parametrize('text', [
    'This X-ray does not confirm a fracture.',
    'The CT cannot confirm or exclude the cause through this service.',
    'I cannot interpret an ECG to confirm a diagnosis.',
    'The X-ray shows two views of the lower legs; specialist review is required.',
    'It is not safe to wait if severe breathing difficulty develops.',
    'There is no assurance that it is safe to wait.',
    'This is provisional guidance, not a validated triage outcome or assurance that waiting is safe.',
    'I cannot say the patient can wait safely.',
    'Serious causes cannot be ruled out from this information.',
    'These symptoms do not rule out a serious cause.',
    'The uploaded file does not establish a diagnosis.',
    'Do not change medicines without advice from your clinician.',
    "Don't stop your prescribed medication without speaking to your doctor.",
    'Never increase your medication dose yourself.',
    'Ask your clinician whether to change the medication dose.',
    'Discuss with your clinician whether to start medication.',
    'A clinician may consider changing medication after a full review.',
    'Your doctor may consider tests to rule out a fracture.',
    'A clinician may consider an X-ray to assess for fracture.',
    'Muscle strain is one possibility, but examination is needed.',
    'Start a symptom diary to discuss with your doctor.',
    'Start a sleep diary and include the current medication list.',
    'Start a sleep diary and bring a list of your medicines.',
    'Take notes about sleep, exercise and your medications.',
    'Take notes about your medication.',
    'Start a conversation about medication with your clinician.',
    'Take your medication list to the appointment.',
])
def test_negated_cautions_and_clinician_considered_options_remain_allowed(report_app, text):
    context, _, _ = assessment.assessment_input(database.load_intake('i1'))
    report = valid_report(context)
    report['overview']['text'] = text
    assessment._validate(report, context)


def test_overview_requires_citation_when_patient_evidence_exists(report_app):
    context, _, _ = assessment.assessment_input(database.load_intake('i1'))
    report = valid_report(context)
    report['overview']['source_ids'] = []
    with pytest.raises(assessment.HTTPException) as error:
        assessment._validate(report, context)
    assert error.value.status_code == 502


def test_empty_record_may_have_uncited_insufficient_information_overview(report_app):
    context, _, _ = assessment.assessment_input(database.load_intake('i1'))
    report = valid_report(context)
    context['sources'] = [{**source, 'status': 'MISSING', 'value': None} for source in context['sources']]
    report['overview'] = {'text': 'There is insufficient information to suggest a diagnosis.', 'source_ids': []}
    report['possible_diagnoses'] = []
    assessment._validate(report, context)


@pytest.mark.parametrize('filename', ['X-ray confirms fracture.pdf', 'Start amoxicillin 500 mg.pdf'])
def test_attachment_filename_is_metadata_not_generated_medical_advice(report_app, filename):
    context, _, _ = assessment.assessment_input(database.load_intake('i1'))
    context['attachments'] = [{'id': 'file1', 'filename': filename, 'media_type': 'application/pdf'}]
    context['sources'].append({'id': 'attachment_file1', 'status': 'FILLED', 'value': filename})
    report = valid_report(context)
    validated = assessment._validate(report, context)
    assert validated['attachment_reviews'][0]['filename'] == filename
