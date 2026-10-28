"""Latency settings stay explicit without changing a selected model."""
import json
import httpx
import pytest

from app.product import config, provider, intelligence, assessment, engine


@pytest.mark.parametrize('model,careful,expected', [
    ('gpt-6-sol', False, {'reasoning': {'effort': 'low'}}),
    ('gpt-6-sol', True, {'reasoning': {'effort': 'medium'}}),
    ('gpt-6-astra', False, {}),
    ('explicit-custom-model', True, {}),
])
def test_reasoning_policy_preserves_other_models(model, careful, expected):
    assert config.response_reasoning(model, careful=careful) == expected


def test_sol_uses_fast_extraction_and_careful_final_outputs(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-secret')
    requests = []
    data = {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': []}
    def post(url, **kwargs):
        requests.append(kwargs['json'])
        return httpx.Response(200, json={'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(data)}]}]})
    monkeypatch.setattr(httpx, 'post', post)
    provider.OpenAIProvider().extract(engine.new_intake({'id': 'synthetic'}, 'gpt-6-sol', ['WF-01']), 'A leg ache')
    client = intelligence.OpenAIIntelligence()
    client._request('gpt-6-sol', 'synthetic', {}, {}, 'preparation_followup_batch', 100)
    client._request('gpt-6-sol', 'synthetic', {}, {}, 'preparation_synthesis', 100)
    assessment.OpenAIAssessment()._request('gpt-6-sol', [], {}, 'assessment', 'synthetic', 100)
    assert [r['reasoning']['effort'] for r in requests] == ['low', 'low', 'medium', 'medium']
    assert all(r['model'] == 'gpt-6-sol' and r['store'] is False and not r.get('tools') for r in requests)
