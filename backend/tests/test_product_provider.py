"""OpenAI request boundaries and safe provider errors, with HTTP mocked."""
import json
from types import SimpleNamespace
import httpx
import pytest
from app.product import provider
from app.product.engine import new_intake

@pytest.fixture
def settings(monkeypatch):
    value=SimpleNamespace(openai_api_key='synthetic-test-secret',openai_base_url='https://api.openai.com/v1')
    monkeypatch.setattr(provider,'get_settings',lambda:value)
    return value

def session():return new_intake({'id':'synthetic'},'gpt-6-sol',['WF-01'])

@pytest.mark.parametrize('status,fragment',[(401,'rejected access'),(403,'rejected access'),(404,'unavailable for this project'),(429,'quota or rate limit'),(500,'error (500)')])
def test_http_failures_are_actionable_without_secret_or_raw_body(monkeypatch,settings,status,fragment):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:httpx.Response(status,json={'error':'synthetic-test-secret patient-data'}))
    with pytest.raises(provider.ProviderUnavailable) as err:provider.OpenAIProvider().extract(session(),'Synthetic patient input')
    assert fragment in str(err.value)
    assert 'synthetic-test-secret' not in str(err.value) and 'patient-data' not in str(err.value)

def test_request_uses_exact_selected_model_responses_strict_schema_no_storage(monkeypatch,settings):
    captured={}
    result={'new_concerns':[],'facts':[],'signals':[],'items':[],'priority_order':[],'needs_clarification':False,'correction_complete':True}
    def post(url,**kwargs):
        captured.update(url=url,**kwargs)
        return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(result)}]}]})
    monkeypatch.setattr(provider.httpx,'post',post)
    state=session();state['model']='gpt-5.6-sol'
    assert provider.OpenAIProvider().extract(state,'Synthetic test')==result
    assert captured['url']=='https://api.openai.com/v1/responses'
    assert captured['json']['model']=='gpt-5.6-sol' and captured['json']['store'] is False
    assert captured['json']['text']['format']['strict'] is True
    assert 'synthetic-test-secret' not in json.dumps(captured['json'])

@pytest.mark.parametrize('response',[{'status':'incomplete','output':[]},{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'not json'}]}]},{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'[]'}]}]}])
def test_incomplete_or_malformed_output_is_never_accepted(monkeypatch,settings,response):
    monkeypatch.setattr(provider.httpx,'post',lambda *a,**k:httpx.Response(200,json=response))
    with pytest.raises(provider.ProviderUnavailable):provider.OpenAIProvider().extract(session(),'Synthetic message')

def test_missing_key_and_timeout_are_honest_errors(monkeypatch,settings):
    settings.openai_api_key=''
    with pytest.raises(provider.ProviderUnavailable,match='not configured'):provider.OpenAIProvider().extract(session(),'Synthetic')
    settings.openai_api_key='synthetic-test-secret'
    def timeout(*a,**k):raise httpx.ReadTimeout('synthetic')
    monkeypatch.setattr(provider.httpx,'post',timeout)
    with pytest.raises(provider.ProviderUnavailable,match='timed out'):provider.OpenAIProvider().extract(session(),'Synthetic')
