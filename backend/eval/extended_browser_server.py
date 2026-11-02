"""Replay six actual live-run results through the real API and built UI."""
import hashlib,json,os,secrets,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
RUN=ROOT/'runs/extended-20261102'
OUT=RUN/'browser';OUT.mkdir(exist_ok=True)
os.environ.update(PRODUCT_DB_PATH=str(OUT/'isolated.sqlite3'),UPLOAD_DIR=str(OUT/'uploads'),
                  OPENAI_API_KEY='',RESEND_API_KEY='',RESEND_FROM_EMAIL='',APP_ENV='test',
                  APP_BASE_URL='http://127.0.0.1:8012',LLM_PROVIDER='fake',ENABLE_LEGACY_API='0',DOCTOR_EMAILS='')
sys.path.insert(0,str(ROOT.parent))
from app.product.database import init_db,get_connection,save_intake
from common import write_json,read_json
init_db();tokens={}
with get_connection() as conn:
    for role,email in [('patient','patient@example.test'),('doctor','doctor@example.test')]:
        uid='eval-browser-'+role;token=secrets.token_urlsafe(40);tokens[role]=token
        conn.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?)',(uid,email,'Synthetic '+role,'2026-11-02'))
        conn.execute('INSERT OR IGNORE INTO account_roles VALUES (?,?,?)',(uid,role,'2026-11-02'))
        conn.execute('INSERT INTO sessions VALUES (?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,role,time.time()+7200,time.time()))
selected=[]
for family in ('simple','multiple','uncertainty','correction','incomplete','noise'):
    candidates=[(p,read_json(p)) for p in sorted(RUN.glob('*-full-*/outcome.json'))]
    path,row=next((p,r) for p,r in candidates if r['family']==family and (p.parent/'final_state.json').exists())
    state=read_json(path.parent/'final_state.json'); state.update(id='browser-'+family,patient_id='eval-browser-patient',patient_email='patient@example.test',patient_name='Synthetic patient',status='review',doctor_email=None,shared_at=None)
    state.pop('revision',None);state['summary'].pop('approved_at',None);state['summary'].pop('approved_version',None)
    save_intake(state);selected.append({'id':state['id'],'family':family,'source_trial':row['id'],'delivery':row['delivery']})
write_json(OUT/'tokens.json',tokens);write_json(OUT/'selected.json',selected)
from app.core.main import create_app
import uvicorn
uvicorn.run(create_app(),host='127.0.0.1',port=8012,log_level='warning')
