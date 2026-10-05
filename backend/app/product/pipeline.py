"""Form → bounded adaptive follow-up → cited AI synthesis.

This wrapper leaves the original evidence/safety engine authoritative. It filters
baseline targets from chat, tracks actual model-operation timings, and never
modifies an approved version or silently substitutes a model.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
import time
from typing import Callable

from . import engine
from .provider import ExtractionProvider, ProviderUnavailable, get_provider
from .intelligence import (IntelligenceProvider, IntelligenceUnavailable, current_sources,
                           current_concerns, get_intelligence, validate_plan,
                           validate_synthesis, unavailable_synthesis)

_ACTIVITY_LIMIT = 30


def _guard(session: dict) -> None:
    if session.get('status') == 'approved':
        raise ValueError('Withdraw sharing before changing approved preparation notes.')
    if not session.get('consent'):
        raise ValueError('Consent was withdrawn. Start a new preparation to continue.')


def _state(session: dict) -> dict:
    if '_followup' not in session:
        try:
            maximum = int(os.getenv('FOLLOWUP_MAX_QUESTIONS', '6'))
        except ValueError:
            maximum = 6
        session['_followup'] = {'max_questions': min(12, max(0, maximum)), 'asked_targets': [], 'baseline_fingerprint': None}
    return session['_followup']


def _record(session: dict, operation: str, started: float, status: str, message: str | None = None) -> None:
    # Real elapsed wall time of the invoked operation; no simulated progress scores.
    activity = session.setdefault('ai_activity', [])
    activity.append({'operation': operation, 'model': session['model'], 'status': status,
                     'duration_ms': round(max(0, (time.perf_counter() - started) * 1000)), 'created_at': engine._now()})
    if message:
        activity[-1]['message'] = message
    del activity[:-_ACTIVITY_LIMIT]



def _safe_failure_message(error: Exception) -> str:
    """Classify into authored messages; never persist exception text or raw bodies."""
    detail = str(error)[:4000].lower()
    categories = [
        (('timed out', 'timeout'), 'OpenAI timed out. Your notes remain saved.'),
        (('quota', 'rate limit'), 'OpenAI quota or rate limit was reached. Your notes remain saved.'),
        (('not configured',), 'OpenAI is not configured. Your notes remain saved.'),
        (('api key', 'access was denied', 'rejected access'), 'OpenAI access could not be authenticated or authorized.'),
        (('question outside', 'eligible follow-up'), 'AI selected a question outside the eligible follow-up fields.'),
        (('unsupported agenda',), 'AI planning returned an unsupported agenda.'),
        (('recorded uncertainty',), 'AI output did not preserve a recorded uncertainty.'),
        (('negative answer',), 'AI output did not preserve an explicit negative answer.'),
        (('introduced a number',), 'AI output introduced a number absent from its cited sources.'),
        (('mixed information between concerns',), 'AI output mixed information between concerns.'),
        (('omitted a concern',), 'AI synthesis omitted a concern with supplied information.'),
        (('citation', 'source references', 'source that is not'), 'AI output did not pass current-source validation.'),
        (('preparation scope', 'unsupported markup'), 'AI output did not pass the preparation scope check.'),
        (('incomplete', 'unusable', 'invalid'), 'AI output was incomplete or had an invalid structure.'),
        (('could not be reached',), 'OpenAI could not be reached. Your notes remain saved.'),
    ]
    for markers, message in categories:
        if any(marker in detail for marker in markers):
            return message
    return 'The AI operation could not be completed. Your notes remain saved.'


def _run(session: dict, operation: str, callback: Callable):
    started = time.perf_counter()
    try:
        value = callback()
    except (ProviderUnavailable, IntelligenceUnavailable) as exc:
        message = _safe_failure_message(exc)
        _record(session, operation, started, 'unavailable', message)
        safe_error = ProviderUnavailable if isinstance(exc, ProviderUnavailable) else IntelligenceUnavailable
        raise safe_error(message) from exc
    except (ValueError, KeyError, TypeError) as exc:
        _record(session, operation, started, 'invalid', 'AI output had an invalid structure. Your notes remain saved.')
        raise IntelligenceUnavailable('AI output could not be processed safely. Your structured notes remain available.') from exc
    _record(session, operation, started, 'completed')
    return value



def _extraction_view(session: dict) -> dict:
    """Extraction sees current values and identities, never private old histories."""
    def slots_view(slots: dict) -> dict:
        return {key: {'label': slot.get('label'), 'value': slot.get('value') if not slot.get('exclude_from_handoff') and slot.get('status') in {'FILLED', 'UNCERTAIN'} else None,
                      'status': slot.get('status'), 'question': slot.get('question'), 'condition': slot.get('condition')}
                for key, slot in slots.items()}
    return {'model': session['model'], 'current_question': deepcopy(session.get('current_question')),
            'shared_slots': slots_view(session.get('shared_slots', {})),
            'concerns': [{'id': concern['id'], 'workflow_id': concern['workflow_id'], 'title': concern['title'],
                          'slots': slots_view(concern.get('slots', {})),
                          'signals': {key: {'present': signal.get('present')} for key, signal in concern.get('signals', {}).items()}}
                         for concern in session.get('concerns', [])],
            'items': [{key: deepcopy(item[key]) for key in ('id', 'kind', 'concern_id', 'name', 'fields') if key in item}
                      for item in session.get('items', [])]}


class _TimedExtractor:
    def __init__(self, session: dict, provider: ExtractionProvider):
        self.session = session
        self.provider = provider

    def extract(self, session: dict, text: str, *, correction: bool = False) -> dict:
        try:
            return _run(self.session, 'extraction', lambda: self.provider.extract(_extraction_view(session), text, correction=correction))
        except IntelligenceUnavailable as exc:
            raise ProviderUnavailable(str(exc)) from exc


def _baseline_keys(session: dict) -> set[tuple[str, str]]:
    baseline = session.get('baseline', {})
    keys = set()
    for row in baseline.get('field_keys', []) + baseline.get('deferred_keys', []):
        if isinstance(row, dict) and isinstance(row.get('key'), str):
            keys.add((row.get('concern_id', 'session'), row['key']))
    owners = [('session', session.get('shared_slots', {}))] + [(c['id'], c.get('slots', {})) for c in session.get('concerns', [])]
    for owner, slots in owners:
        for key, slot in slots.items():
            if slot.get('baseline') or slot.get('baseline_deferred'):
                keys.add((owner, key))
    for owner, key in list(keys):
        if key in {'symptom_onset', 'symptom_duration'}:
            keys.add((owner, 'symptom_onset'))
            keys.add((owner, 'symptom_duration'))
        if key in {'main_concern', 'concern_description', 'agenda_items'}:
            keys.add(('session', 'topic_clarification'))
        # Common shared questions stay shared even if a legacy form used a concern owner.
        if key in engine.SHARED_QUESTIONS:
            keys.add(('session', key))
    return keys


def _target_id(owner: str, key: str) -> str:
    return 'target_' + hashlib.sha256(f'{owner}\0{key}'.encode()).hexdigest()[:20]


def eligible_followups(session: dict) -> list[dict]:
    """Only applicable unresolved non-baseline targets may reach the planner."""
    engine._apply_conditions(session)
    excluded = _baseline_keys(session)
    asked = set(_state(session)['asked_targets'])
    targets = []
    seen = set()
    for question in engine._eligible(session):
        owner, key = question.get('concern_id', 'session'), question['key']
        if (owner, key) in excluded or key in {'main_concern', 'topic_clarification', 'summary_review'}:
            continue
        slots = engine._owner_slots(session, owner)
        slot = slots.get(key) if slots else None
        tid = _target_id(owner, key)
        if not slot or slot.get('status') != 'MISSING' or slot.get('exclude_from_handoff') or tid in asked or tid in seen:
            continue
        seen.add(tid)
        targets.append({'target_id': tid, 'concern_id': owner, 'key': key,
                        'label': slot.get('label', key), 'question': question['question']})
    return targets


def _assistant(session: dict, mode: str, overview: str, *, focus: str = '', rationale: str = '', topics: list[str] | None = None) -> None:
    state = _state(session)
    count = len(state['asked_targets'])
    session['assistant'] = {'mode': mode, 'overview': overview, 'focus': focus, 'rationale': rationale,
                            'suggested_topics': topics or [], 'questions_remaining': max(0, state['max_questions'] - count),
                            'question_count': count}


def _finish_followup(session: dict, message: str, mode: str = 'ready') -> dict:
    session['current_question'] = None
    session['plan']['next_target'] = None
    session['stage'] = 'followup'
    _assistant(session, mode, message)
    return session


def _baseline_rows(session: dict) -> list[dict]:
    rows = []
    for owner, key in sorted(_baseline_keys(session)):
        slots = engine._owner_slots(session, owner)
        slot = slots.get(key) if slots else None
        if not slot or slot.get('exclude_from_handoff') or slot.get('reused_from'):
            continue
        value = slot.get('value')
        if slot.get('status') not in {'FILLED', 'UNCERTAIN'} or not isinstance(value, str) or not value.strip():
            continue
        rows.append({'concern_id': owner, 'key': key, 'status': slot['status'], 'value': value})
    return rows




def _tag_form_evidence(session: dict, evidence: dict, rows: list[dict]) -> None:
    evidence['source'] = 'saved_baseline_form'
    evidence['form_sources'] = [{'concern_id': row['concern_id'], 'key': row['key'],
        'signature': _form_signature(row['concern_id'], row['key'], (engine._owner_slots(session, row['concern_id']) or {}).get(row['key']))} for row in rows]
    evidence['form_uncertain_only'] = bool(rows) and all(row['status'] == 'UNCERTAIN' for row in rows)


def _form_signature(owner: str, key: str, slot: dict | None) -> str:
    payload = [owner, key, slot.get('value') if slot else None, slot.get('status') if slot else None, bool(slot and slot.get('exclude_from_handoff'))]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _stale_derivation(session: dict, evidence: object) -> bool:
    if not isinstance(evidence, dict) or evidence.get('source') != 'saved_baseline_form':
        return False
    for source in evidence.get('form_sources', []):
        owner, key = source.get('concern_id'), source.get('key')
        slot = (engine._owner_slots(session, owner) or {}).get(key)
        if _form_signature(owner, key, slot) != source.get('signature'):
            return True
    return False


def _invalidate_baseline_derivatives(session: dict) -> None:
    """A form edit supersedes only derived material grounded in its old answers."""
    for concern in list(session.get('concerns', [])):
        if not _stale_derivation(session, concern.get('entry_evidence')):
            continue
        independently_supplied = any(slot.get('status') in {'FILLED', 'UNCERTAIN'} and isinstance(slot.get('evidence'), dict) and slot['evidence'].get('source') != 'saved_baseline_form' for slot in concern.get('slots', {}).values())
        if not independently_supplied:
            session.setdefault('_superseded_baseline_concerns', []).append(deepcopy(concern))
            session['concerns'].remove(concern)
            session['items'] = [item for item in session.get('items', []) if item['concern_id'] != concern['id']]
            agenda = session.get('shared_slots', {}).get('agenda_items')
            if agenda and (agenda.get('evidence') or {}).get('source') == 'concern_entries':
                agenda.update(value='; '.join(c['title'] for c in session['concerns']), evidence={'source': 'concern_entries', 'concern_ids': [c['id'] for c in session['concerns']]})
    for item in list(session.get('items', [])):
        if _stale_derivation(session, item.get('evidence')):
            slots = engine._owner_slots(session, item['concern_id']) or {}
            saved = {key: deepcopy(slots[key]) for key in item.get('fields', {}).values() if key in slots}
            session.setdefault('_superseded_baseline_items', []).append({'item': deepcopy(item), 'slots': saved})
            for key in item.get('fields', {}).values(): slots.pop(key, None)
            session['items'].remove(item)
    excluded = _baseline_keys(session)
    for owner, slots in [('session', session['shared_slots'])] + [(c['id'], c['slots']) for c in session['concerns']]:
        for key, slot in list(slots.items()):
            if (owner, key) in excluded or not _stale_derivation(session, slot.get('evidence')):
                continue
            slot.setdefault('history', []).append({'value': slot.get('value'), 'status': slot.get('status'), 'evidence': deepcopy(slot.get('evidence')), 'reason': 'baseline_answer_changed'})
            slot.update(value=None, status='MISSING', evidence=None)
            slot.pop('conflict', None)
            slot.pop('alternatives', None)
        concern = engine._concern(session, owner)
        if concern:
            for key, signal in list(concern.get('signals', {}).items()):
                if _stale_derivation(session, signal.get('evidence')):
                    del concern['signals'][key]
    engine._apply_conditions(session)
    engine._metrics(session)


def _prepare_baseline(session: dict, provider: ExtractionProvider) -> bool:
    """Discover explicit signals/items without rewriting direct form answers.

    Data lines retain explicit owners. Labels are not accepted as patient evidence.
    No synthetic patient chat message or fabricated visit reason is created.
    """
    _invalidate_baseline_derivatives(session)
    rows = _baseline_rows(session)
    fingerprint = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    state = _state(session)
    if state.get('baseline_fingerprint') == fingerprint:
        return True
    if not rows:
        state['baseline_fingerprint'] = fingerprint
        return True
    excluded = _baseline_keys(session)
    protected = {}
    for owner, key in excluded:
        slots = engine._owner_slots(session, owner)
        if slots is not None and key in slots:
            protected[(owner, key)] = deepcopy(slots[key])
    # Actual form values, not labels/status metadata, are the only valid evidence.
    raw_values = [row['value'] for row in rows]
    text = '\n\n'.join(f"Saved form answer (owner={row['concern_id']}, field={row['key']}, status={row['status']}):\n{row['value']}" for row in rows)
    snapshot = _extraction_view(session)
    snapshot['current_question'] = None
    snapshot['_extraction_context'] = 'Saved baseline form answers. Preserve existing owners and facts; extract only explicit additional detail and activation signals.'
    rollback_state = None
    original_concern_ids = {c['id'] for c in session.get('concerns', [])}
    try:
        extraction = _run(session, 'baseline_extraction', lambda: provider.extract(snapshot, text, correction=False))
        if not isinstance(extraction, dict) or any(not isinstance(extraction.get(key, []), list) for key in ('new_concerns', 'facts', 'signals', 'items', 'priority_order')):
            raise IntelligenceUnavailable('Baseline extraction returned unusable output. Your form answers remain saved.')
        filtered = {'facts': [], 'signals': [], 'new_concerns': [], 'items': [], 'priority_order': [], 'needs_clarification': False,
                    'correction_complete': True, 'remove_concerns': [], 'remove_items': []}
        def supporting_rows(span: str, owner: str | None = None, shared_keys: tuple[str, ...] = ()) -> list[dict]:
            matches = [row for row in rows if span and span in row['value']]
            if owner in original_concern_ids:
                matches = [row for row in matches if row['concern_id'] == owner or (row['concern_id'] == 'session' and row['key'] in shared_keys)]
            return matches
        def grounded(candidate: dict, *, value_key: str | None = None) -> bool:
            span = candidate.get('evidence')
            if not isinstance(span, str) or not span.strip() or not supporting_rows(span, candidate.get('concern_id'), ('current_medications',) if candidate.get('key') == 'medication_use' else ()):
                return False
            return value_key is None or (isinstance(candidate.get(value_key), str) and candidate[value_key] in span)
        existing_workflows = {c['workflow_id'] for c in session.get('concerns', [])}
        existing_titles = {c['title'].casefold() for c in session.get('concerns', [])}
        for candidate in extraction.get('new_concerns', [])[:30]:
            if (isinstance(candidate, dict) and grounded(candidate, value_key='title')
                    and isinstance(candidate.get('ref'), str)
                    and any(row['status'] == 'FILLED' for row in supporting_rows(candidate['evidence']))
                    and candidate.get('workflow_id') not in existing_workflows
                    and candidate.get('title', '').casefold() not in existing_titles):
                filtered['new_concerns'].append(candidate)
                existing_workflows.add(candidate['workflow_id'])
                existing_titles.add(candidate['title'].casefold())
        new_refs = {c['ref'] for c in filtered['new_concerns']}
        existing_owners = {'session'} | {c['id'] for c in session.get('concerns', [])} | new_refs
        for candidate in extraction.get('facts', [])[:600]:
            if (isinstance(candidate, dict) and grounded(candidate, value_key='value')
                    and candidate.get('operation', 'set') == 'set'
                    and candidate.get('concern_id') in existing_owners
                    and (candidate.get('concern_id'), candidate.get('key')) not in excluded):
                candidate = deepcopy(candidate)
                if all(row['status'] == 'UNCERTAIN' for row in supporting_rows(candidate['evidence'], candidate.get('concern_id'))):
                    candidate['certainty'] = 'unknown'
                filtered['facts'].append(candidate)
        for name in ('signals', 'priority_order'):
            for candidate in extraction.get(name, [])[:400]:
                if isinstance(candidate, dict) and grounded(candidate) and candidate.get('concern_id') in existing_owners:
                    filtered[name].append(candidate)
        for candidate in extraction.get('items', [])[:100]:
            if isinstance(candidate, dict) and grounded(candidate, value_key='name') and candidate.get('concern_id') in existing_owners:
                item = deepcopy(candidate)
                item['fields'] = [field for field in (candidate.get('fields') if isinstance(candidate.get('fields'), list) else []) if isinstance(field, dict) and grounded({**field, 'concern_id': candidate['concern_id']}, value_key='value')]
                filtered['items'].append(item)
        msg = {'id': 'form_' + engine._id(), 'text': text, 'created_at': engine._now()}
        rollback_state = deepcopy(session)
        result = engine._accept_extraction(session, filtered, msg, False)
        # Restore original form provenance and status even if conditional logic ran.
        for (owner, key), slot in protected.items():
            slots = engine._owner_slots(session, owner)
            if slots is not None:
                slots[key] = slot
        for owner, slots in [('session', session['shared_slots'])] + [(c['id'], c['slots']) for c in session['concerns']]:
            for key, slot in slots.items():
                evidence = slot.get('evidence')
                if isinstance(evidence, dict) and evidence.get('message_id') == msg['id']:
                    _tag_form_evidence(session, evidence, supporting_rows(evidence.get('span', ''), owner))
                    if evidence.get('form_uncertain_only') and slot.get('status') == 'FILLED':
                        slot['status'] = 'UNCERTAIN'
        for concern in session['concerns']:
            entry_evidence = concern.get('entry_evidence')
            if concern['id'] not in original_concern_ids and isinstance(entry_evidence, dict) and entry_evidence.get('message_id') == msg['id']:
                _tag_form_evidence(session, entry_evidence, supporting_rows(entry_evidence.get('span', '')))
            for signal_key, signal in concern.get('signals', {}).items():
                evidence = signal.get('evidence')
                if isinstance(evidence, dict) and evidence.get('message_id') == msg['id']:
                    _tag_form_evidence(session, evidence, supporting_rows(evidence.get('span', ''), concern['id'], ('current_medications',) if signal_key == 'medication_use' else ()))
        for item in session['items']:
            evidence = item.get('evidence')
            if isinstance(evidence, dict) and evidence.get('message_id') == msg['id']:
                _tag_form_evidence(session, evidence, supporting_rows(evidence.get('span', ''), item['concern_id']))
        session.setdefault('audit', []).append({'event': 'baseline_extraction', 'source': 'saved_baseline_form', **result})
        session['ai_status'] = {'mode': 'live', 'model': session['model'], 'message': 'Saved form details were organized using OpenAI.'}
        state['baseline_fingerprint'] = fingerprint
        engine._apply_conditions(session)
        engine._metrics(session)
        return True
    except (ProviderUnavailable, IntelligenceUnavailable, ValueError, KeyError, TypeError) as exc:
        if not isinstance(exc, (ProviderUnavailable, IntelligenceUnavailable)):
            exc = IntelligenceUnavailable('AI baseline extraction could not be validated. Your form answers remain saved.')
        # No partial candidate mutation survives a failed extraction validation.
        if rollback_state is not None:
            session.clear()
            session.update(rollback_state)
        # No direct form answers are lost or falsely replaced if this operation fails.
        for (owner, key), slot in protected.items():
            slots = engine._owner_slots(session, owner)
            if slots is not None:
                slots[key] = slot
        session['ai_status'] = {'mode': 'unavailable', 'model': session['model'], 'message': str(exc)}
        _finish_followup(session, str(exc), 'unavailable')
        return False


def _plan(session: dict, intelligence: IntelligenceProvider) -> dict:
    state = _state(session)
    targets = eligible_followups(session)
    if len(state['asked_targets']) >= state['max_questions']:
        return _finish_followup(session, 'You have reached the optional follow-up limit. Review your notes whenever you are ready.')
    if not targets:
        return _finish_followup(session, 'Your baseline and optional details are ready. You can review your preparation notes now.')
    sources, concerns = current_sources(session), current_concerns(session)
    try:
        plan = _run(session, 'planning', lambda: validate_plan(intelligence.plan(model=session['model'], sources=sources, concerns=concerns, targets=targets), sources, concerns, targets))
    except IntelligenceUnavailable as exc:
        return _finish_followup(session, str(exc), 'unavailable')
    if plan.get('overview_fallback') and session.get('ai_activity'):
        session['ai_activity'][-1]['message'] = 'The optional overview did not pass validation; the validated follow-up plan was retained.'
    target = plan['target']
    if target is None:
        return _finish_followup(session, plan['overview'], 'ready')
    # The model chooses an eligible field. Curated wording cannot add a diagnosis,
    # a second target or a new clinical screening objective.
    question = {'key': target['key'], 'question': target['question'], 'why': plan['rationale']}
    if target['concern_id'] != 'session':
        question['concern_id'] = target['concern_id']
    session['current_question'] = question
    session['plan']['next_target'] = deepcopy(question)
    session['plan']['rationale'] = plan['rationale']
    state['asked_targets'].append(target['target_id'])
    _assistant(session, 'live', plan['overview'], focus=target['label'], rationale=plan['rationale'], topics=plan['suggested_topics'])
    engine._message(session, 'assistant', question['question'])
    return session


def start_followup(session: dict, *, intelligence: IntelligenceProvider | None = None, extraction: ExtractionProvider | None = None) -> dict:
    _guard(session)
    if session.get('status') == 'interrupted':
        return session
    if not session.get('baseline', {}).get('completed'):
        raise ValueError('Save and finish your baseline form before starting optional follow-up.')
    if session.get('status') == 'review':
        # Retrying should not reopen a patient-finished review unexpectedly.
        return session
    session['status'] = 'active'
    session['stage'] = 'followup'
    session.setdefault('followup_started_at', engine._now())
    state = _state(session)
    _invalidate_baseline_derivatives(session)
    fresh_fingerprint = hashlib.sha256(json.dumps(_baseline_rows(session), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    existing = session.get('current_question')
    if existing and session.get('assistant', {}).get('mode') == 'live' and state.get('baseline_fingerprint') == fresh_fingerprint:
        owner = existing.get('concern_id', 'session')
        tid = _target_id(owner, existing['key'])
        slot = (engine._owner_slots(session, owner) or {}).get(existing['key'])
        if tid in state['asked_targets'] and slot and slot['status'] == 'MISSING' and (owner, existing['key']) not in _baseline_keys(session):
            return session
    if not _prepare_baseline(session, extraction or get_provider()):
        return session
    return _plan(session, intelligence or get_intelligence())


def _synthesize(session: dict, intelligence: IntelligenceProvider) -> dict:
    summary = session.get('summary')
    if not summary or session.get('status') != 'review':
        return session
    session['stage'] = 'review'
    if summary.get('needs_reconciliation') or session.get('unreconciled_corrections'):
        message = 'Your correction is saved but has not been reconciled. Retry the correction before approving; no updated AI summary has been generated.'
        summary['synthesis'] = unavailable_synthesis(session, message, include_sources=False)
        _assistant(session, 'unavailable', message)
        return session
    sources, concerns = current_sources(session), current_concerns(session)
    try:
        result = _run(session, 'synthesis', lambda: validate_synthesis(intelligence.synthesize(model=session['model'], sources=sources, concerns=concerns), sources, concerns))
        summary['synthesis'] = {'status': 'live', 'model': session['model'], 'generated_at': engine._now(),
                                **result, 'sources': sources,
                                'message': 'Review the English wording and any translations against your original source details before sharing.'}
        _assistant(session, 'live', 'Your AI preparation summary is ready. Check the wording, translations and source details before approving.')
    except IntelligenceUnavailable as exc:
        summary['synthesis'] = unavailable_synthesis(session, str(exc))
        _assistant(session, 'unavailable', str(exc))
    return session


def process_message(session: dict, text: str, action: str = 'answer', *, intelligence: IntelligenceProvider | None = None,
                    extraction: ExtractionProvider | None = None) -> dict:
    _guard(session)
    before_count = len(session.get('messages', []))
    was_review = session.get('status') == 'review'
    engine.process_message(session, text, action, provider=_TimedExtractor(session, extraction or get_provider()))
    if session.get('status') in {'interrupted', 'withdrawn'}:
        session['current_question'] = None
        return session
    # Keep patient text; suppress the legacy engine's next baseline/fallback question.
    session['messages'][before_count:] = [m for m in session['messages'][before_count:] if m['role'] != 'assistant']
    if session.get('status') == 'review' or was_review:
        return _synthesize(session, intelligence or get_intelligence())
    session['stage'] = 'followup'
    if session.get('ai_status', {}).get('mode') == 'unavailable' and action == 'answer':
        return _finish_followup(session, 'Your response is saved, but AI extraction is unavailable. You can review your structured notes or retry optional follow-up.', 'unavailable')
    return _plan(session, intelligence or get_intelligence())


def build_review(session: dict, correction: str | None = None, *, intelligence: IntelligenceProvider | None = None,
                 extraction: ExtractionProvider | None = None) -> dict:
    _guard(session)
    _invalidate_baseline_derivatives(session)
    before_count = len(session.get('messages', []))
    engine.build_review(session, correction, provider=_TimedExtractor(session, extraction or get_provider()))
    if session.get('status') in {'interrupted', 'withdrawn'}:
        return session
    if correction:
        session['messages'][before_count:] = [m for m in session['messages'][before_count:] if m['role'] != 'assistant']
    return _synthesize(session, intelligence or get_intelligence())
