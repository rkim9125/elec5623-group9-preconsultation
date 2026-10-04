"""Optional LIVE API smoke test: two GPT-6 Sol calls using synthetic input only.

Run explicitly with `.venv/bin/python scripts/smoke-openai.py`. It consumes API
usage and never runs as part of the normal offline test suite or app startup.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.product.engine import new_intake, process_message, build_review
from app.product.routes import clinician_public_session

s = new_intake({'id':'synthetic-smoke','email':'synthetic@example.test','name':'Synthetic test'}, 'gpt-6-sol', ['WF-01'])
s = process_message(s, 'I want to discuss a dull ache in my left calf for about three weeks. I also have difficulty falling asleep for two months. I take Vitamin D 1000 IU daily and I have no known allergies.')
assert s['ai_status']['mode'] == 'live', s['ai_status'].get('message')
assert {'WF-01', 'WF-08'}.issubset(set(s['plan']['workflow_ids'])), 'Expected independent leg and sleep concerns.'
s = build_review(s)
s = build_review(s, correction='Please remove Vitamin D and all of its dose and frequency details from my record.')
report = {'live_model': s['model'], 'ai_mode': s['ai_status']['mode'], 'workflow_ids': s['plan']['workflow_ids'],
          'summary_version': s['summary']['version'], 'correction_reconciled': not s['summary']['needs_reconciliation'],
          'removed_information_absent': 'Vitamin D' not in json.dumps(clinician_public_session(s))}
print(json.dumps(report, indent=2))
if s['summary']['needs_reconciliation']:
    print(json.dumps({'correction_validation': s.get('audit', [])[-1].get('rejected', [])}))
assert report['ai_mode'] == 'live'
assert report['correction_reconciled'], 'Correction was safely blocked but did not complete.'
assert report['removed_information_absent'], 'Removed information remains in the handoff projection.'
