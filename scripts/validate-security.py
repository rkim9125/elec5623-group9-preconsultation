#!/usr/bin/env python3
"""Run deterministic security regressions and export reviewable evidence.

Use the backend virtualenv. Tests use disposable data and mocked providers;
this runner never performs a live-model or production-data attack.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SUITE = [
    'test_product_security_boundary.py', 'test_product_auth.py', 'test_product_api.py',
    'test_product_app.py', 'test_product_media.py', 'test_product_provider.py',
    'test_product_assessment.py', 'test_product_intelligence.py',
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/security-validation')
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    junit = output / 'security-junit.xml'
    command = [sys.executable, '-m', 'pytest', *['backend/tests/' + filename for filename in SUITE],
               '-q', '--junitxml=' + str(junit)]
    run = subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYTHON_DOTENV_DISABLED': '1'},
                         text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (output / 'security-tests.log').write_text(run.stdout)
    rows = []
    if junit.exists():
        for case in ET.parse(junit).getroot().iter('testcase'):
            failure = case.find('failure')
            error = case.find('error')
            skipped = case.find('skipped')
            rows.append({'suite': case.get('classname'), 'case': case.get('name'),
                         'seconds': float(case.get('time', 0)),
                         'status': 'failed' if failure is not None or error is not None else 'skipped' if skipped is not None else 'passed'})
    result = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'Deterministic application regression. Disposable SQLite and synthetic identities; all remote AI/email responses mocked.',
        'production_data_accessed': False, 'live_model_calls': 0, 'exit_code': run.returncode,
        'total': len(rows), 'passed': sum(r['status'] == 'passed' for r in rows),
        'failed': sum(r['status'] == 'failed' for r in rows), 'skipped': sum(r['status'] == 'skipped' for r in rows),
        'new_boundary_cases': sum(r['suite'].endswith('test_product_security_boundary') for r in rows),
        'cases': rows,
        'limits': ['Passing these cases does not prove resistance to all future prompt injections.',
                   'Output phrase checks are bounded; server authorization and lack of model action tools are the access boundary.',
                   'Doctor account registration verifies email ownership, not medical licensure.',
                   'Production deployment security and clinical safety require independent evaluation.'],
    }
    (output / 'security-results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(run.stdout)
    print(json.dumps({key: result[key] for key in ('total', 'passed', 'failed', 'skipped', 'new_boundary_cases', 'exit_code')}))
    return run.returncode


if __name__ == '__main__':
    raise SystemExit(main())
