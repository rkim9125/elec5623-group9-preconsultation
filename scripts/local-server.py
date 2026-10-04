"""Small local supervisor: start, stop, status. Binds loopback only."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local'
STATE.mkdir(exist_ok=True)
PID = STATE / 'server.pid'
URL = 'http://127.0.0.1:8000'

def running():
    try:
        pid = int(PID.read_text())
        os.kill(pid, 0)
        # Avoid killing unrelated processes after PID reuse.
        command = subprocess.check_output(['ps', '-p', str(pid), '-o', 'command='], text=True)
        return pid if 'uvicorn app.core.main:app' in command else None
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None

action = sys.argv[1] if len(sys.argv) > 1 else 'status'
if action == 'stop':
    pid = running()
    if pid:
        os.kill(pid, signal.SIGTERM)
        print('Pre-consultation local server stopped.')
    else:
        print('Pre-consultation local server is not running.')
    PID.unlink(missing_ok=True)
elif action == 'start':
    if running():
        print('Already running. Patient: ' + URL + '/#/patient  Doctor: ' + URL + '/#/doctor')
        sys.exit(0)
    env = dict(os.environ, PYTHONUNBUFFERED='1')
    env.pop('ENABLE_LEGACY_API', None)
    with (STATE / 'server.log').open('ab') as log:
        process = subprocess.Popen([str(ROOT / '.venv/bin/python'), '-m', 'uvicorn', 'app.core.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'],
            cwd=ROOT / 'backend', env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    PID.write_text(str(process.pid))
    PID.chmod(0o600)
    for _ in range(60):
        if process.poll() is not None:
            PID.unlink(missing_ok=True)
            print('Server failed to start. Check .local/server.log.', file=sys.stderr)
            sys.exit(1)
        try:
            with urllib.request.urlopen(URL + '/api/v1/config', timeout=1) as response:
                if response.status == 200:
                    print('Patient: ' + URL + '/#/patient')
                    print('Doctor:  ' + URL + '/#/doctor')
                    print('Local data: backend/data/   Logs: .local/server.log')
                    break
        except Exception:
            time.sleep(0.25)
    else:
        print('Startup still pending. Check .local/server.log.', file=sys.stderr)
        sys.exit(1)
else:
    print(json.dumps({'running': bool(running()), 'url': URL, 'pid': running()}))
