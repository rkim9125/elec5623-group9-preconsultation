"""Offline, paired validation of the frozen final candidates; never calls a model."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT.parent), str(ROOT)]
from app.product import intelligence as current
from common import read_json, read_jsonl, write_json
from grade import model_output, verify_body


def verdict(validator, data, sources, concerns, locale):
    try:
        validator.validate_synthesis(deepcopy(data), deepcopy(sources), deepcopy(concerns), locale=locale)
        return {'accepted': True, 'reason': None}
    except validator.IntelligenceUnavailable as exc:
        return {'accepted': False, 'reason': str(exc)}


def replay(evidence_path, baseline_path, original_evidence_path):
    spec = importlib.util.spec_from_file_location('app.product._validator_before', baseline_path)
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    evidence = read_json(evidence_path)
    rows = []
    for trial in evidence['combined_rows']:
        if trial['variant'] == 'generic':
            continue  # Generic has no product synthesis validator.
        directory = Path(trial['generation_directory'])
        requests = {r['call_id']: r for r in read_jsonl(directory / 'requests.jsonl')}
        responses = [r for r in read_jsonl(directory / 'responses.jsonl') if r['operation'] == 'preparation_synthesis']
        response = responses[-1]
        request = requests[response['call_id']]
        verify_body(request)
        verify_body(response)
        inputs = json.loads(next(message['content'] for message in request['body_json']['input'] if message['role'] == 'user'))
        candidate, _, issues = model_output(response)
        if response['status_code'] != 200 or issues or not candidate:
            raise ValueError(f"Unusable final candidate: {trial['id']}")
        args = candidate, inputs['sources'], inputs['concerns'], inputs.get('locale', 'en')
        old, new = verdict(before, *args), verdict(current, *args)
        if old['accepted'] != trial['delivery']:
            raise ValueError(f"Frozen baseline does not reproduce delivery: {trial['id']}")
        rows.append({'id': trial['id'], 'variant': trial['variant'], 'generation_directory': str(directory),
                     'call_id': response['call_id'], 'request_body_sha256': request['body_sha256'],
                     'response_body_sha256': response['body_sha256'], 'before': old, 'after': new})
    fixtures = []
    for fixture in read_json(original_evidence_path)['offline']['validator_cases']:
        verdicts = {}
        for label, validator in [('before', before), ('after', current)]:
            try:
                validator._validate_cited(fixture['output'], {'s1': fixture['source']})
                verdicts[label] = True
            except validator.IntelligenceUnavailable:
                verdicts[label] = False
        if verdicts['before'] != fixture['validator_on_accept']:
            raise ValueError(f"Baseline fixture changed: {fixture['id']}")
        fixtures.append({**fixture, **verdicts})
    groups = {}
    for variant in ('full', 'fixed', 'no_followup', 'attack'):
        selected = [row for row in rows if row['variant'] == variant]
        groups[variant] = {'n': len(selected), **{when: sum(row[when]['accepted'] for row in selected) for when in ('before', 'after')}}
    return {
        'method': 'Same captured final candidate + same generation-time sources/concerns; validator only. No model or full-pipeline rerun.',
        'model_calls': 0, 'evidence_sha256': hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        'baseline_path': str(baseline_path), 'baseline_sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        'current_sha256': hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest(),
        'groups': groups, 'rows': rows, 'fixtures': fixtures,
        'newly_accepted': [r['id'] for r in rows if r['after']['accepted'] and not r['before']['accepted']],
        'newly_rejected': [r['id'] for r in rows if r['before']['accepted'] and not r['after']['accepted']],
        'remaining_first_reasons': dict(Counter(r['after']['reason'] for r in rows if not r['after']['accepted'])),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT/'reports/2026-11-02-pipeline-resumed-evidence.json')
    parser.add_argument('--original-evidence', type=Path, default=ROOT/'reports/2026-11-02-pipeline-evidence.json')
    parser.add_argument('--baseline', type=Path, default=ROOT/'runs/extended-20261102/source_snapshot/backend/app/product/intelligence.py')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch('httpx.Client.send', side_effect=AssertionError('Offline replay forbids model/network calls')):
        result = replay(args.evidence, args.baseline, args.original_evidence)
    write_json(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key in ('groups', 'newly_rejected', 'remaining_first_reasons')}, ensure_ascii=False, indent=2))
