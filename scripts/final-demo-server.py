"""Isolated final-demo fixture. Synthetic identities; no external AI/email calls.

AI planning and synthesis are deterministic fixtures. All UI/API/database/access
control behaviour uses the real product implementation. Never run on port 8000.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import os
import secrets
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'presentation-final-2026-10-28'
STATE=ROOT/'.local/final-demo'
STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
os.environ.update(PYTHON_DOTENV_DISABLED='1',PRODUCT_DB_PATH=str(STATE/'test.sqlite3'),UPLOAD_DIR=str(STATE/'uploads'),
                  OPENAI_API_KEY='',RESEND_API_KEY='',RESEND_FROM_EMAIL='',APP_ENV='local',
                  APP_BASE_URL='http://127.0.0.1:8001',DOCTOR_EMAILS='',ENABLE_LEGACY_API='0',OPENAI_MODEL='gpt-6-sol')
sys.path.insert(0,str(ROOT/'backend'))
from app.product import engine,forms,pipeline,profiles
from app.product.database import init_db,get_connection,save_intake

init_db()
identities={
 'patient':dict(id='final-demo-alex',email='alex@example.test',name='Alex Morgan',role='patient'),
 'patient_b':dict(id='final-demo-maya',email='maya@example.test',name='Maya Chen',role='patient'),
 'doctor':dict(id='final-demo-doctor',email='doctor@example.test',name='Jamie Taylor',role='doctor'),
 'other_doctor':dict(id='final-demo-other-doctor',email='unassigned@example.test',name='Robin Lane',role='doctor')}
tokens={}
with get_connection() as conn:
    for table in ['intakes','sessions','rate_limits','patient_profiles']:
        conn.execute(f'DELETE FROM {table}')
    for key,user in identities.items():
        conn.execute('INSERT OR IGNORE INTO users (id,email,name,created_at) VALUES (?,?,?,?)',(user['id'],user['email'],user['name'],'2026-10-28T00:00:00Z'))
        conn.execute('INSERT INTO account_roles (user_id,role,assigned_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role',(user['id'],user['role'],'2026-10-28T00:00:00Z'))
        token=secrets.token_urlsafe(48)
        conn.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],user['role'],time.time()+7200,time.time()))
        tokens[key]=token
(STATE/'sessions.json').write_text(json.dumps(tokens));(STATE/'sessions.json').chmod(0o600)
cases=json.loads((OUT/'test-data/cases.json').read_text())['cases']

class EmptyExtractor:
    def extract(self,*args,**kwargs):
        return dict(new_concerns=[],facts=[],signals=[],items=[],priority_order=[],remove_concerns=[],remove_items=[],needs_clarification=False,correction_complete=True)

class FixtureSynthesis:
    """Cited, deterministic statements used only by this local fixture script."""
    def synthesize(self,*,sources,concerns,**kwargs):
        result=dict(patient_overview=[],clinician_brief=[],concern_summaries=[],appointment_agenda=[],uncertainties=[])
        for concern in concerns:
            source=next(s for s in sources if s['concern_id']==concern['id'] and s['key']=='concern_description')
            result['concern_summaries'].append(dict(concern_id=concern['id'],title=concern['title'],summary='Patient reports: '+source['value'],source_ids=[source['id']]))
            result['patient_overview'].append(dict(text='Patient reports: '+source['value'],source_ids=[source['id']]))
        for key in ['current_medications','appointment_goal']:
            source=next((s for s in sources if s['key']==key and s['status']=='FILLED'),None)
            if source:result['clinician_brief'].append(dict(text=source['value'],source_ids=[source['id']]))
        source=next((s for s in sources if s['status']=='UNCERTAIN' and s.get('value')),None)
        if source:result['uncertainties'].append(dict(text='Patient is unsure: '+source['value'],source_ids=[source['id']]))
        return result

def base(case,user,record_id,complete=True):
    profile=profiles.save_profile(user['id'],profiles.PatientProfileInput(**case['profile']))
    state=forms.initialize(engine.new_intake(user,'gpt-6-sol',[case['workflow_id']],title=case['title']))
    state.update(id=record_id,locale=case['locale'],profile_snapshot=profiles.snapshot_for_intake(user['id']))
    forms.apply_profile(state,profiles.prefill_answers(user['id'],profile=profile))
    concern=state['concerns'][0]
    answers=[dict(concern_id='session' if row['owner']=='session' else concern['id'],key=row['key'],value=row['value'],status=row['status']) for row in case['baseline']]
    forms.apply_baseline(state,answers,complete=complete)
    signals={'current_symptom':case['workflow_id']=='WF-01','episodes':case['workflow_id']=='WF-01','previous_actions':True,'records_available':case['workflow_id']=='WF-24','previous_consultation':case['workflow_id']=='WF-24'}
    for key,present in signals.items():concern['signals'][key]=dict(present=present,evidence='Synthetic authored fixture')
    engine._apply_conditions(state)
    return state

manifest={'mode':'Real product UI/API with synthetic DB and deterministic AI fixtures; external providers disabled','records':{}}
leg=cases[0];bp=cases[1]
for case,user,key in [(leg,identities['patient'],'leg'),(bp,identities['patient_b'],'bp')]:
    state=base(case,user,'demo-'+key+'-review')
    cid=state['concerns'][0]['id']
    for row in case['followup']:
        # Deterministic authored follow-up values; UI submission is tested below.
        if row['key'] in state['concerns'][0]['slots']:
            engine._update_slot(state['concerns'][0]['slots'][row['key']],row['value'],row['status'],{'source':'synthetic_fixture','span':row['value']})
    pipeline.build_review(state,intelligence=FixtureSynthesis(),extraction=EmptyExtractor())
    assert state['summary']['synthesis']['status']=='live',state['summary']['synthesis']
    save_intake(state)
    manifest['records'][key+'_review']=state['id']

draft=base(leg,identities['patient'],'demo-leg-draft',complete=False)
save_intake(draft);manifest['records']['leg_draft']=draft['id']

batch=base(leg,identities['patient'],'demo-leg-followup')
owner=batch['concerns'][0]['id']
questions=[]
for row in leg['followup']:
    slot=batch['concerns'][0]['slots'][row['key']]
    slot.update(status='MISSING',value=None)
    questions.append(dict(target=dict(target_id=pipeline._target_id(owner,row['key']),concern_id=owner,key=row['key'],question=row['question']),question=row['question'],rationale='This adds a detail that is not yet recorded in your preparation.',options=[dict(id=chr(65+i),label=value,value=value) for i,value in enumerate(row['choices'])]))
pipeline._publish_batch(batch,questions,'You have described both knees and how activity affects them. These remaining details help complete your appointment notes.')
save_intake(batch);manifest['records']['leg_followup']=batch['id']

zh=deepcopy(draft);zh.pop('revision',None);zh.update(id='demo-leg-zh',locale='zh-CN',title='双膝不适的就诊准备')
cid=zh['concerns'][0]['id']
forms.apply_baseline(zh,[dict(concern_id=cid,key='concern_description',value='10月21日长距离步行后，双侧膝盖前方开始酸痛，右侧更明显。上下楼时加重，坐下休息会缓解。仍能走路，但暂停了跑步。')])
save_intake(zh);manifest['records']['leg_zh']=zh['id']
(STATE/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'ready':True,'port':8001,'records':manifest['records'],'external_ai':False,'external_email':False}),flush=True)
from app.core.main import create_app
import uvicorn
uvicorn.run(create_app(enable_legacy=False),host='127.0.0.1',port=8001,access_log=False)
