"""Harness invariants, not new product behavior tests."""
import json
import sys
from pathlib import Path
from copy import deepcopy
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from extended_corpus import cases, ATTACKS
from extended_run import patient_answer, answer_key, prose, run_generic
from extended_offline import validators

def test_corpus_and_secondary_timeline_are_fixed():
    rows=cases()
    assert len(rows)==len({c['case_id'] for c in rows})==24
    assert all(sum(c['family']==f for c in rows)==4 for f in {c['family'] for c in rows})
    c=next(c for c in rows if c['family']=='multiple')
    assert patient_answer(c,'symptom_duration',secondary=True)=='Two weeks.'
    assert patient_answer(c,'nonexistent') is None
    assert len(ATTACKS)==8

def test_generic_never_gets_gold_or_hidden_answers(monkeypatch):
    import extended_run
    calls=[]
    def request(prompt,data,schema,name):
        calls.append(deepcopy(data))
        return {'questions':['How severe is it?']} if name=='baseline_questions' else {'summary':'A factual summary.'}
    monkeypatch.setattr(extended_run,'generic_request',request)
    c=cases()[0]; c['required'].append('SECRET_GOLD');c['answers']['never_asked']='SECRET_ANSWER'
    out={};run_generic(c,out)
    encoded=json.dumps(calls)
    assert 'SECRET_GOLD' not in encoded and 'SECRET_ANSWER' not in encoded
    assert out['questions'][0]['answer']=='It is mild.'

def test_unknown_output_is_not_counted_as_delivered():
    assert prose({'status':'unavailable','patient_overview':[{'text':'Not an AI success'}]})==''
    assert answer_key('How long does each episode last?')=='symptom_episode_duration'
    assert answer_key('Did it start suddenly or gradually?')=='symptom_onset_character'

def test_validator_bank_exposes_both_error_directions():
    rows=validators()
    assert len(rows)==40
    assert sum(r['expected_valid'] for r in rows)==20
    assert any(r['expected_valid'] and not r['validator_on_accept'] for r in rows)
    assert any(not r['expected_valid'] and r['validator_on_accept'] for r in rows)

def test_credit_exhaustion_stops_next_trial_before_network(tmp_path):
    import httpx,time
    from extended_run import Capture
    from capture import BudgetExceeded
    (tmp_path/'manifest.json').write_text('{}')
    first=tmp_path/'first';first.mkdir();second=tmp_path/'second';second.mkdir()
    a=Capture(first,base_url='https://api.openai.com/v1',live=True,max_calls=2,max_reserved_output_tokens=100)
    b=Capture(second,base_url='https://api.openai.com/v1',live=True,max_calls=2,max_reserved_output_tokens=100)
    request=httpx.Request('POST','https://api.openai.com/v1/responses',json={'max_output_tokens':1})
    with a.job(case_id='test',job_id='first',operation='test'):
        record=a.before(request,request.read())
        response=httpx.Response(429,json={'error':{'code':'credit_balance_exhausted'}})
        a.after(record,response,response.content,time.perf_counter())
    with b.job(case_id='test',job_id='second',operation='test'),pytest.raises(BudgetExceeded):b.before(request,request.read())
    assert b.calls==0
