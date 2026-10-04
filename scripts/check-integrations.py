"""Read-only provider probes. Never print credentials or raw provider errors."""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
for line in (Path(__file__).resolve().parents[1] / 'backend/.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        key, value = line.split('=', 1)
        os.environ.setdefault(key, value)

def probe(name, url, key):
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {key}', 'User-Agent': 'Preconsult-Integration-Check/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
            if name == 'openai':
                wanted = {'gpt-6-sol','gpt-5.6-sol','gpt-4o-mini-transcribe'}
                print(json.dumps({'provider': name, 'status': response.status, 'requested_models_available': sorted(x['id'] for x in payload.get('data',[]) if x['id'] in wanted)}))
            else:
                print(json.dumps({'provider': name, 'status': response.status, 'domains': [{'name': x.get('name'), 'status': x.get('status')} for x in payload.get('data',[])]}))
    except urllib.error.HTTPError as error:
        print(json.dumps({'provider':name,'status':error.code,'error':'Authentication, permission, or endpoint error; see provider dashboard.'}))
    except Exception as error:
        print(json.dumps({'provider':name,'error':type(error).__name__}))

probe('openai', 'https://api.openai.com/v1/models', os.environ.get('OPENAI_API_KEY',''))
probe('resend', 'https://api.resend.com/domains', os.environ.get('RESEND_API_KEY',''))
