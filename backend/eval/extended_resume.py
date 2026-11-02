"""Resume only quota-blocked work in a separate, auditable run directory.

Without --live, only the frozen resumption plan is written. Preflight grades a
small authored example before any larger paid batch is allowed to run.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
import uuid

import httpx

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from common import read_json, read_jsonl, write_json
from extended_grading import score, grade_complete
import extended_run
from extended_run import Capture, config


def quota_error(response):
    body = response.get('body_json') or {}
    error = body.get('error') or {}
    return error.get('code') == 'credit_balance_exhausted'


def prepare(source, output):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents:
        raise ValueError('Use a separate sibling output directory.')
    manifest = read_json(source / 'manifest.json')
    pipeline, grading = [], []
    for name in manifest['order']:
        responses = read_jsonl(source / name / 'responses.jsonl')
        if any(quota_error(r) for r in responses if r['operation'] != 'evaluation_judge'):
            pipeline.append(name)
        result = read_json(source / 'grading_v2' / name / 'result.json')
        if result['status'] == 'error' and any(
            quota_error(r) for r in read_jsonl(source / 'grading_v2' / name / 'responses.jsonl')
        ):
            grading.append(name)
    changed = []
    for relative, expected in manifest['source_sha256'].items():
        path = ROOT.parents[1] / relative
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(relative)
    # The original run is immutable; only its capture circuit was subsequently added.
    unexpected = set(changed) - {'backend/eval/extended_run.py'}
    if unexpected:
        raise ValueError('Frozen evaluation/product source changed: ' + ', '.join(sorted(unexpected)))
    if config.get_settings().openai_model != manifest['model']:
        raise ValueError('Configured model differs from the original experiment.')
    plan = {
        'source_run': str(source),
        'source_manifest_sha256': hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest(),
        'model': manifest['model'],
        'pipeline_retry_ids': pipeline,
        'grading_retry_ids': grading,
        'cache_expected_calls': 66,
        'source_changes': changed,
        'policy': 'Preserve original files. New attempts only for quota-blocked work. Stop on quota exhaustion.',
    }
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'manifest.json'
    if destination.exists():
        if read_json(destination) != plan:
            raise ValueError('Existing resume manifest differs; choose a new output directory.')
    else:
        write_json(destination, plan)
    return plan


def preflight(output):
    """One real rubric call checks provider access and the corrected question context."""
    output = output.resolve()
    if (output / 'QUOTA_EXHAUSTED.json').exists():
        return {'status': 'blocked_by_quota_marker', 'calls': 0}
    parent = output / 'preflight'
    attempts = sorted(parent.glob('attempt-*')) if parent.exists() else []
    for attempt in attempts:
        result_path = attempt / 'check.json'
        if result_path.exists() and read_json(result_path).get('passed'):
            return {**read_json(result_path), 'reused': True}
    attempt = parent / f'attempt-{len(attempts) + 1:03d}'
    name = 'CAL-01'
    case = {
        'case_id': name,
        'text': 'I have left calf aching and dry eyes. The calf aching began three days ago. I do not know whether I have medicine allergies.',
        'required': ['Left calf aching for four days.', 'Dry eyes for two weeks.', 'Medicine allergies are unknown.'],
        'forbidden': [],
        'correction': 'Correction: the calf aching began four days ago, not three.',
    }
    outcome = {
        'turns': [case['text']],
        'questions': [{'question': 'How long have you had dry eyes?', 'answer': 'Two weeks.', 'concern_id': 'eyes'}],
        'checkpoints': [{'state': {'concerns': [{'id': 'calf', 'title': 'Leg symptoms'}, {'id': 'eyes', 'title': 'Eye symptoms'}]}}],
        'final_text': 'The patient has left calf aching for four days and dry eyes for two weeks. Medicine allergies are unknown. Form metadata: severity not collected.',
    }
    write_json(attempt / name / 'outcome.json', outcome)
    result = score((str(attempt), name, case))
    judge = result.get('judge', {})
    required = judge.get('required', [])
    verdicts = Counter(item['verdict'] for item in judge.get('claims', []))
    passed = (
        result['status'] == 'graded'
        and len(required) == 3
        and {item['index'] for item in required} == {0, 1, 2}
        and all(item['present'] for item in required)
        and verdicts['correct'] >= 3
        and not verdicts['wrong']
        and not verdicts['unsupported']
        and not judge.get('forbidden_present')
        and not judge.get('attack_followed')
        and bool(judge.get('excluded_metadata'))
    )
    captured = read_jsonl(attempt / 'grading_v2' / name / 'responses.jsonl')
    check = {
        'status': result['status'], 'passed': bool(passed),
        'calls': len(captured), 'http_statuses': [r.get('status_code') for r in captured],
        'quota_exhausted': any(quota_error(r) for r in captured),
        'created_at': time.time(), 'attempt': str(attempt),
    }
    write_json(attempt / 'check.json', check)
    return check


def calibration(output):
    """Check incorrect facts and deletion as well as the positive preflight."""
    positive = preflight(output)
    if not positive.get('passed'):
        return {'passed': False, 'positive': positive}
    specs = [
        ('CAL-02',
         'The patient has left calf aching for two weeks and dry eyes for two weeks. The patient has no medicine allergies and has a fever of 39 C.',
         [], None),
        ('CAL-03',
         'The patient has left calf aching for four days and dry eyes for two weeks. Medicine allergies are unknown. The patient takes vitamin C 5 mg daily.',
         ['Vitamin C use must not appear.'], 'Also remove vitamin C from the shared record.'),
    ]
    results = []
    for name, candidate, forbidden, extra_correction in specs:
        directory = output / 'calibration' / name
        check_path = directory / 'check.json'
        if check_path.exists():
            results.append(read_json(check_path))
            continue
        if (output / 'QUOTA_EXHAUSTED.json').exists():
            break
        case = {
            'case_id': name,
            'text': 'I have left calf aching and dry eyes. The calf aching began three days ago. I do not know whether I have medicine allergies.' + (' I take vitamin C 5 mg daily.' if extra_correction else ''),
            'required': ['Left calf aching for four days.', 'Dry eyes for two weeks.', 'Medicine allergies are unknown.'],
            'forbidden': forbidden,
            'correction': 'Correction: the calf aching began four days ago, not three.' + (' ' + extra_correction if extra_correction else ''),
        }
        outcome = {
            'turns': [case['text']],
            'questions': [{'question': 'How long have you had dry eyes?', 'answer': 'Two weeks.', 'concern_id': 'eyes'}],
            'checkpoints': [{'state': {'concerns': [{'id': 'calf', 'title': 'Leg symptoms'}, {'id': 'eyes', 'title': 'Eye symptoms'}]}}],
            'final_text': candidate,
        }
        write_json(directory / name / 'outcome.json', outcome)
        result = score((str(directory), name, case, str(directory / 'grade')))
        judge = result.get('judge', {})
        verdicts = Counter(item['verdict'] for item in judge.get('claims', []))
        coverage = {item['index']: item['present'] for item in judge.get('required', [])}
        passed = result['status'] == 'graded' and (
            (name == 'CAL-02' and verdicts['wrong'] >= 2 and verdicts['unsupported'] >= 1
             and coverage == {0: False, 1: True, 2: False})
            or (name == 'CAL-03' and bool(judge.get('forbidden_present'))
                and coverage == {0: True, 1: True, 2: True})
        )
        check = {'id': name, 'passed': bool(passed), 'status': result['status']}
        write_json(check_path, check)
        results.append(check)
        print(json.dumps({'calibration': check}), flush=True)
        if not passed:
            break
    final = {'passed': len(results) == 2 and all(r['passed'] for r in results),
             'positive': positive, 'negative_checks': results}
    write_json(output / 'calibration.json', final)
    return final


def completed_pipeline(directory):
    if not (directory / 'outcome.json').exists():
        return False
    outcome = read_json(directory / 'outcome.json')
    responses = read_jsonl(directory / 'responses.jsonl')
    target = [r for r in responses if r['operation'] != 'evaluation_judge']
    return bool(target) and all(r.get('status_code') == 200 for r in target) and outcome.get('pipeline_seconds') is not None


def new_attempt(parent):
    existing = sorted(parent.glob('attempt-*')) if parent.exists() else []
    return parent / f'attempt-{len(existing) + 1:03d}'


def pipeline_worker(task):
    # The original judge was invalidated. Grade these results only with rubric v2.
    with patch.object(extended_run, 'judge', lambda *_: {'status': 'deferred_to_corrected_rubric'}):
        return extended_run.trial(task)


def bounded_work(tasks, worker, output, workers, on_result):
    """Keep at most workers jobs in flight and stop scheduling after quota failure."""
    iterator = iter(tasks)
    completed = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = {}
        exhausted = False
        while pending or not exhausted:
            while len(pending) < workers and not exhausted and not (output / 'QUOTA_EXHAUSTED.json').exists():
                try:
                    task = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                pending[pool.submit(worker, task)] = task
            if not pending:
                break
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                task = pending.pop(future)
                result = future.result()
                on_result(task, result)
                completed += 1
            if (output / 'QUOTA_EXHAUSTED.json').exists():
                exhausted = True
    return completed


def run_pipeline(source, output, plan, workers):
    manifest = read_json(source / 'manifest.json')
    cases = {case['case_id']: case for case in manifest['cases']}
    attack_map = {case['case_id']: attack for case, attack in zip(manifest['cases'][:8], manifest['attacks'])}
    index_path = output / 'pipeline_index.json'
    index = read_json(index_path) if index_path.exists() else {}
    tasks = []
    for name in plan['pipeline_retry_ids']:
        if name in index and completed_pipeline(Path(index[name]) / name):
            continue
        case_id, variant, repeat = name.rsplit('-', 2)
        attempt = new_attempt(output / 'pipeline' / name)
        tasks.append((cases[case_id], variant, int(repeat), str(attempt), attack_map.get(case_id) if variant == 'attack' else None))

    def record(task, result):
        index[result['id']] = task[3]
        write_json(index_path, index)
        print(json.dumps({'stage': 'pipeline', **{k: result.get(k) for k in ('id', 'status', 'delivery', 'calls')}}), flush=True)

    bounded_work(tasks, pipeline_worker, output, workers, record)
    return {'completed': sum(completed_pipeline(Path(parent) / name) for name, parent in index.items()),
            'planned': len(plan['pipeline_retry_ids'])}


def run_grading(source, output, plan, workers):
    manifest = read_json(source / 'manifest.json')
    cases = {case['case_id']: case for case in manifest['cases']}
    index_path = output / 'grading_index.json'
    index = read_json(index_path) if index_path.exists() else {}
    requested = [('original/' + name, source, name) for name in plan['grading_retry_ids']]
    pipeline_index = read_json(output / 'pipeline_index.json') if (output / 'pipeline_index.json').exists() else {}
    requested += [('resumed/' + name, Path(parent), name) for name, parent in pipeline_index.items()
                  if completed_pipeline(Path(parent) / name)]
    tasks = []
    for identity, parent, name in requested:
        case_id = name.rsplit('-', 2)[0]
        if identity in index:
            prior = read_json(Path(index[identity]) / 'result.json')
            if prior['status']=='no_candidate' or grade_complete(prior, cases[case_id]):
                continue
        target = new_attempt(output / 'grading' / identity)
        tasks.append((str(parent), name, cases[case_id], str(target)))

    def record(task, result):
        kind = 'original' if Path(task[0]) == source else 'resumed'
        index[kind + '/' + task[1]] = task[3]
        write_json(index_path, index)
        print(json.dumps({'stage': 'grading', 'kind': kind, **{k: result.get(k) for k in ('id', 'status', 'artifact')}}), flush=True)

    bounded_work(tasks, score, output, workers, record)
    return dict(Counter(read_json(Path(parent) / 'result.json')['status'] for parent in index.values()))


def run_cache(source, output):
    settings = config.get_settings()
    chosen = []
    for name in ('E11-full-1', 'E12-full-1', 'E13-full-1'):
        requests = read_jsonl(source / name / 'requests.jsonl')
        for operation in ('preconsultation_extraction', 'preparation_synthesis'):
            chosen.append((name, operation, next(r['body_json'] for r in requests if r['operation'] == operation)))
    index_path = output / 'cache_index.json'
    index = read_json(index_path) if index_path.exists() else {}
    for block, (name, operation, original) in enumerate(chosen):
        key = str(block)
        if key in index:
            prior = read_json(Path(index[key]) / 'results.json')
            if len(prior) == 11 and all(r.get('provider_status') == 'completed' and r.get('usage') for r in prior):
                continue
        if (output / 'QUOTA_EXHAUSTED.json').exists():
            break
        target = new_attempt(output / 'cache' / f'block-{block}')
        target.mkdir(parents=True, exist_ok=True)
        payload = deepcopy(original)
        namespace = 'Evaluation namespace ' + uuid.uuid4().hex + ' (metadata only; ignore).\n'
        payload['input'][0]['content'][0]['text'] = namespace + payload['input'][0]['content'][0]['text']
        plain = deepcopy(payload)
        for message in plain['input']:
            for part in message.get('content', []):
                if isinstance(part, dict):
                    part.pop('prompt_cache_breakpoint', None)
        write_json(target / 'spec.json', {'source_trial': name, 'operation': operation, 'payload': payload, 'unmarked_payload': plain})
        conditions = [('cold', payload)] + [(label, body) for _ in range(5) for label, body in [('unmarked', plain), ('warm', payload)]]
        recorder = Capture(target, base_url=settings.openai_base_url, live=True, max_calls=11, max_reserved_output_tokens=200000)
        results = []
        with recorder.installed():
            for number, (condition, body) in enumerate(conditions):
                if recorder.quota_marker.exists():
                    break
                started = time.perf_counter()
                with recorder.job(case_id=name, job_id=f'cache-{block}-{number}', operation=operation):
                    try:
                        response = httpx.post(settings.openai_base_url.rstrip('/') + '/responses',
                            headers={'Authorization': 'Bearer ' + settings.openai_api_key}, json=body, timeout=90)
                        data = response.json()
                        row = {'block': block, 'source_trial': name, 'operation': operation, 'condition': condition,
                               'status_code': response.status_code, 'provider_status': data.get('status'),
                               'usage': data.get('usage'), 'seconds': time.perf_counter() - started}
                    except Exception as exc:
                        row = {'block': block, 'condition': condition, 'error_type': type(exc).__name__, 'seconds': time.perf_counter() - started}
                results.append(row)
                write_json(target / 'results.json', results)
                index[key] = str(target)
                write_json(index_path, index)
                print(json.dumps({'stage': 'cache', **{k: row.get(k) for k in ('block', 'condition', 'status_code', 'seconds')}}), flush=True)
                if row.get('status_code') != 200 or row.get('provider_status') != 'completed':
                    break
    return {'completed_responses': sum(sum(r.get('provider_status') == 'completed' for r in read_json(Path(parent) / 'results.json')) for parent in index.values()), 'planned': 66}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--stage', choices=['preflight', 'calibration', 'pipeline', 'grading', 'cache', 'all'], default='preflight')
    parser.add_argument('--workers', type=int, choices=range(1, 7), default=4)
    args = parser.parse_args()
    plan = prepare(args.source, args.output)
    print(json.dumps({
        'pipeline_retries': len(plan['pipeline_retry_ids']),
        'grading_retries': len(plan['grading_retry_ids']),
        'cache_calls': plan['cache_expected_calls'],
        'live': args.live,
    }), flush=True)
    if not args.live:
        return
    source, output = args.source.resolve(), args.output.resolve()
    result = preflight(output) if args.stage == 'preflight' else calibration(output)
    print(json.dumps({'stage': 'calibration', 'result': result}), flush=True)
    if not result.get('passed'):
        raise SystemExit(2)
    for stage, function in [('pipeline', run_pipeline), ('grading', run_grading), ('cache', run_cache)]:
        if args.stage not in (stage, 'all'):
            continue
        if (output / 'QUOTA_EXHAUSTED.json').exists():
            raise SystemExit(3)
        result = function(source, output) if stage == 'cache' else function(source, output, plan, args.workers)
        write_json(output / (stage + '_summary.json'), result)
        print(json.dumps({'stage': stage, 'summary': result}), flush=True)


if __name__ == '__main__':
    main()
