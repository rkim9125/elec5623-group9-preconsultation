"""Resumption must not spend calls on completed work or overwrite old evidence."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import extended_grading
import extended_resume as resume
from common import read_json, write_json, append_jsonl


def test_plan_selects_task_quota_separately_from_grader_quota(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'resume'
    names = ['E11-full-1', 'E12-full-1', 'E13-full-1']
    write_json(source / 'manifest.json', {'order': names, 'model': resume.config.get_settings().openai_model, 'source_sha256': {}})
    quota = {'status_code': 429, 'body_json': {'error': {'code': 'credit_balance_exhausted'}}}
    for index, name in enumerate(names):
        (source / name).mkdir()
        append_jsonl(source / name / 'responses.jsonl', {'operation': 'preparation_synthesis', **(quota if index == 0 else {'status_code': 200})})
        if index == 1:
            append_jsonl(source / name / 'responses.jsonl', {'operation': 'evaluation_judge', **quota})
        write_json(source / 'grading_v2' / name / 'result.json', {'status': 'graded' if index == 2 else 'error'})
        if index != 2:
            append_jsonl(source / 'grading_v2' / name / 'responses.jsonl', quota)
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    plan = resume.prepare(source, output)
    assert plan['pipeline_retry_ids'] == [names[0]]
    assert plan['grading_retry_ids'] == names[:2]
    assert resume.prepare(source, output) == plan
    assert before == {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='separate sibling'):
        resume.prepare(source, source / 'new')


def test_external_grade_target_preserves_original_error(tmp_path, monkeypatch):
    source, target = tmp_path / 'source', tmp_path / 'retry'
    case = {'case_id': 'E11', 'text': 'Left calf aching.', 'required': ['Left calf aching.'], 'forbidden': []}
    write_json(source / 'E11-full-1' / 'outcome.json', {'final_text': 'Left calf aching.', 'turns': [case['text']]})
    old = source / 'grading_v2' / 'E11-full-1' / 'result.json'
    write_json(old, {'status': 'error'})
    original = old.read_bytes()
    monkeypatch.setattr(extended_grading, 'generic_request', lambda *args: {'claims': [], 'required': [{'index': 0, 'present': True}]})
    result = extended_grading.score((str(source), 'E11-full-1', case, str(target)))
    assert result['status'] == 'graded'
    assert read_json(target / 'result.json')['rubric_version'] == 2
    assert old.read_bytes() == original


def test_graded_results_skipped_but_error_results_get_new_attempt(tmp_path, monkeypatch):
    source, output = tmp_path / 'source', tmp_path / 'retry'
    write_json(source / 'manifest.json', {'cases': [{'case_id': 'E11', 'required': []}, {'case_id': 'E12', 'required': []}]})
    good = output / 'grading' / 'original' / 'E11-full-1' / 'attempt-001'
    bad = output / 'grading' / 'original' / 'E12-full-1' / 'attempt-001'
    write_json(good / 'result.json', {'status': 'graded'})
    write_json(bad / 'result.json', {'status': 'error'})
    write_json(output / 'grading_index.json', {'original/E11-full-1': str(good), 'original/E12-full-1': str(bad)})
    submitted = []
    monkeypatch.setattr(resume, 'bounded_work', lambda tasks, *_: submitted.extend(tasks))
    resume.run_grading(source, output, {'grading_retry_ids': ['E11-full-1', 'E12-full-1']}, 1)
    assert len(submitted) == 1
    assert submitted[0][1] == 'E12-full-1'
    assert Path(submitted[0][3]).name == 'attempt-002'
    assert read_json(bad / 'result.json') == {'status': 'error'}


def test_quota_marker_blocks_preflight_and_batch_before_network(tmp_path, monkeypatch):
    write_json(tmp_path / 'QUOTA_EXHAUSTED.json', {'code': 'credit_balance_exhausted'})
    monkeypatch.setattr(resume, 'score', lambda *_: pytest.fail('Network work must not start'))
    assert resume.preflight(tmp_path)['calls'] == 0
    assert resume.bounded_work([1, 2], resume.score, tmp_path, 1, lambda *_: None) == 0


def test_missing_required_index_is_retryable_not_a_content_failure(tmp_path, monkeypatch):
    source, output = tmp_path / 'source', tmp_path / 'retry'
    case = {'case_id': 'E11', 'required': ['Left calf aching.']}
    write_json(source / 'manifest.json', {'cases': [case]})
    prior = output / 'grading' / 'original' / 'E11-full-1' / 'attempt-001'
    malformed = {'status': 'graded', 'judge': {'claims': [], 'required': []}}
    write_json(prior / 'result.json', malformed)
    write_json(output / 'grading_index.json', {'original/E11-full-1': str(prior)})
    tasks = []
    monkeypatch.setattr(resume, 'bounded_work', lambda submitted, *_: tasks.extend(submitted))
    resume.run_grading(source, output, {'grading_retry_ids': ['E11-full-1']}, 1)
    assert len(tasks) == 1
    assert Path(tasks[0][3]).name == 'attempt-002'
    assert read_json(prior / 'result.json') == malformed
