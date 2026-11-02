"""Validator counterexamples, original replay, and provider-failure recovery."""
import argparse, json, os, sys, tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT)]
from common import write_json, read_json, read_jsonl
from grade import model_output
from app.product import intelligence as ai, pipeline, provider
from app.product.database import init_db, save_intake, load_intake, get_connection
from tests.test_product_intelligence import baseline, Extractor, Smart, PATIENT
import httpx

def validators():
    rows=[]
    for i in range(4):
        dose=[5,10,20,40][i]
        tests=[('uncertainty',{'value':'I do not know whether I have medicine allergies.','status':'UNCERTAIN'},'The patient does not know whether they have medicine allergies.','The patient has no medicine allergies.'),
               ('mixed_negative',{'value':'Left knee aching. No supplements.','status':'FILLED'},'The patient reports left knee aching.','The patient takes supplements.'),
               ('laterality',{'value':['Left knee aching','Left shoulder aching','Right wrist aching','Right ankle aching'][i],'status':'FILLED'},['Left knee aching.','Left shoulder aching.','Right wrist aching.','Right ankle aching.'][i],['Right knee aching.','Right shoulder aching.','Left wrist aching.','Left ankle aching.'][i]),
               ('dose',{'value':f'Vitamin C {dose} mg','status':'FILLED'},f'Vitamin C {dose} mg.',f'Vitamin C {dose+1} mg.'),
               ('citation',{'value':'Rest helps','status':'FILLED'},'Rest helps.','Rest helps.')]
        for family,source,good,bad in tests:
            source={'id':'s1','concern_id':'c1','key':'description','label':'Description',**source}
            for valid,text in ((True,good),(False,bad)):
                entry={'text':text,'source_ids':['missing' if family=='citation' and not valid else 's1']}
                try: ai._validate_cited(entry,{'s1':source}); accepted=True; reason=None
                except ai.IntelligenceUnavailable as exc: accepted=False; reason=str(exc)
                rows.append({'id':f'{family}-{i}-{valid}','family':family,'expected_valid':valid,'source':source,'output':entry,'validator_on_accept':accepted,'validator_off_accept':True,'reason':reason})
    return rows

def replay():
    root=ROOT/'runs/live-20261028-001'; rows=[]
    for response in read_jsonl(root/'responses.jsonl'):
        if response['operation']!='synthesis': continue
        case=read_json(root/'cases'/f"{response['case_id']}.json"); data,_,_=model_output(response)
        try: ai.validate_synthesis(data,case['generation_input']['sources'],case['concerns']); accepted=True; reason=None
        except ai.IntelligenceUnavailable as exc: accepted=False; reason=str(exc)
        rows.append({'case_id':case['case_id'],'call_id':response['call_id'],'accepted':accepted,'reason':reason})
    return rows

def faults(output):
    rows=[]
    for stage in ('extraction','planning','synthesis'):
        for fault in ('timeout','429','503','invalid_json'):
            with tempfile.TemporaryDirectory(prefix='preconsult-eval-') as tmp:
                os.environ.update(PRODUCT_DB_PATH=tmp+'/eval.sqlite3',UPLOAD_DIR=tmp+'/uploads',APP_ENV='test')
                init_db()
                with get_connection() as conn: conn.execute('INSERT INTO users VALUES (?,?,?,?)',(PATIENT['id'],PATIENT['email'],'Synthetic','2026-11-02'))
                s=baseline(); original=s['concerns'][0]['slots']['concern_description']['value']; attempts=[]
                def send(*args,**kw):
                    attempts.append(fault)
                    if fault=='timeout': raise httpx.ReadTimeout('injected timeout')
                    if fault in ('429','503'): return httpx.Response(int(fault),json={'error':{'message':'synthetic failure'}})
                    return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'not json'}]}]})
                with patch('httpx.post',send):
                    if stage=='extraction': pipeline.start_followup(s,extraction=provider.OpenAIProvider(),intelligence=Smart())
                    elif stage=='planning': pipeline.start_followup(s,extraction=Extractor(),intelligence=ai.OpenAIIntelligence())
                    else: pipeline.build_review(s,intelligence=ai.OpenAIIntelligence())
                save_intake(s); loaded=load_intake(s['id']); preserved=loaded['concerns'][0]['slots']['concern_description']['value']==original
                unavailable=loaded.get('assistant',{}).get('mode')=='unavailable'
                not_live=(loaded.get('summary') or {}).get('synthesis',{}).get('status')!='live'
                if stage=='synthesis': pipeline.build_review(loaded,intelligence=Smart())
                else: pipeline.start_followup(loaded,extraction=Extractor(),intelligence=Smart()); pipeline.build_review(loaded,intelligence=Smart())
                save_intake(loaded); recovered=load_intake(s['id'])['summary']['synthesis']['status']=='live'
                rows.append({'stage':stage,'fault':fault,'injected_calls':len(attempts),'notes_preserved':preserved,'visible_unavailable':unavailable,'no_false_live_summary':not_live,'recovered_with_valid_stub':recovered,'passed':all([len(attempts)>0,preserved,unavailable,not_live,recovered])})
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    result={'validator_cases':validators(),'original_replay':replay(),'fault_cases':faults(args.output)}
    write_json(args.output/'offline.json',result)
    print(json.dumps({'validator_checks':len(result['validator_cases']),'replay_accepts':sum(x['accepted'] for x in result['original_replay']),'fault_passes':sum(x['passed'] for x in result['fault_cases'])}))
