"""Actual outgoing payloads keep authored prefixes reusable and patient data separate."""
import json
import logging
from copy import deepcopy

import httpx
import pytest

from app.product import assessment, engine, intelligence, prompt_cache, provider
from app.product.workflows import WORKFLOWS, SHARED_QUESTIONS, SIGNALS, question_definitions

BASE = 'https://api.openai.com/v1'


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret-not-for-logs')
    monkeypatch.setenv('OPENAI_BASE_URL', BASE)
    monkeypatch.setenv('OPENAI_PROMPT_CACHE', '1')


def completed(data, usage=None):
    return {'status': 'completed', 'usage': usage, 'output': [{'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps(data)}]}]}


def capture(monkeypatch, data):
    calls = []
    def post(url, **kwargs):
        calls.append(deepcopy(kwargs['json']))
        return httpx.Response(200, json=completed(data))
    monkeypatch.setattr(httpx, 'post', post)
    return calls


def test_extraction_prefix_is_identical_across_patients_and_keeps_complete_catalogue(monkeypatch):
    calls = capture(monkeypatch, {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': []})
    for name, text in [('patient-A-canary', 'PRIVATE left leg detail'), ('patient-B-canary', 'PRIVATE right arm detail')]:
        session = engine.new_intake({'id': name}, 'gpt-6-sol', ['WF-01'])
        provider.OpenAIProvider().extract(session, text)
    assert calls[0]['input'][0] == calls[1]['input'][0]
    assert calls[0]['input'][1] != calls[1]['input'][1]
    prefix = calls[0]['input'][0]['content'][0]
    assert prefix['prompt_cache_breakpoint'] == {'mode': 'explicit'}
    assert 'PRIVATE' not in prefix['text'] and 'patient-A-canary' not in prefix['text']
    reference = json.loads(prefix['text'].split('activation_signals):\n', 1)[1])
    expected = [{'id': w['id'], 'title': w['title'], 'description': w['description'],
                 'fields': [{'key': q['key'], 'question': q['question'], 'condition': q.get('condition')}
                            for q in question_definitions(w['id'])]} for w in WORKFLOWS]
    assert reference == {'catalogue': expected, 'session_fields': SHARED_QUESTIONS, 'activation_signals': SIGNALS}
    for body in calls:
        dynamic = json.loads(body['input'][1]['content'])
        assert not reference.keys() & dynamic['context'].keys()
        assert dynamic['CURRENT_MESSAGE'].startswith('PRIVATE')
        assert body['text']['format']['schema'] == provider.EXTRACTION_SCHEMA
        assert body['prompt_cache_options'] == {'mode': 'explicit', 'ttl': '30m'}
        assert body['store'] is False and 'instructions' not in body


@pytest.mark.parametrize('model,url,switch', [
    ('gpt-4.1', BASE, '1'), ('custom-model', BASE, '1'),
    ('gpt-6-sol', 'https://example.test/v1', '1'), ('gpt-6-sol', BASE, '0'),
])
def test_unsupported_provider_or_rollback_preserves_original_extraction(monkeypatch, model, url, switch):
    monkeypatch.setenv('OPENAI_BASE_URL', url)
    monkeypatch.setenv('OPENAI_PROMPT_CACHE', switch)
    calls = capture(monkeypatch, {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': []})
    provider.OpenAIProvider().extract(engine.new_intake({'id': 'p'}, model, ['WF-01']), 'Unchanged patient text')
    body = calls[0]
    assert 'prompt_cache_options' not in body and body['instructions'].startswith(provider._SYSTEM)
    data = json.loads(body['input'])
    assert len(data['context']['catalogue']) == 30 and data['CURRENT_MESSAGE'] == 'Unchanged patient text'


def test_dynamic_schemas_keep_allowlists_and_avoid_one_use_cache_writes(monkeypatch):
    calls = capture(monkeypatch, {'questions': [], 'overview': {'text': '', 'source_ids': []}, 'suggested_concern_ids': []})
    client = intelligence.OpenAIIntelligence()
    for target_id in ('patient_a:field', 'patient_b:field'):
        client.plan(model='gpt-6-sol', sources=[], concerns=[], targets=[{'target_id': target_id}])
    for body, target in zip(calls, ('patient_a:field', 'patient_b:field')):
        assert body['text']['format']['schema']['properties']['questions']['items']['properties']['target_id']['enum'] == [target]
        assert body['prompt_cache_options']['mode'] == 'explicit'
        assert 'prompt_cache_breakpoint' not in json.dumps(body)
        assert 'instructions' in body
    calls.clear()
    client._request('gpt-6-sol', 'translation policy', {'texts': []}, {}, 'preparation_presentation_translation', 100)
    assert 'prompt_cache_breakpoint' not in json.dumps(calls[0])


def test_synthesis_and_assessment_put_only_instructions_before_boundary(monkeypatch):
    calls = capture(monkeypatch, {})
    intelligence.OpenAIIntelligence()._request('gpt-6-sol', 'fixed policy', {'sources': ['private-source']}, {}, 'preparation_synthesis', 100)
    files = [{'type': 'input_text', 'text': 'private-context'},
             {'type': 'input_file', 'filename': 'private.pdf', 'file_data': 'data:application/pdf;base64,AAAA'},
             {'type': 'input_image', 'image_url': 'data:image/png;base64,BBBB'}]
    assessment.OpenAIAssessment()._request('gpt-6-sol', files, {}, 'provisional_clinical_assessment', 'fixed policy', 100)
    for body in calls:
        assert body['input'][0]['content'][0]['text'] == 'fixed policy'
        assert 'private' not in json.dumps(body['input'][0])
        assert 'private' in json.dumps(body['input'][1])
    assert calls[1]['input'][1]['content'] == files


def usage(incoming=3000, cached=0, written=2000, outgoing=500, **extra):
    return {'input_tokens': incoming, 'output_tokens': outgoing,
            'input_tokens_details': {'cached_tokens': cached, 'cache_write_tokens': written, **extra}}


def bill(data, model='gpt-6-sol', **body):
    return prompt_cache.usage_record({'usage': data, **body}, model=model, operation='extraction', base_url=BASE)


def test_cost_counts_writes_once_and_matches_ten_request_example():
    first = bill(usage())
    hit = bill(usage(cached=2000, written=0))
    assert first['estimated_standard_cost_usd'] == pytest.approx(.012)
    assert hit['estimated_standard_cost_usd'] == pytest.approx(.0074)
    assert first['estimated_standard_cost_usd'] + 9 * hit['estimated_standard_cost_usd'] == pytest.approx(.0786)
    mixed = bill(usage(cache_write_tokens_details={'ttl_30m_tokens': 1000, 'ttl_12h_tokens': 1000}))
    assert mixed['estimated_standard_cost_usd'] == pytest.approx(.0145)


@pytest.mark.parametrize('data,extra', [
    (usage(incoming=10), {}), (usage(cached=-1), {}), (usage(outgoing=True), {}),
    (usage(incoming=272001), {}), (usage(outgoing=10**1000), {}), (usage(), {'service_tier': 'fast'}),
    (usage(cache_write_tokens_details={'ttl_30m_tokens': 1, 'ttl_12h_tokens': 2}), {}),
    ({'input_tokens': 3000, 'output_tokens': 500}, {}),
])
def test_incomplete_or_inconsistent_usage_has_no_misleading_estimate(data, extra):
    assert bill(data, **extra)['estimated_standard_cost_usd'] is None


def test_unknown_model_has_usage_but_no_invented_price():
    assert bill(usage(), model='custom-model')['input_tokens'] == 3000
    assert bill(usage(), model='custom-model')['estimated_standard_cost_usd'] is None
    assert prompt_cache.usage_record([], model='gpt-6-sol', operation='test', base_url=BASE) is None


def test_failed_billable_attempt_is_logged_without_prompts_credentials_or_raw_response(monkeypatch, caplog):
    def post(*args, **kwargs):
        return httpx.Response(200, json={'status': 'incomplete', 'usage': usage(),
                                        'output': 'private raw response', 'id': 'private-id'})
    monkeypatch.setattr(httpx, 'post', post)
    with caplog.at_level(logging.INFO, logger='uvicorn.error.openai_usage'):
        with pytest.raises(intelligence.IntelligenceUnavailable):
            intelligence.OpenAIIntelligence()._request('gpt-6-sol', 'private prompt', {'text': 'private patient'}, {}, 'preparation_synthesis', 100)
    message = next(record.message for record in caplog.records if 'openai_usage ' in record.message)
    row = json.loads(message.split('openai_usage ', 1)[1])
    assert row['input_tokens'] == 3000 and row['cache_write_tokens'] == 2000
    assert 'private' not in message and 'test-secret' not in message
