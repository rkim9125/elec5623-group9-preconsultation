"""Isolated browser-test server. Synthetic identities; never used by start-local.sh."""
from pathlib import Path
import hashlib
import json
import os
import secrets
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
from app.product.database import init_db, get_connection
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
from app.core.main import create_app
import uvicorn
uvicorn.run(create_app(enable_legacy=False), host='127.0.0.1', port=8001, access_log=False)
