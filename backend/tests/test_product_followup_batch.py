"""Bounded one-batch follow-up: server limits, provenance, drafts and ownership."""
from copy import deepcopy
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.product import auth, engine, forms, intelligence as ai, pipeline, routes
from app.product.database import load_intake, save_intake
from .test_product_auth import product_env, sign_in
from .test_product_intelligence import Extractor, DownExtractor, Smart, baseline, fact


class BatchPlanner(Smart):
    def plan(self, **kwargs):
        self.plans.append(deepcopy(kwargs))
        return {'overview': {'text': '', 'source_ids': []}, 'suggested_concern_ids': [],
                'questions': [{'target_id': target['target_id'],
                               'rationale': 'This can help describe your experience at the appointment.',
                               'options': [{'label': 'Comes and goes', 'value': 'Comes and goes'},
                                           {'label': 'Present all the time', 'value': 'Present all the time'}]}
                              for target in kwargs['targets'][:5]]}


def prepared():
    session = baseline()
    planner, extractor = BatchPlanner(), Extractor()
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    return session, planner, extractor


def answers(session, value='Patient supplied detail', status='FILLED'):
    return [{'question_id': q['id'], 'value': value if status == 'FILLED' else None, 'status': status}
            for q in session['followup_batch']['questions']]


def test_one_batch_has_all_questions_choices_and_no_serial_question():
    session, planner, _ = prepared()
    batch = session['followup_batch']
    assert 1 < len(batch['questions']) <= 5 and batch['round'] == 1 and batch['status'] == 'pending'
    assert session['current_question'] is None and session['plan']['next_target'] is None
    assert len(planner.plans) == 1
    assert all(q['allow_custom'] and [o['id'] for o in q['options']] == ['A', 'B'] for q in batch['questions'])
    # Merely displaying a choice cannot create a clinical fact.
    assert all(engine._owner_slots(session, q['concern_id'])[q['key']]['status'] == 'MISSING' for q in batch['questions'])


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'unknown', 'empty', 'bad_status'])
def test_submission_validation_is_atomic(mutation):
    session, _, extractor = prepared()
    rows = answers(session)
    if mutation == 'missing': rows.pop()
    if mutation == 'duplicate': rows[-1] = deepcopy(rows[0])
    if mutation == 'unknown': rows[-1]['question_id'] = 'invented'
    if mutation == 'empty': rows[-1]['value'] = ' '
    if mutation == 'bad_status': rows[-1]['status'] = 'MISSING'
    before = deepcopy(session)
    with pytest.raises(ValueError): pipeline.answer_followup_batch(session, session['followup_batch']['id'], rows, extraction=extractor)
    assert session == before and len(extractor.calls) == 1


def test_answers_saved_directly_then_one_extraction_and_no_second_plan():
    session, planner, extractor = prepared()
    batch = deepcopy(session['followup_batch'])
    pipeline.answer_followup_batch(session, batch['id'], answers(session), extraction=extractor)
    assert session['followup_batch']['status'] == 'answered' and session['assistant']['mode'] == 'ready'
    assert len(extractor.calls) == 2 and len(planner.plans) == 1
    for q in batch['questions']:
        slot = engine._owner_slots(session, q['concern_id'])[q['key']]
        assert slot['value'] == 'Patient supplied detail' and slot['evidence']['source'] == 'followup_batch'
        snapshot = extractor.calls[-1]['session']
        slots = snapshot['shared_slots'] if q['concern_id'] == 'session' else next(c['slots'] for c in snapshot['concerns'] if c['id'] == q['concern_id'])
        assert slots[q['key']]['value'] == 'Patient supplied detail'
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    pipeline.process_message(session, 'Extra optional detail.', intelligence=planner, extraction=extractor)
    assert len(planner.plans) == 1 and session['followup_batch']['round'] == 1


def test_retry_and_messages_cannot_bypass_pending_or_answered_batch():
    session, planner, extractor = prepared()
    batch = deepcopy(session['followup_batch'])
    for _ in range(4): pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    assert len(planner.plans) == 1 and session['followup_batch'] == batch
    with pytest.raises(ValueError, match='together'):
        pipeline.process_message(session, 'one answer', intelligence=planner, extraction=extractor)
    pipeline.answer_followup_batch(session, batch['id'], answers(session, status='SKIPPED'), extraction=extractor)
    before = deepcopy(session)
    with pytest.raises(ValueError, match='no longer pending'):
        pipeline.answer_followup_batch(session, batch['id'], answers(session), extraction=extractor)
    assert session == before


def test_failure_keeps_direct_answers_and_does_not_unlock_another_round():
    session, planner, extractor = prepared()
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], answers(session), extraction=DownExtractor())
    assert session['assistant']['mode'] == 'unavailable' and session['followup_batch']['status'] == 'answered'
    assert all(engine._owner_slots(session, q['concern_id'])[q['key']]['value'] == 'Patient supplied detail' for q in session['followup_batch']['questions'])
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    assert len(planner.plans) == 1


def test_draft_is_private_and_does_not_apply_or_invoke_extraction():
    session, _, extractor = prepared()
    batch = session['followup_batch']; rows = answers(session)
    pipeline.save_followup_draft(session, batch['id'], rows[:1])
    assert batch['draft_answers'] == rows[:1]
    q = batch['questions'][0]
    assert engine._owner_slots(session, q['concern_id'])[q['key']]['status'] == 'MISSING'
    assert len(extractor.calls) == 1
    assert 'draft_answers' not in json.dumps(routes.clinician_public_session(session))
    pipeline.answer_followup_batch(session, batch['id'], rows, extraction=extractor)
    assert session['followup_batch']['draft_answers'] == []


def test_all_values_pass_safety_before_any_answer_or_ai_mutation():
    session, _, extractor = prepared()
    rows = answers(session); rows[-1]['value'] = 'I have chest pain now.'
    before_slots = deepcopy(session['concerns'])
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], rows, extraction=extractor)
    assert session['status'] == 'interrupted' and len(extractor.calls) == 1
    assert session['concerns'] == before_slots


def test_consent_withdrawal_in_batch_stops_before_extraction():
    session, _, extractor = prepared(); rows = answers(session); rows[-1]['value'] = 'I withdraw my consent.'
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], rows, extraction=extractor)
    assert not session['consent'] and session['status'] == 'withdrawn' and len(extractor.calls) == 1


def test_only_new_important_conflicts_get_one_explicit_second_round():
    session, planner, _ = prepared()
    extraction = Extractor(facts=[fact('session', 'current_medications', 'I take Vitamin C')])
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], answers(session, 'I take Vitamin C'), extraction=extraction)
    batch = deepcopy(session['followup_batch'])
    assert batch['round'] == 2 and batch['status'] == 'pending' and batch['second_round_reason']
    assert len(batch['questions']) == 1 and batch['questions'][0]['key'] == 'current_medications'
    assert batch['questions'][0]['options'] == []
    pipeline.answer_followup_batch(session, batch['id'], answers(session, 'I take Vitamin C'), extraction=Extractor())
    assert session['followup_batch']['status'] == 'answered'
    assert not session['shared_slots']['current_medications'].get('conflict')
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor())
    assert session['followup_batch']['round'] == 2 and len(planner.plans) == 1


def test_old_important_conflict_and_new_minor_conflict_do_not_spawn_second_batch():
    session = baseline()
    session['shared_slots']['allergies'].update(value='Earlier vs later', status='UNCERTAIN', conflict=True)
    owner = session['concerns'][0]['id']
    session['concerns'][0]['slots']['symptom_onset'].update(value='two weeks', status='FILLED')
    pipeline.start_followup(session, intelligence=BatchPlanner(), extraction=Extractor())
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], answers(session, 'three weeks'), extraction=Extractor(facts=[fact(owner, 'symptom_onset', 'three weeks')]))
    assert session['followup_batch']['round'] == 1 and session['followup_batch']['status'] == 'answered'


def test_finish_review_dismisses_pending_batch_and_cannot_restart_it():
    session, planner, extractor = prepared()
    pipeline.build_review(session, intelligence=planner)
    assert session['status'] == 'review' and session['followup_batch']['status'] == 'dismissed'
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    assert len(planner.plans) == 1


@pytest.mark.parametrize('invalid', ['too_many', 'duplicate', 'outside', 'four_options', 'advice'])
def test_invalid_model_batches_are_rejected(invalid):
    session = baseline(); targets = pipeline.eligible_followups(session)
    sources, concerns = ai.current_sources(session), ai.current_concerns(session)
    output = BatchPlanner().plan(targets=targets, sources=sources, concerns=concerns)
    if invalid == 'too_many': output['questions'] = output['questions'] * 2
    if invalid == 'duplicate': output['questions'][1] = deepcopy(output['questions'][0])
    if invalid == 'outside': output['questions'][0]['target_id'] = 'invented'
    if invalid == 'four_options': output['questions'][0]['options'] *= 2
    if invalid == 'advice': output['questions'][0]['options'][0]['value'] = 'You should take medicine.'
    with pytest.raises(ai.IntelligenceUnavailable): ai.validate_plan(output, sources, concerns, targets)


def test_configuration_cannot_raise_question_limit(monkeypatch):
    monkeypatch.setenv('FOLLOWUP_MAX_QUESTIONS', '999')
    session, _, _ = prepared()
    assert len(session['followup_batch']['questions']) <= 5
    assert pipeline._state(session)['max_questions'] == 5


@pytest.fixture
def batch_api(product_env, monkeypatch):
    app = FastAPI()
    app.include_router(auth.router, prefix='/api/v1')
    app.include_router(routes.router, prefix='/api/v1')
    monkeypatch.setattr(pipeline, 'get_intelligence', BatchPlanner)
    monkeypatch.setattr(pipeline, 'get_provider', Extractor)
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        sign_in(client, product_env)
        state = client.post('/api/v1/intakes', json={'consent': True, 'workflow_ids': ['WF-01']}).json()
        state = client.put('/api/v1/intakes/' + state['id'] + '/baseline', json={'answers': [], 'complete': True}).json()
        yield client, state


def test_api_drafts_revision_and_final_atomic_answer_submission(batch_api):
    client, state = batch_api; url = '/api/v1/intakes/' + state['id']; batch = state['followup_batch']
    response = client.put(url + '/followup/draft', json={'batch_id': batch['id'], 'answers': answers(state)[:1], 'revision': state['revision']})
    assert response.status_code == 200 and response.json()['followup_batch']['draft_answers']
    stale = client.post(url + '/followup/answers', json={'batch_id': batch['id'], 'answers': answers(state), 'revision': state['revision']})
    assert stale.status_code == 409
    missing = client.post(url + '/followup/answers', json={'batch_id': batch['id'], 'answers': answers(state)[:-1]})
    assert missing.status_code == 409 and load_intake(state['id'])['followup_batch']['status'] == 'pending'
    response = client.post(url + '/followup/answers', json={'batch_id': batch['id'], 'answers': answers(state), 'revision': response.json()['revision']})
    assert response.status_code == 200 and response.json()['followup_batch']['status'] == 'answered'
    assert client.post(url + '/followup/answers', json={'batch_id': batch['id'], 'answers': answers(state)}).status_code == 409
    assert client.post(url + '/review').status_code == 200


def test_legacy_chat_can_explicitly_upgrade_but_unfinished_wizard_cannot():
    legacy = engine.new_intake({'id': 'patient'}, 'gpt-6-astra', ['WF-01'])
    engine._message(legacy, 'patient', 'My leg is uncomfortable.')
    assert pipeline.can_start_followup(legacy)
    pipeline.start_followup(legacy, intelligence=BatchPlanner(), extraction=Extractor())
    assert legacy['followup_batch']['status'] == 'pending' and legacy['current_question'] is None
    wizard = forms.initialize(engine.new_intake({'id': 'patient'}, 'gpt-6-astra', ['WF-01']))
    engine._message(wizard, 'patient', 'Some saved baseline text.')
    assert not pipeline.can_start_followup(wizard)
    with pytest.raises(ValueError, match='finish your baseline'):
        pipeline.start_followup(wizard, intelligence=BatchPlanner(), extraction=Extractor())


def test_pending_batch_legacy_message_still_honors_safety_and_consent():
    session, _, extractor = prepared()
    pipeline.process_message(session, 'I have chest pain now.', extraction=extractor)
    assert session['status'] == 'interrupted' and len(extractor.calls) == 1
    session, _, extractor = prepared()
    pipeline.process_message(session, 'I withdraw my consent.', extraction=extractor)
    assert session['status'] == 'withdrawn' and not session['consent'] and len(extractor.calls) == 1


def test_medicine_allergy_and_measurement_fields_never_seed_suggested_values():
    target = {'target_id': 't', 'key': 'medication.synthetic.dose', 'concern_id': 'session', 'question': 'What dose?', 'label': 'Dose'}
    data = BatchPlanner().plan(targets=[target], sources=[], concerns=[])
    assert ai.validate_plan(data, [], [], [target])['questions'][0]['options'] == []


def test_changed_baseline_closes_old_questions_preserves_drafts_and_budget():
    session, planner, extractor = prepared()
    batch = deepcopy(session['followup_batch']); draft = answers(session)
    pipeline.save_followup_draft(session, batch['id'], draft)
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'Vitamin D', 'status': 'FILLED'}], complete=True)
    # The forms hook and direct pipeline guard are both covered: explicit check
    # before retry ensures old IDs cannot be submitted against changed context.
    with pytest.raises(ValueError): pipeline.answer_followup_batch(session, batch['id'], draft, extraction=extractor)
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    assert session['followup_batch']['status'] == 'dismissed'
    assert session['followup_batch']['invalidated_reason'] == 'baseline_changed'
    assert session['followup_batch']['draft_answers'] == draft
    assert session['_followup']['rounds_created'] == 1 and len(planner.plans) == 1
    assert len(extractor.calls) == 2  # Changed baseline is organized once.
    assert session['shared_slots']['current_medications']['value'] == 'Vitamin D'


def test_answered_batch_evidence_survives_later_baseline_edit_without_reroll():
    session, planner, extractor = prepared(); batch = deepcopy(session['followup_batch'])
    pipeline.answer_followup_batch(session, batch['id'], answers(session), extraction=extractor)
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'Vitamin D', 'status': 'FILLED'}], complete=True)
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    assert len(planner.plans) == 1 and session['followup_batch']['status'] == 'answered'
    assert all(engine._owner_slots(session, q['concern_id'])[q['key']]['value'] == 'Patient supplied detail' for q in batch['questions'])


def test_no_longer_applicable_question_is_rejected_before_mutation():
    session, _, extractor = prepared(); q = session['followup_batch']['questions'][0]
    concern = engine._concern(session, q['concern_id'])
    concern['signals']['current_symptom'] = {'present': False}
    before = deepcopy(session)
    with pytest.raises(ValueError, match='field has changed'):
        pipeline.answer_followup_batch(session, session['followup_batch']['id'], answers(session), extraction=extractor)
    assert session == before


@pytest.mark.parametrize('pending', [False, True])
def test_legacy_asked_budget_never_resets_on_upgrade(pending):
    session = baseline(); targets = pipeline.eligible_followups(session)[:5]
    assert len(targets) == 5
    session['_followup'] = {'max_questions': 6, 'asked_targets': [q['target_id'] for q in targets], 'baseline_fingerprint': None}
    session['current_question'] = {'key': targets[-1]['key'], 'concern_id': targets[-1]['concern_id'], 'question': targets[-1]['question']} if pending else None
    planner = BatchPlanner()
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor())
    assert len(session['_followup']['asked_targets']) == 5 and not planner.plans
    if pending:
        assert len(session['followup_batch']['questions']) == 1
        assert session['followup_batch']['questions'][0]['target_id'] == targets[-1]['target_id']
    else:
        assert session['assistant']['mode'] == 'ready' and not session.get('followup_batch')


@pytest.mark.parametrize('text,status', [('I don’t know', 'UNCERTAIN'), ('Prefer not to answer', 'SKIPPED'), ('我不知道', 'UNCERTAIN'), ('暂不回答', 'SKIPPED')])
def test_typed_unknown_or_refusal_is_not_a_filled_clinical_fact(text, status):
    session, _, extractor = prepared(); batch = deepcopy(session['followup_batch'])
    pipeline.answer_followup_batch(session, batch['id'], answers(session, text), extraction=extractor)
    for q in batch['questions']:
        slot = engine._owner_slots(session, q['concern_id'])[q['key']]
        assert slot['status'] == status and slot['evidence']['span'] == text
        if status == 'SKIPPED': assert slot['value'] is None


def test_safety_interruption_preserves_every_submitted_draft_without_accepting_facts():
    session, _, extractor = prepared(); batch = session['followup_batch']; rows = answers(session)
    rows[-1]['value'] = 'I have chest pain now.'
    pipeline.save_followup_draft(session, batch['id'], rows[:1])
    pipeline.answer_followup_batch(session, batch['id'], rows, extraction=extractor)
    assert session['status'] == 'interrupted' and session['followup_batch']['draft_answers'] == rows
    assert all(engine._owner_slots(session, q['concern_id'])[q['key']]['status'] == 'MISSING' for q in batch['questions'])


def test_dynamic_question_translation_keeps_stable_target_and_custom_entry():
    target = {'target_id': 't', 'key': 'medication.synthetic.dose', 'concern_id': 'session',
              'question': 'What dose do you currently take of Vitamin C?', 'label': 'Vitamin C dose'}
    data = {'questions': [{'target_id': 't', 'question': '您目前服用 Vitamin C 的剂量是多少？', 'display_label': 'Vitamin C 的剂量',
                          'rationale': '帮助记录您实际服用的情况。', 'options': []}], 'overview': {'text': '', 'source_ids': []}, 'suggested_concern_ids': []}
    validated = ai.validate_plan(data, [], [], [target], locale='zh-CN')['questions'][0]
    assert validated['target']['target_id'] == 't' and validated['question'] == data['questions'][0]['question']
    assert validated['display_label'] == 'Vitamin C 的剂量' and validated['options'] == []


@pytest.mark.parametrize('locale,fragment', [('zh-CN', '服用多少'), ('zh-TW', '服用多少'), ('ko', '얼마나 복용'), ('ja', 'どのくらい服用')])
def test_legacy_dynamic_question_is_localized_without_new_call_or_budget(locale, fragment):
    session = baseline()
    session['locale'] = locale
    key = 'medication.legacy_item.dose'
    question = 'What dose do you currently take of Vitamin C?'
    session['shared_slots'][key] = engine._slot('Vitamin C · dose', question=question)
    session['items'].append({'id': 'legacy_item', 'kind': 'medication', 'concern_id': 'session',
                             'name': 'Vitamin C', 'fields': {'dose': key}})
    pending_id = pipeline._target_id('session', key)
    session['_followup'] = {'max_questions': 6, 'asked_targets': ['prior1', 'prior2', 'prior3', 'prior4', pending_id], 'baseline_fingerprint': None}
    session['current_question'] = {'key': key, 'question': question, 'why': 'Old English purpose.'}
    planner, extractor = BatchPlanner(), Extractor()
    pipeline.start_followup(session, intelligence=planner, extraction=extractor)
    migrated = session['followup_batch']['questions'][0]
    assert migrated['target_id'] == pending_id and migrated['key'] == key and fragment in migrated['question']
    assert 'Vitamin C' in migrated['question'] and 'What dose' not in migrated['question']
    assert 'dose' not in migrated['display_label'] and 'Old English' not in migrated['why']
    assert len(session['followup_batch']['questions']) == 1 and len(session['_followup']['asked_targets']) == 5
    assert not planner.plans and session['shared_slots'][key]['status'] == 'MISSING'


def dynamic_dose_session():
    session = baseline()
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'Vitamin C', 'status': 'FILLED'}], complete=True)
    item = {'kind': 'medication', 'concern_id': 'session', 'existing_item_id': None, 'name': 'Vitamin C', 'evidence': 'Vitamin C', 'fields': []}
    class DosePlanner(BatchPlanner):
        def plan(self, **kwargs):
            target = next(t for t in kwargs['targets'] if t['key'].endswith('.dose'))
            return super().plan(**{**kwargs, 'targets': [target]})
    planner = DosePlanner()
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor(items=[item]))
    pipeline.answer_followup_batch(session, session['followup_batch']['id'], answers(session, '5 mg'), extraction=Extractor())
    return session, planner, item


def test_dynamic_direct_dose_survives_same_item_reextracted_after_baseline_edit():
    session, planner, item = dynamic_dose_session()
    old_id = session['items'][0]['id']
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'Vitamin C and Vitamin D', 'status': 'FILLED'}], complete=True)
    assert not session['items'] and '5 mg' not in json.dumps(ai.current_sources(session))
    other = {**item, 'name': 'Vitamin D', 'evidence': 'Vitamin D'}
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor(items=[item, other]))
    current = next(i for i in session['items'] if i['name'] == 'Vitamin C')
    dose = session['shared_slots'][current['fields']['dose']]
    assert current['id'] != old_id and dose['value'] == '5 mg' and dose['evidence']['source'] == 'followup_batch'
    assert session['_followup']['rounds_created'] == 1 and len(planner.plans) == 1
    assert any(s['value'] == '5 mg' for s in ai.current_sources(session))


def test_removed_item_direct_dose_stays_private_and_is_not_reused_on_later_readdition():
    session, planner, item = dynamic_dose_session()
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'No medicines', 'status': 'FILLED'}], complete=True)
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor())
    assert not session['items'] and '5 mg' not in json.dumps(ai.current_sources(session))
    forms.apply_baseline(session, [{'concern_id': 'session', 'key': 'current_medications', 'value': 'Vitamin C again', 'status': 'FILLED'}], complete=True)
    pipeline.start_followup(session, intelligence=planner, extraction=Extractor(items=[item]))
    current = session['items'][0]
    assert session['shared_slots'][current['fields']['dose']]['status'] == 'MISSING'
    assert '5 mg' not in json.dumps(ai.current_sources(session))
