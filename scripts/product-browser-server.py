"""Isolated browser-test server. Synthetic identities; never used by start-local.sh."""
from pathlib import Path
import hashlib
import json
import os
import secrets
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / '.local/browser-test'
TEST.mkdir(parents=True, exist_ok=True, mode=0o700)
# This harness always uses an isolated DB, never the real application data.
os.environ.update(PRODUCT_DB_PATH=str(TEST / 'test.sqlite3'), UPLOAD_DIR=str(TEST / 'uploads'),
                  OPENAI_API_KEY='', RESEND_API_KEY='', RESEND_FROM_EMAIL='', APP_ENV='local',
                  APP_BASE_URL='http://127.0.0.1:8001', DOCTOR_EMAILS='doctor@example.test', ENABLE_LEGACY_API='0')
sys.path.insert(0, str(ROOT / 'backend'))
from app.product.database import init_db, get_connection, save_intake
init_db()
tokens = {}
with get_connection() as conn:
    conn.execute('DELETE FROM intakes')
    conn.execute('DELETE FROM sessions')
    conn.execute('DELETE FROM rate_limits')
    for role, email, name in [('patient','patient@example.test','Alex Morgan'),('doctor','doctor@example.test','Jamie Taylor')]:
        uid = 'browser-test-' + role
        conn.execute('INSERT OR IGNORE INTO users (id,email,name,created_at) VALUES (?,?,?,?)', (uid,email,name,'2026-10-05T00:00:00Z'))
        token = secrets.token_urlsafe(48)
        conn.execute('INSERT INTO sessions VALUES (?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),uid,role,time.time()+3600,time.time()))
        tokens[role] = token
path = TEST / 'sessions.json'
path.write_text(json.dumps(tokens))
path.chmod(0o600)
# Optional genuine OpenAI output produced by the separate, explicit synthetic
# smoke test. Browser tests still make no external calls and never use real users.
live_fixture = ROOT / '.local/v2-live-smoke.json'
if live_fixture.exists():
    seed = json.loads(live_fixture.read_text())
    if seed.get('patient_id') != 'synthetic-v2-smoke':
        raise RuntimeError('Only the synthetic v2 smoke record may seed this fixture.')
    seed.update(id='browser-live-summary', patient_id='browser-test-patient',
                patient_email='patient@example.test', patient_name='Alex Morgan',
                title='Appointment preparation · live AI example', status='review',
                doctor_email=None, shared_at=None, reviewed_at=None, reviewed_by=None)
    seed.pop('revision', None)
    seed['attachments'] = []
    if seed.get('summary'):
        seed['summary'].pop('approved_at', None)
        seed['summary'].pop('approved_version', None)
    save_intake(seed)
# The assessment smoke uses only synthetic data and generated attachments. Copy
# those files into this isolated upload root so PDF browser checks stay local.
assessment_fixture = ROOT / '.local/assessment-smoke/session.json'
if assessment_fixture.exists():
    seed = json.loads(assessment_fixture.read_text())
    if seed.get('patient_id') != 'synthetic-assessment-smoke':
        raise RuntimeError('Only a synthetic assessment may seed this fixture.')
    seed.update(id='browser-assessment', patient_id='browser-test-patient',
                patient_email='patient@example.test', patient_name='Alex Morgan (synthetic)',
                status='review', doctor_email=None, shared_at=None,
                reviewed_at=None, reviewed_by=None)
    seed.pop('revision', None)
    seed['summary'].pop('approved_at', None)
    seed['summary'].pop('approved_version', None)
    upload_root = ROOT / '.local/assessment-smoke/uploads'
    target_dir = TEST / 'uploads' / 'browser-assessment'
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    for attachment in seed.get('attachments', []):
        source = Path(attachment['storage_path']).resolve()
        if not source.is_relative_to(upload_root.resolve()):
            raise RuntimeError('Assessment fixture file is outside the synthetic upload root.')
        target = target_dir / source.name
        shutil.copy2(source, target)
        target.chmod(0o600)
        attachment['storage_path'] = str(target)
        attachment['url'] = f"/api/v1/intakes/browser-assessment/attachments/{attachment['id']}"
    from app.product.assessment import public_report
    if not public_report(seed):
        raise RuntimeError('Synthetic assessment is not current after fixture copying.')
    save_intake(seed)
from app.core.main import create_app
import uvicorn
uvicorn.run(create_app(enable_legacy=False), host='127.0.0.1', port=8001, access_log=False)
