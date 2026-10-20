"""Locale contracts for generated reports and complete PDF exports. Synthetic only."""
from copy import deepcopy
from io import BytesIO
from string import Formatter
import hashlib

from fastapi import HTTPException
from pypdf import PdfReader
import pytest

from app.product import assessment, report_pdf
from app.product.locales import translate_text
from app.product.report_copy import COPY, REPORT_LOCALIZATION_VERSION, report_text
from .test_product_assessment import valid_report, report_app
from .test_product_report_pdf import patient_record

SENTENCES = {
    'en': 'Reported discomfort needs clinical review; its cause remains uncertain.',
    'zh-CN': '患者报告腿部不适，仍需医生评估，原因尚不确定。',
    'zh-TW': '患者報告腿部不適，仍需醫師評估，原因尚不確定。',
    'ko': '환자가 다리 불편감을 보고했으며 원인이 불확실하여 의료진 평가가 필요합니다.',
    'ja': '患者は脚の不快感を報告しています。原因は不明で、医師による評価が必要です。',
}


def context_for(locale):
    return {'locale': locale, 'sources': [{'id': 'source-1', 'concern_id': 'c1', 'key': 'current_medications',
             'value': 'Amlodipine 5 mg', 'status': 'FILLED'}], 'attachments': []}


def localized_report(context):
    result = valid_report(context)
    locale = context.get('locale', 'en')
    def localize(value):
        if isinstance(value, str):
            return SENTENCES[locale]
        if isinstance(value, list):
            return [localize(item) for item in value]
        if isinstance(value, dict):
            return {key: item if key in {'source_ids', 'attachment_id', 'filename', 'status', 'urgency'} else localize(item)
                    for key, item in value.items()}
        return value
    result = localize(result)
    result['possible_diagnoses'][0]['name'] = translate_text('Leg pain', locale)
    return result


@pytest.mark.parametrize('locale', list(COPY))
def test_report_copy_is_complete_and_placeholders_match(locale):
    assert set(COPY[locale]) == set(COPY['en'])
    for key, english in COPY['en'].items():
        fields = lambda text: {name for _, name, _, _ in Formatter().parse(text) if name}
        assert fields(COPY[locale][key]) == fields(english), key


@pytest.mark.parametrize('locale', list(COPY))
def test_every_generated_report_field_uses_patient_language_and_local_limits(locale):
    context = context_for(locale)
    result = assessment._validate(localized_report(context), context)
    assert result['possible_diagnoses'][0]['name'] == translate_text('Leg pain', locale)
    assert result['limitations'][:2] == [report_text(locale, 'disclaimer'), report_text(locale, 'imaging_limitation')]
    assert result['overview']['source_ids'] == ['source-1']
    if locale != 'en':
        assert assessment.DISCLAIMER not in result['limitations']


@pytest.mark.parametrize('locale', ['zh-CN', 'zh-TW', 'ko', 'ja'])
def test_wrong_language_diagnosis_or_bullet_is_not_saved(locale):
    context = context_for(locale)
    result = localized_report(context)
    result['possible_diagnoses'][0]['name'] = 'Possible muscle strain'
    with pytest.raises(HTTPException, match='patient language'):
        assessment._validate(result, context)
    result = localized_report(context)
    result['next_steps'][0]['text'] = 'Discuss symptoms with your clinician.'
    with pytest.raises(HTTPException, match='patient language'):
        assessment._validate(result, context)


def test_provider_retries_once_from_same_evidence_when_language_is_wrong(monkeypatch):
    context = context_for('zh-CN')
    captures = []
    expected = localized_report(context)
    def request(self, model, content, schema, name, prompt, max_output):
        captures.append((model, deepcopy(content), prompt))
        return valid_report(context) if len(captures) == 1 else expected
    monkeypatch.setattr(assessment.OpenAIAssessment, '_request', request)
    actual = assessment.OpenAIAssessment().generate(model='synthetic-model', context=context, files=[])
    assert actual == expected and len(captures) == 2
    assert captures[0][:2] == captures[1][:2]
    assert 'Simplified Chinese' in captures[0][2]
    assert 'diagnosis names' in captures[0][2]
    assert 'previous attempt used the wrong language' in captures[1][2]


def test_repeated_wrong_language_is_bounded_and_never_saved(monkeypatch):
    context = context_for('ko')
    calls = []
    def request(self, *args):
        calls.append(args)
        return valid_report(context)
    monkeypatch.setattr(assessment.OpenAIAssessment, '_request', request)
    result = assessment.OpenAIAssessment().generate(model='synthetic-model', context=context, files=[])
    assert len(calls) == 2
    with pytest.raises(HTTPException, match='patient language'):
        assessment._validate(result, context)


def test_summary_choice_labels_translate_but_free_text_and_drug_identity_do_not():
    value = report_pdf._summary_value({'key': 'functional_impact',
        'value': 'Selected options:\n- Walking\n\nAdditional details:\nMY ORIGINAL WORDS 141/88 mmHg'}, 'zh-CN')
    assert 'Walking' not in value
    assert 'MY ORIGINAL WORDS 141/88 mmHg' in value
    assert report_pdf._summary_value({'key': 'current_medications', 'value': 'Amlodipine 5 mg'}, 'zh-CN') == 'Amlodipine 5 mg'
    report = localized_report(context_for('zh-CN'))
    report['possible_diagnoses'][0]['supporting_evidence'] = ['Amlodipine 5 mg']
    assert assessment._language_valid(report, context_for('zh-CN'))


def test_patient_selected_locale_is_saved_and_doctor_cannot_override_it(report_app, monkeypatch):
    client, identity, _ = report_app
    class Provider:
        def generate(self, **kwargs):
            return localized_report(kwargs['context'])
    monkeypatch.setattr(assessment, 'get_assessment_provider', lambda: Provider())
    response = client.post('/api/v1/intakes/i1/ai-report', json={'locale': 'zh-TW'})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report['locale'] == 'zh-TW'
    assert report['localization_version'] == REPORT_LOCALIZATION_VERSION
    assert report_text('zh-TW', 'disclaimer') in report['limitations']
    from app.product import database
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary'].update(approved_at='now', approved_version=record['summary']['version'])
    database.save_intake(record)
    identity.update(id='d1', email='doctor@example.test', role='doctor')
    response = client.post('/api/v1/intakes/i1/ai-report', json={'locale': 'en'})
    assert response.status_code == 403
    assert database.load_intake('i1')['locale'] == 'zh-TW'
    # With no requested override the doctor's UI never changes patient language.
    response = client.post('/api/v1/intakes/i1/ai-report')
    assert response.status_code == 200, response.text
    assert response.json()['locale'] == 'zh-TW'


def test_approved_patient_must_review_before_changing_report_language(report_app):
    client, _, _ = report_app
    from app.product import database
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    database.save_intake(record)
    response = client.post('/api/v1/intakes/i1/ai-report', json={'locale': 'ja'})
    assert response.status_code == 409
    assert database.load_intake('i1').get('locale', 'en') == 'en'


def test_legacy_approved_report_is_preserved_and_marked_for_regeneration(report_app):
    client, _, _ = report_app
    from app.product import database
    assert client.post('/api/v1/intakes/i1/ai-report').status_code == 200
    record = database.load_intake('i1')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    record['ai_report'].pop('localization_version')
    before = deepcopy(record['ai_report'])
    result = assessment.public_report(record)
    assert result['localization_outdated'] is True
    assert result['overview'] == before['overview']
    assert record['ai_report'] == before


@pytest.mark.parametrize('locale', ['zh-CN', 'zh-TW', 'ko', 'ja'])
def test_legacy_approved_non_english_fingerprint_survives_presentation_localization(locale):
    record = patient_record()
    record.update(locale=locale, status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    record['profile_snapshot'] = {'date_of_birth': '1988-04-12', 'sex_at_birth': 'male', 'blood_group': 'O',
                                  'age_years': 38, 'age_as_of': '2026-10-21'}
    context, _, fingerprint = assessment.assessment_input(record, include_bytes=False)
    # Independently reconstruct the pre-localization provider input, whose raw
    # labels/titles were included in the persisted report fingerprint.
    legacy = deepcopy(context)
    owners = {'session': record['shared_slots'], **{c['id']: c['slots'] for c in record['concerns']}}
    legacy_profile_labels = {'profile.date_of_birth': 'Date of birth (patient reported)',
        'profile.sex_at_birth': 'Sex at birth (patient reported)', 'profile.blood_group': 'Blood group (patient reported)',
        'profile.age_at_preparation': 'Age at preparation (calculated from patient-reported date of birth)'}
    for source in legacy['sources']:
        slot = owners.get(source['concern_id'], {}).get(source['key'])
        source['label'] = str(slot.get('label') or source['key'])[:240] if slot else legacy_profile_labels[source['key']]
    legacy['concerns'] = [{key: concern[key] for key in ['id', 'title', 'workflow_id']} for concern in record['concerns']]
    old_fingerprint = hashlib.sha256(assessment._canonical(legacy)).hexdigest()
    assert fingerprint == old_fingerprint
    assert context['concerns'][0]['title'] == translate_text('Leg pain', locale)
    assert context['concerns'] != legacy['concerns']
    record['ai_report'] = {**localized_report(context), 'status': 'ready', 'input_fingerprint': old_fingerprint}
    before = deepcopy(record)
    report = assessment.public_report(record)
    assert report is not None and report['localization_outdated'] is True
    assert report['overview'] == record['ai_report']['overview']
    # Patient and clinician projection must neither invalidate nor mutate it.
    from app.product import routes
    assert routes.public_session(record)['ai_report'] == report
    assert routes.clinician_public_session(record)['ai_report'] == report
    assert record == before
    for change in ['fact', 'status', 'profile', 'title', 'locale', 'summary']:
        changed = deepcopy(record)
        if change == 'fact': changed['concerns'][0]['slots']['location']['value'] = 'Right knee'
        elif change == 'status': changed['concerns'][0]['slots']['location']['status'] = 'UNCERTAIN'
        elif change == 'profile': changed['profile_snapshot']['blood_group'] = 'A'
        elif change == 'title': changed['concerns'][0]['title'] = 'A different concern'
        elif change == 'locale': changed['locale'] = 'en'
        else: changed['summary']['text'] = 'A corrected summary'
        assert assessment.public_report(changed) is None, change


@pytest.mark.parametrize('locale', list(COPY))
def test_pdf_localizes_fixed_labels_disease_name_and_preserves_original_evidence(locale):
    record = patient_record()
    record.update(locale=locale, title='Leg pain')
    record['summary']['sections'][0]['title'] = 'Leg pain'
    record['summary']['sections'][0]['entries'][0]['value'] = 'ORIGINAL PATIENT WORDING 141/88 mmHg'
    context = context_for(locale)
    report = assessment._validate(localized_report(context), context)
    report.update(locale=locale, status='ready', model='synthetic-model', generated_at='2026-10-21', summary_version=3)
    pdf = PdfReader(BytesIO(report_pdf._main_document(record, report, [])))
    text = '\n'.join(page.extract_text() for page in pdf.pages)
    # Each is a real rendered heading or status, not hidden metadata.
    for key in ['ai_heading', 'diagnoses', 'care', 'uncertain', 'summary', 'source_heading', 'appendix', 'private']:
        assert report_text(locale, key) in text, key
    assert translate_text('Leg pain', locale) in text
    assert 'ORIGINAL PATIENT WORDING 141/88 mmHg' in text
    assert '讨论腿痛 & questions <not markup>' in text
    if locale != 'en':
        assert 'AI diagnosis & consultation guidance' not in text
        assert 'Current source information' not in text
        assert 'Leg pain' not in text
    assert len(pdf.pages) >= 2


@pytest.mark.parametrize('kind', ['summary', 'assessment'])
def test_pdf_rejects_mixed_language_generated_artifacts(kind, monkeypatch):
    record = patient_record()
    record['locale'] = 'ja'
    report = None
    if kind == 'summary':
        record['summary']['synthesis'] = {'status': 'live', 'locale': 'en', 'patient_overview': []}
    else:
        report = {'locale': 'en', 'localization_outdated': True}
    monkeypatch.setattr(assessment, 'public_report', lambda session: report)
    with pytest.raises(HTTPException, match='selected patient language'):
        report_pdf.create_pdf(record)


def test_japanese_and_korean_fallback_fonts_cover_script(monkeypatch):
    monkeypatch.setattr(report_pdf, '_UNICODE_FONT', None)
    assert 'HeiseiMin-W3' in report_pdf._markup('ひらがなとカタカナ')
    assert 'HYSMyeongJo-Medium' in report_pdf._markup('한국어')
    assert 'STSong-Light' in report_pdf._markup('患者')
