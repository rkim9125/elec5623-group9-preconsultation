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
import uuid
from typing import Callable

from . import engine
from . import oldcarts
from .followup_copy import legacy_question_copy, followup_copy, localized_lifecycle
from .locales import translate_text, field_label, prose_matches_locale
from .provider import ExtractionProvider, ProviderUnavailable, get_provider
from .intelligence import (IntelligenceProvider, IntelligenceUnavailable, current_sources,
                           current_concerns, get_intelligence, validate_plan,
                           validate_synthesis, unavailable_synthesis, validate_presentation_translation)

_ACTIVITY_LIMIT = 30


def _guard(session: dict) -> None:
    if session.get('status') == 'approved':
        raise ValueError('Withdraw sharing before changing approved preparation notes.')
    if not session.get('consent'):
        raise ValueError('Consent was withdrawn. Start a new preparation to continue.')


def _state(session: dict) -> dict:
    state = session.setdefault('_followup', {'asked_targets': [], 'baseline_fingerprint': None})
    try:
        maximum = int(os.getenv('FOLLOWUP_MAX_QUESTIONS', '5'))
    except ValueError:
        maximum = 5
    # Configuration cannot expand the patient-facing five-question contract.
    state['max_questions'] = min(5, max(0, maximum))
    state.setdefault('asked_targets', [])
    state.setdefault('rounds_created', 0)
    state.setdefault('completed', False)
    return state


def _record(session: dict, operation: str, started: float, status: str, message: str | None = None) -> None:
    # Real elapsed wall time of the invoked operation; no simulated progress scores.
    activity = session.setdefault('ai_activity', [])
    activity.append({'operation': operation, 'model': session['model'], 'status': status,
                     'duration_ms': round(max(0, (time.perf_counter() - started) * 1000)), 'created_at': engine._now()})
    if message:
        activity[-1]['message'] = message
    del activity[:-_ACTIVITY_LIMIT]



def _safe_failure_message(error: Exception, locale: str = 'en') -> str:
    """Classify into authored messages; never persist exception text or raw bodies."""
    detail = str(error)[:4000].lower()
    if 'selected patient language' in detail or 'translation' in detail:
        return followup_copy('language_unavailable', locale)
    categories = [
        (('unavailable for this project',), 'The selected AI model could not be used. Check model access or choose another model in Advanced options; no model was substituted.'),
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
            translated = translate_text(message, locale)
            return translated if prose_matches_locale(translated, locale) else followup_copy('ai_unavailable', locale)
    return followup_copy('ai_unavailable', locale)


def _run(session: dict, operation: str, callback: Callable):
    started = time.perf_counter()
    try:
        value = callback()
    except (ProviderUnavailable, IntelligenceUnavailable) as exc:
        message = _safe_failure_message(exc, session.get('locale', 'en'))
        _record(session, operation, started, 'unavailable', message)
        safe_error = ProviderUnavailable if isinstance(exc, ProviderUnavailable) else IntelligenceUnavailable
        raise safe_error(message) from exc
    except (ValueError, KeyError, TypeError) as exc:
        message = followup_copy('ai_unavailable', session.get('locale', 'en'))
        _record(session, operation, started, 'invalid', message)
        raise IntelligenceUnavailable(message) from exc
    _record(session, operation, started, 'completed')
    return value



def _extraction_view(session: dict) -> dict:
    """Extraction sees current values and identities, never private old histories."""
    def slots_view(slots: dict) -> dict:
        return {key: {'label': slot.get('label'), 'value': slot.get('value') if not slot.get('exclude_from_handoff') and slot.get('status') in {'FILLED', 'UNCERTAIN'} else None,
                      'status': slot.get('status'), 'question': slot.get('question'), 'condition': slot.get('condition')}
                for key, slot in slots.items()}
    return {'model': session['model'], 'locale': session.get('locale', 'en'), 'current_question': deepcopy(session.get('current_question')),
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
        concern = engine._concern(session, owner)
        dimension = oldcarts.dimension_for_key(concern['workflow_id'], key) if concern else None
        targets.append({'target_id': tid, 'concern_id': owner, 'key': key,
                        'label': slot.get('label', key), 'question': question['question'],
                        **({'oldcarts_dimension': dimension} if dimension else {})})
    return oldcarts.priority_targets(session, targets)


def _assistant(session: dict, mode: str, overview: str, *, focus: str = '', rationale: str = '', topics: list[str] | None = None) -> None:
    state = _state(session)
    count = len(state['asked_targets'])
    locale = session.get('locale', 'en')
    overview = localized_lifecycle(translate_text(overview, locale), locale)
    rationale = localized_lifecycle(translate_text(rationale, locale), locale)
    if locale != 'en' and overview and not prose_matches_locale(overview, locale):
        overview = followup_copy('ai_unavailable' if mode == 'unavailable' else 'optional_ready', locale)
    if locale != 'en' and rationale and not prose_matches_locale(rationale, locale):
        rationale = followup_copy('batch_reason', locale)
    session['assistant'] = {'mode': mode, 'locale': locale, 'overview': overview, 'focus': focus, 'rationale': rationale,
                            'suggested_topics': topics or [], 'questions_remaining': len(session.get('followup_batch', {}).get('questions', [])) if session.get('followup_batch', {}).get('status') == 'pending' else 0,
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
            session.setdefault('_superseded_baseline_items', []).append({'item': deepcopy(item), 'slots': saved, 'restore_revision': session.get('baseline', {}).get('revision', 0)})
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


def _restore_independent_item_answers(session: dict, message_id: str) -> None:
    """Reconnect direct answers only to an item re-confirmed in this revision."""
    def independent(slot: dict) -> bool:
        evidence = slot.get('evidence') or {}
        direct = evidence.get('source') in {'followup_batch', 'direct_patient_response', 'patient_form', 'patient_text'} and not str(evidence.get('message_id', '')).startswith('form_') and not evidence.get('form_sources')
        return direct or any(independent(row) for row in slot.get('alternatives', []) if isinstance(row, dict))

    revision = session.get('baseline', {}).get('revision', 0)
    for snapshot in session.get('_superseded_baseline_items', []):
        if snapshot.get('restore_revision') != revision or snapshot.get('restoration_checked'):
            continue
        snapshot['restoration_checked'] = True
        previous = snapshot['item']
        current = next((item for item in session.get('items', [])
                        if item['kind'] == previous['kind'] and item['concern_id'] == previous['concern_id']
                        and item['name'].casefold() == previous['name'].casefold()
                        and (item.get('evidence') or {}).get('message_id') == message_id), None)
        if not current:
            continue
        slots = engine._owner_slots(session, current['concern_id']) or {}
        for field, old_key in previous.get('fields', {}).items():
            old = snapshot.get('slots', {}).get(old_key)
            if not old or old.get('exclude_from_handoff') or old.get('status') not in {'FILLED', 'UNCERTAIN', 'SKIPPED'} or not independent(old):
                continue
            key = current['fields'].setdefault(field, f"{current['kind']}.{current['id']}.{field}")
            fresh = slots.get(key)
            restored = deepcopy(old)
            if fresh and fresh.get('status') in {'FILLED', 'UNCERTAIN', 'SKIPPED'} and (fresh.get('value'), fresh.get('status')) != (old.get('value'), old.get('status')):
                engine._update_slot(restored, fresh.get('value'), fresh['status'], deepcopy(fresh.get('evidence')), correction=False)
            slots[key] = restored
            session.setdefault('audit', []).append({'event': 'direct_item_answer_reconnected', 'concern_id': current['concern_id'], 'item_id': current['id'], 'key': key})


def _prepare_baseline(session: dict, provider: ExtractionProvider, *, prefill: bool = False) -> bool:
    """Discover explicit signals/items without rewriting direct form answers.

    Data lines retain explicit owners. Labels are not accepted as patient evidence.
    No synthetic patient chat message or fabricated visit reason is created.
    """
    _invalidate_baseline_derivatives(session)
    rows = _baseline_rows(session)
    if prefill:
        # Early organisation uses only saved, patient-authored answers. Empty
        # wizard fields remain eligible; explicit uncertainty/refusal is protected.
        rows = []
        owners = [('session', session.get('shared_slots', {}))] + [(c['id'], c['slots']) for c in session.get('concerns', [])]
        for owner, slots in owners:
            for key, slot in slots.items():
                if (slot.get('status') in {'FILLED', 'UNCERTAIN'} and not slot.get('exclude_from_handoff')
                        and not slot.get('reused_from') and isinstance(slot.get('value'), str) and slot['value'].strip()
                        and (slot.get('evidence') or {}).get('source') == 'patient_form'):
                    rows.append({'concern_id': owner, 'key': key, 'status': slot['status'], 'value': slot['value']})
        rows.sort(key=lambda row: (row['concern_id'], row['key']))
    fingerprint = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    state = _state(session)
    fingerprint_key = 'description_fingerprint' if prefill else 'baseline_fingerprint'
    if state.get(fingerprint_key) == fingerprint:
        return True
    if not rows:
        state[fingerprint_key] = fingerprint
        return True
    excluded = _baseline_keys(session)
    if prefill:
        excluded = {(owner, key) for owner, slots in owners for key, slot in slots.items()
                    if slot.get('status') in {'FILLED', 'UNCERTAIN', 'SKIPPED'}
                    and (slot.get('evidence') or {}).get('source') != 'saved_baseline_form'}
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
        _restore_independent_item_answers(session, msg['id'])
        session.setdefault('audit', []).append({'event': 'baseline_extraction', 'source': 'saved_baseline_form', **result})
        session['ai_status'] = {'mode': 'live', 'model': session['model'], 'message': followup_copy('form_organized', session.get('locale', 'en'))}
        state[fingerprint_key] = fingerprint
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
        message = _safe_failure_message(exc, session.get('locale', 'en'))
        session['ai_status'] = {'mode': 'unavailable', 'model': session['model'], 'message': message}
        if not prefill:
            _finish_followup(session, message, 'unavailable')
        return False


def organize_baseline(session: dict, *, extraction: ExtractionProvider | None = None) -> dict:
    """Fill supported gaps from saved answers without starting an interview round."""
    _guard(session)
    if session.get('status') != 'active' or session.get('stage') != 'baseline' or session.get('baseline', {}).get('completed'):
        raise ValueError('Return to your editable preparation before organising these answers.')
    _prepare_baseline(session, extraction or get_provider(), prefill=True)
    return session


def _batch_context(session: dict) -> str:
    # Includes the revision so blank/declined edits also invalidate old questions.
    data = [session.get('baseline', {}).get('revision', 0), _baseline_rows(session)]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def invalidate_followup_for_baseline(session: dict) -> None:
    """Keep the per-visit budget, but never reuse questions for replaced answers."""
    batch = session.get('followup_batch')
    if not batch:
        return
    if batch.get('status') == 'pending':
        batch.update(status='dismissed', invalidated_reason='baseline_changed')
        _state(session)['completed'] = True
        session['current_question'] = None
        session['plan']['next_target'] = None
    session.setdefault('audit', []).append({'event': 'followup_baseline_changed', 'batch_id': batch['id']})


def _publish_batch(session: dict, questions: list[dict], overview: str, *, reason: str | None = None) -> dict:
    state = _state(session)
    if state['rounds_created'] >= 2 or len(questions) > 5:
        raise ValueError('The follow-up question limit has been reached. Review your notes to continue.')
    batch_id = 'batch_' + uuid.uuid4().hex
    previous = session.get('followup_batch')
    if previous:
        session.setdefault('_followup_batches', []).append(deepcopy(previous))
    state['rounds_created'] += 1
    state['batch_context'] = _batch_context(session)
    rows = []
    for index, item in enumerate(questions):
        target = item['target']
        rows.append({'id': f'{batch_id}_{index + 1}', 'target_id': target['target_id'],
                     'concern_id': target['concern_id'], 'key': target['key'],
                     'question': item.get('question', target['question']), 'display_label': item.get('display_label', target.get('label', target['key'])), 'why': item['rationale'],
                     'options': item.get('options', []), 'allow_custom': True})
        concern = engine._concern(session, target['concern_id'])
        dimension = oldcarts.dimension_for_key(concern['workflow_id'], target['key']) if concern else None
        if dimension:
            rows[-1]['oldcarts_dimension'] = dimension
        if target['target_id'] not in state['asked_targets']:
            state['asked_targets'].append(target['target_id'])
    session['followup_batch'] = {'id': batch_id, 'round': state['rounds_created'], 'status': 'pending',
                                  'overview': localized_lifecycle(overview, session.get('locale', 'en')), 'questions': rows, 'draft_answers': [],
                                  'created_at': engine._now(), 'locale': session.get('locale', 'en')}
    if reason:
        session['followup_batch']['second_round_reason'] = reason
    session['current_question'] = None
    session['plan']['next_target'] = None
    session['plan']['rationale'] = reason or followup_copy('batch_reason', session.get('locale', 'en'))
    _assistant(session, 'live', overview, rationale=session['plan']['rationale'])
    engine._message(session, 'assistant', '\n\n'.join(row['question'] for row in rows))
    return session


def relocalize_pending_followup(session: dict, *, intelligence: IntelligenceProvider | None = None) -> dict:
    """Translate a pending batch in place, preserving identities, answers and budget.

    All candidate text is validated before mutation. This is presentation work,
    never another planning round or permission to replace patient evidence.
    """
    original = session.get('followup_batch') or {}
    locale = session.get('locale', 'en')
    if original.get('status') != 'pending' or original.get('locale') == locale:
        return session
    batch = deepcopy(original)
    pending, destinations = {}, {}

    def collect(container: dict, key: str, text: str, identity: str, *, authored: str | None = None) -> None:
        candidate = localized_lifecycle(translate_text(text, locale), locale)
        if authored is not None and prose_matches_locale(authored, locale):
            container[key] = authored
        elif candidate != text and prose_matches_locale(candidate, locale):
            container[key] = candidate
        elif locale == 'en' and original.get('locale') is None and prose_matches_locale(candidate, 'en'):
            # Pre-locale batches were often already English. Preserve their
            # existing English copy without a remote presentation-only call.
            container[key] = candidate
        else:
            pending[identity] = text
            destinations[identity] = (container, key)

    for row in batch.get('questions', []):
        slot = (engine._owner_slots(session, row['concern_id']) or {}).get(row['key'], {})
        target = {'concern_id': row['concern_id'], 'key': row['key'],
                  'question': slot.get('question') or row['question'],
                  'label': slot.get('label') or row.get('display_label') or row['key']}
        copy = legacy_question_copy(session, target)
        question = translate_text(copy['question'], locale)
        label = field_label(row['key'], copy['display_label'], locale)
        # Curated text is authoritative for scope; dynamic copies keep item names.
        collect(row, 'question', row['question'], row['id'] + '.question', authored=question)
        collect(row, 'display_label', row.get('display_label') or target['label'], row['id'] + '.label', authored=label)
        collect(row, 'why', row.get('why') or copy['rationale'], row['id'] + '.why',
                authored=copy['rationale'] if not row.get('why') else None)
        for index, option in enumerate(row.get('options', [])):
            collect(option, 'label', option['label'], f"{row['id']}.option{index}.label")
            collect(option, 'value', option['value'], f"{row['id']}.option{index}.value")
    collect(batch, 'overview', batch.get('overview') or followup_copy('optional_ready', 'en'), 'overview')
    if batch.get('second_round_reason'):
        old_reason = batch['second_round_reason']
        authored_reason = next((parts[0] for key, parts in _CONFLICT_COPY.items() if key == locale), None) if old_reason in {parts[0] for parts in _CONFLICT_COPY.values()} else None
        collect(batch, 'second_round_reason', old_reason, 'second_round_reason', authored=authored_reason)
    if pending:
        provider = intelligence or get_intelligence()
        translator = getattr(provider, 'translate_presentation', None)
        if not callable(translator):
            raise IntelligenceUnavailable(followup_copy('language_unavailable', locale))
        translated = translator(model=session['model'], texts=pending, locale=locale)
        # Injected providers obey the same identity/content boundary as live calls.
        if not isinstance(translated, dict):
            raise IntelligenceUnavailable(followup_copy('language_unavailable', locale))
        translated = validate_presentation_translation({'translations': [{'id': key, 'text': value} for key, value in translated.items()]}, pending, locale)
        for identity, text in translated.items():
            container, key = destinations[identity]
            container[key] = text
    batch['locale'] = locale
    batch['localized_at'] = engine._now()
    session['followup_batch'] = batch
    session['plan']['rationale'] = batch.get('second_round_reason') or followup_copy('batch_reason', locale)
    _assistant(session, 'live', batch['overview'], rationale=session['plan']['rationale'])
    return session


def _plan(session: dict, intelligence: IntelligenceProvider) -> dict:
    state = _state(session)
    if session.get('followup_batch', {}).get('status') == 'pending':
        session['current_question'] = None
        session['plan']['next_target'] = None
        return relocalize_pending_followup(session, intelligence=intelligence)
    if state['completed'] or state['rounds_created']:
        return _finish_followup(session, 'Your baseline answers changed. Previous follow-up questions were closed; review your updated notes.' if session.get('followup_batch', {}).get('invalidated_reason') == 'baseline_changed' else 'Your follow-up answers are saved. You can review your preparation notes now.')
    targets = eligible_followups(session)
    remaining = max(0, state['max_questions'] - len(state['asked_targets']))
    # Migrate an already-displayed legacy question without charging it twice.
    legacy = session.get('current_question') or {}
    owner, key = legacy.get('concern_id', 'session'), legacy.get('key')
    slot = (engine._owner_slots(session, owner) or {}).get(key)
    legacy_questions = []
    if key and _target_id(owner, key) in state['asked_targets'] and slot and slot['status'] == 'MISSING' and not slot.get('exclude_from_handoff') and (owner, key) not in _baseline_keys(session):
        target = {'target_id': _target_id(owner, key), 'concern_id': owner, 'key': key, 'question': legacy['question'], 'label': slot.get('label', key)}
        legacy_options = [{**option, 'label': translate_text(option['label'], session.get('locale', 'en')),
                           'value': translate_text(option['value'], session.get('locale', 'en'))} for option in legacy.get('options', [])]
        legacy_options = [option for option in legacy_options if all(prose_matches_locale(option[field], session.get('locale', 'en')) for field in ('label', 'value'))]
        legacy_questions = [{'target': target, **legacy_question_copy(session, target, legacy.get('why')), 'options': legacy_options}]
    if (not targets or not remaining) and legacy_questions:
        return _publish_batch(session, legacy_questions, 'You can answer the remaining question or review your notes.')
    if not targets or not remaining:
        state['completed'] = True
        return _finish_followup(session, 'Your baseline and optional details are ready. You can review your preparation notes now.')
    sources, concerns = current_sources(session), current_concerns(session)
    try:
        plan = _run(session, 'planning', lambda: validate_plan(intelligence.plan(model=session['model'], sources=sources, concerns=concerns, targets=targets, locale=session.get('locale', 'en')), sources, concerns, targets, locale=session.get('locale', 'en')))
    except IntelligenceUnavailable as exc:
        return _finish_followup(session, str(exc), 'unavailable')
    if plan.get('overview_fallback') and session.get('ai_activity'):
        session['ai_activity'][-1]['message'] = 'The optional overview did not pass validation; the validated follow-up plan was retained.'
    # The model can select fewer questions; the authored coverage order controls
    # which selected details fit the bounded batch. Never turn a gap into a fact.
    target_order = {target['target_id']: index for index, target in enumerate(targets)}
    planned = sorted(plan['questions'], key=lambda item: target_order.get(item['target']['target_id'], len(targets)))
    questions = legacy_questions + planned[:remaining]
    if not questions:
        state['completed'] = True
        return _finish_followup(session, plan['overview'], 'ready')
    return _publish_batch(session, questions, plan['overview'])


def can_start_followup(session: dict) -> bool:
    if session.get('baseline', {}).get('completed'):
        return True
    # Existing conversation drafts can explicitly upgrade without inventing a
    # completed wizard. An unfinished modern wizard still requires completion.
    legacy_chat = session.get('mode') == 'chat' or not session.get('baseline')
    return legacy_chat and any(message.get('role') == 'patient' for message in session.get('messages', []))


def start_followup(session: dict, *, intelligence: IntelligenceProvider | None = None, extraction: ExtractionProvider | None = None) -> dict:
    _guard(session)
    if session.get('status') == 'interrupted':
        return session
    if not can_start_followup(session):
        raise ValueError('Save and finish your baseline form before starting optional follow-up.')
    if session.get('status') == 'review':
        return session
    session['status'] = 'active'
    session['stage'] = 'followup'
    session.setdefault('followup_started_at', engine._now())
    state = _state(session)
    # Reconcile a changed baseline even after follow-up; this cannot reset the
    # question budget or reintroduce a completed/declined interview.
    if session.get('followup_batch') and state.get('batch_context') != _batch_context(session):
        invalidate_followup_for_baseline(session)
    if not _prepare_baseline(session, extraction or get_provider()):
        return session
    # Retries with an unchanged baseline return the same pending question IDs.
    if session.get('followup_batch', {}).get('status') == 'pending':
        session['current_question'] = None
        return relocalize_pending_followup(session, intelligence=intelligence)
    if state['completed'] or state['rounds_created']:
        return _finish_followup(session, 'Your baseline answers changed. Previous follow-up questions were closed; review your updated notes.' if session.get('followup_batch', {}).get('invalidated_reason') == 'baseline_changed' else 'Your follow-up answers are saved. You can review your preparation notes now.')

    return _plan(session, intelligence or get_intelligence())


def _validate_batch_answers(session: dict, batch_id: str, answers: list[dict], *, draft: bool = False) -> list[dict]:
    _guard(session)
    if session.get('status') in {'interrupted', 'review'}:
        raise ValueError('This preparation cannot accept follow-up answers in its current state.')
    batch = session.get('followup_batch') or {}
    if batch.get('id') != batch_id or batch.get('status') != 'pending':
        raise ValueError('This follow-up batch is no longer pending. Refresh before continuing.')
    if _state(session).get('batch_context') != _batch_context(session):
        raise ValueError('Your baseline answers changed. Review the updated preparation before continuing.')
    applicable = deepcopy(session)
    engine._apply_conditions(applicable)
    questions = {q['id']: q for q in batch['questions']}
    if not isinstance(answers, list) or len(answers) > 5:
        raise ValueError('Submit no more than five follow-up answers.')
    normalized, seen = [], set()
    for answer in answers:
        if not isinstance(answer, dict):
            raise ValueError('Choose a valid follow-up answer.')
        qid, status, value = answer.get('question_id'), answer.get('status', 'FILLED'), answer.get('value')
        if not isinstance(qid, str) or qid not in questions or qid in seen:
            raise ValueError('Follow-up answers must contain each current question exactly once.')
        if status not in ({'FILLED', 'UNCERTAIN', 'SKIPPED', 'MISSING'} if draft else {'FILLED', 'UNCERTAIN', 'SKIPPED'}):
            raise ValueError('Choose an answer, unsure, or skip for each question.')
        if value is not None and (not isinstance(value, str) or len(value) > 6000):
            raise ValueError('Keep each follow-up answer under 6,000 characters.')
        value = value.strip() if isinstance(value, str) else None
        if not draft and status == 'FILLED' and value:
            control = value.strip('.!。！ ').casefold()
            if engine._UNKNOWN.match(value) or control in {'我不知道', '不知道', '我不确定', '我不確定', '不确定', '不確定', '不清楚', '모르겠어요', '모릅니다', 'わかりません', '分かりません'}:
                status = 'UNCERTAIN'
            elif engine._SKIP.match(value) or control in {'暂不回答', '暫不回答', '不想回答', '不愿回答', '不願回答', '跳过', '跳過', '답변하지 않겠습니다', '건너뛰기', '回答を控えます', 'スキップ'}:
                status = 'SKIPPED'
        if not draft and status == 'FILLED' and not value:
            raise ValueError('Enter an answer, or choose unsure or skip.')
        q = questions[qid]
        slot = (engine._owner_slots(applicable, q['concern_id']) or {}).get(q['key'])
        can_answer = slot and (slot.get('status') == 'MISSING' or (batch.get('round') == 2 and slot.get('conflict')))
        if not can_answer or slot.get('exclude_from_handoff'):
            raise ValueError('A follow-up field has changed. Review your notes before continuing.')
        seen.add(qid)
        normalized.append({'question_id': qid, 'status': status, 'value': value})
    if not draft and seen != set(questions):
        raise ValueError('Answer, skip, or mark unsure for every question before continuing.')
    return normalized


def save_followup_draft(session: dict, batch_id: str, answers: list[dict]) -> dict:
    normalized = _validate_batch_answers(session, batch_id, answers, draft=True)
    batch = session['followup_batch']
    existing = {a['question_id']: a for a in batch.get('draft_answers', [])}
    existing.update({a['question_id']: a for a in normalized})
    batch['draft_answers'] = [existing[q['id']] for q in batch['questions'] if q['id'] in existing]
    return session


def _batch_extraction(session: dict, rows: list[dict], msg: dict, provider: ExtractionProvider) -> bool:
    useful = [row for row in rows if row['status'] in {'FILLED', 'UNCERTAIN'} and row['value']]
    if not useful:
        return True
    protected = {(row['concern_id'], row['key']): deepcopy(engine._owner_slots(session, row['concern_id'])[row['key']]) for row in rows}
    snapshot = _extraction_view(session)
    snapshot['current_question'] = None
    snapshot['_extraction_context'] = 'A complete follow-up batch. Direct answers are already saved. Extract only additional explicit details; preserve each owner and unknown/refused status.'
    # Refused text and question labels never enter the extraction payload as evidence.
    text = '\n\n'.join(f"Follow-up answer (owner={row['concern_id']}, field={row['key']}, status={row['status']}):\n{row['value']}" for row in useful)
    before = deepcopy(session)
    try:
        data = _run(session, 'extraction', lambda: provider.extract(snapshot, text, correction=False))
        if not isinstance(data, dict) or any(not isinstance(data.get(key, []), list) for key in ('new_concerns', 'facts', 'signals', 'items', 'priority_order')):
            raise IntelligenceUnavailable('AI follow-up extraction returned invalid output. Your direct answers remain saved.')
        def matching(candidate: dict, *, owner: bool = True) -> list[dict]:
            span = candidate.get('evidence')
            if not isinstance(span, str) or not span.strip():
                return []
            found = [row for row in useful if span in row['value']]
            cid = candidate.get('concern_id')
            if owner and cid in {'session', *[c['id'] for c in session['concerns']]} and not (cid == 'session' and candidate.get('key') in {'current_medications', 'allergies'}):
                found = [row for row in found if row['concern_id'] == cid or (row['key'] == 'current_medications' and candidate.get('key') == 'medication_use')]
            return found
        filtered = {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': [],
                    'needs_clarification': False, 'correction_complete': True, 'remove_concerns': [], 'remove_items': []}
        for candidate in data.get('new_concerns', [])[:30]:
            if isinstance(candidate, dict) and any(row['status'] == 'FILLED' for row in matching(candidate, owner=False)):
                filtered['new_concerns'].append(candidate)
        for candidate in data.get('facts', [])[:600]:
            if not isinstance(candidate, dict) or (candidate.get('concern_id'), candidate.get('key')) in protected or candidate.get('operation', 'set') != 'set':
                continue
            supports = matching(candidate)
            if supports:
                candidate = deepcopy(candidate)
                if all(row['status'] == 'UNCERTAIN' for row in supports):
                    candidate['certainty'] = 'unknown'
                filtered['facts'].append(candidate)
        for name in ('signals', 'priority_order'):
            for candidate in data.get(name, [])[:400]:
                if isinstance(candidate, dict) and any(row['status'] == 'FILLED' for row in matching(candidate)):
                    filtered[name].append(candidate)
        for candidate in data.get('items', [])[:200]:
            if not isinstance(candidate, dict):
                continue
            supports = matching(candidate)
            if not supports:
                continue
            candidate = deepcopy(candidate)
            candidate['fields'] = [field for field in candidate.get('fields', []) if isinstance(field, dict) and isinstance(field.get('evidence'), str) and any(field['evidence'] in row['value'] for row in supports)]
            if all(row['status'] == 'UNCERTAIN' for row in supports):
                for field in candidate['fields']:
                    field['certainty'] = 'unknown'
            filtered['items'].append(candidate)
        accepted = engine._accept_extraction(session, filtered, msg, False)
        for item in session.get('items', []):
            evidence = item.get('evidence') or {}
            supports = matching({'concern_id': item['concern_id'], 'evidence': evidence.get('span')})
            if evidence.get('message_id') == msg['id'] and supports and all(row['status'] == 'UNCERTAIN' for row in supports):
                slots = engine._owner_slots(session, item['concern_id']) or {}
                for key in item.get('fields', {}).values():
                    if key in slots and slots[key].get('status') == 'FILLED':
                        slots[key]['status'] = 'UNCERTAIN'
        for (owner, key), slot in protected.items():
            engine._owner_slots(session, owner)[key] = slot
        session.setdefault('audit', []).append({'event': 'followup_batch_extraction', 'message_id': msg['id'], **accepted})
        session['ai_status'] = {'mode': 'live', 'model': session['model'], 'message': followup_copy('followup_organized', session.get('locale', 'en'))}
        engine._apply_conditions(session)
        engine._metrics(session)
        return True
    except (ProviderUnavailable, IntelligenceUnavailable, ValueError, KeyError, TypeError) as exc:
        activity = session.get('ai_activity', [])
        session.clear()
        session.update(before)
        session['ai_activity'] = activity
        session['ai_status'] = {'mode': 'unavailable', 'model': session['model'], 'message': _safe_failure_message(exc, session.get('locale', 'en'))}
        return False


_CONFLICT_COPY = {
    'en': ('One final clarification is needed because your new answers introduced conflicting medicine or allergy details.', 'Your answers about {label} differ. What would you like recorded?'),
    'zh-CN': ('您的新回答中出现了相互矛盾的用药或过敏信息，需要最后确认一次。', '关于「{label}」的回答不一致。您希望记录什么？'),
    'zh-TW': ('您的新回答中出現了相互矛盾的用藥或過敏資訊，需要最後確認一次。', '關於「{label}」的回答不一致。您希望記錄什麼？'),
    'ja': ('新しい回答で薬やアレルギーの情報に食い違いが生じたため、最後に確認します。', '「{label}」について回答が異なります。どのように記録しますか？'),
    'ko': ('새 답변의 약물 또는 알레르기 정보가 서로 달라 마지막으로 확인합니다.', '「{label}」에 대한 답변이 다릅니다. 무엇을 기록할까요?'),
}


def _conflict_label(key: str, locale: str) -> str:
    labels = {
        'en': ('Medicines and supplements', 'Allergies and reactions'),
        'zh-CN': ('用药与补充剂', '过敏与药物反应'),
        'zh-TW': ('用藥與補充劑', '過敏與藥物反應'),
        'ja': ('薬とサプリメント', 'アレルギーと薬の反応'),
        'ko': ('약물 및 보충제', '알레르기 및 약물 반응'),
    }
    return labels.get(locale, labels['en'])[int(key == 'allergies' or key.startswith('allergy.'))]


def _important_conflicts(session: dict) -> dict[tuple[str, str], dict]:
    result = {}
    for owner, slots in [('session', session['shared_slots'])] + [(c['id'], c['slots']) for c in session['concerns']]:
        for key, slot in slots.items():
            if slot.get('conflict') and not slot.get('exclude_from_handoff') and (key in {'allergies', 'current_medications'} or key.startswith(('medication.', 'allergy.'))):
                result[(owner, key)] = slot
    return result


def answer_followup_batch(session: dict, batch_id: str, answers: list[dict], *, extraction: ExtractionProvider | None = None) -> dict:
    normalized = _validate_batch_answers(session, batch_id, answers)
    batch = session['followup_batch']
    questions = {q['id']: q for q in batch['questions']}
    rows = [{**answer, 'concern_id': questions[answer['question_id']]['concern_id'], 'key': questions[answer['question_id']]['key']} for answer in normalized]
    # Gate every supplied value before any direct answer is applied; labels and
    # suggestions never become patient facts merely by being displayed.
    for row in rows:
        value = row['value'] or ''
        if engine.check_safety(value).triggered or engine._WITHDRAW.search(value):
            msg = engine._message(session, 'patient', value)
            batch.update(status='dismissed', draft_answers=deepcopy(normalized), invalidated_reason='safety_interruption' if engine.check_safety(value).triggered else 'consent_withdrawn')
            if not engine._interrupt(session, msg):
                session.update(consent=False, status='withdrawn', summary=None, current_question=None)
                session['plan'].update(next_target=None, stop_reason='CONSENT_WITHDRAWN')
            return session
    conflicts_before = set(_important_conflicts(session))
    text = '\n\n'.join(f"Follow-up answer (owner={row['concern_id']}, field={row['key']}, status={row['status']}):\n{row['value'] or ('I am not sure.' if row['status'] == 'UNCERTAIN' else 'Prefer not to answer.')}" for row in rows)
    msg = engine._message(session, 'patient', text)
    for row in rows:
        slot = engine._owner_slots(session, row['concern_id'])[row['key']]
        value = row['value'] if row['status'] != 'SKIPPED' else None
        evidence = engine._provenance(msg, row['value'] or '', 'followup_batch')
        evidence.update(batch_id=batch_id, question_id=row['question_id'], concern_id=row['concern_id'], key=row['key'])
        engine._update_slot(slot, value, row['status'], evidence, correction=batch['round'] == 2)
        concern = engine._concern(session, row['concern_id'])
        if concern:
            concern['preparation_status'] = 'in progress'
            if row['key'] == 'sensitive_permission':
                granted = row['status'] == 'FILLED' and bool(engine._YES.match(value or ''))
                concern['signals']['sensitive_permission'] = {'present': granted, 'evidence': evidence}
                if not granted and row['status'] == 'FILLED':
                    slot['status'] = 'SKIPPED' if engine._NO.match(value or '') else 'UNCERTAIN'
    batch.update(status='answered', answered_at=engine._now(), draft_answers=[])
    session['current_question'] = None
    session['plan']['next_target'] = None
    session['plan']['turns'] += 1
    state = _state(session)
    state['completed'] = True
    engine._apply_conditions(session)
    engine._metrics(session)
    extracted = _batch_extraction(session, rows, msg, extraction or get_provider())
    # The only automatic exception is a NEW, explicit contradiction in supplied
    # medicines/allergies. Missing ordinary fields never justify another round.
    new_conflicts = {pair: slot for pair, slot in _important_conflicts(session).items() if pair not in conflicts_before}
    if extracted and batch['round'] == 1 and state['rounds_created'] < 2 and new_conflicts:
        reason, template = _CONFLICT_COPY.get(session.get('locale', 'en'), _CONFLICT_COPY['en'])
        questions = [{'target': {'target_id': _target_id(owner, key), 'concern_id': owner, 'key': key,
                                 'question': template.format(label=_conflict_label(key, session.get('locale', 'en'))),
                                 'label': _conflict_label(key, session.get('locale', 'en'))}, 'rationale': reason, 'options': []}
                     for (owner, key), slot in list(new_conflicts.items())[:5]]
        return _publish_batch(session, questions, reason, reason=reason)
    message = 'Your follow-up answers are saved. You can review your preparation notes now.' if extracted else 'Your answers are saved directly. AI organization is unavailable; you can still review your notes.'
    return _finish_followup(session, message, 'ready' if extracted else 'unavailable')


def _synthesize(session: dict, intelligence: IntelligenceProvider) -> dict:
    summary = session.get('summary')
    if not summary or session.get('status') != 'review':
        return session
    session['stage'] = 'review'
    summary['locale'] = session.get('locale', 'en')
    summary['symptom_history'] = oldcarts.coverage_for_session(session)
    if summary.get('needs_reconciliation') or session.get('unreconciled_corrections'):
        summary['symptom_history'] = []
        message = followup_copy('correction_pending', session.get('locale', 'en'))
        summary['synthesis'] = unavailable_synthesis(session, message, include_sources=False)
        _assistant(session, 'unavailable', message)
        return session
    sources, concerns = current_sources(session), current_concerns(session)
    try:
        result = _run(session, 'synthesis', lambda: validate_synthesis(intelligence.synthesize(model=session['model'], sources=sources, concerns=concerns, locale=session.get('locale', 'en')), sources, concerns, locale=session.get('locale', 'en')))
        summary['synthesis'] = {'status': 'live', 'model': session['model'], 'locale': session.get('locale', 'en'), 'generated_at': engine._now(),
                                **result, 'sources': sources,
                                'message': followup_copy('check_translation', session.get('locale', 'en'))}
        _assistant(session, 'live', 'Your AI preparation summary is ready. Check the wording, translations and source details before approving.')
    except IntelligenceUnavailable as exc:
        summary['synthesis'] = unavailable_synthesis(session, str(exc))
        _assistant(session, 'unavailable', str(exc))
    return session


def process_message(session: dict, text: str, action: str = 'answer', *, intelligence: IntelligenceProvider | None = None,
                    extraction: ExtractionProvider | None = None) -> dict:
    _guard(session)
    batch = session.get('followup_batch') or {}
    if batch.get('status') == 'pending':
        if engine.check_safety(text).triggered or engine._WITHDRAW.search(text):
            msg = engine._message(session, 'patient', text)
            batch.update(status='dismissed', invalidated_reason='safety_interruption' if engine.check_safety(text).triggered else 'consent_withdrawn')
            if not engine._interrupt(session, msg):
                session.update(consent=False, status='withdrawn', summary=None, current_question=None)
                session['plan'].update(next_target=None, stop_reason='CONSENT_WITHDRAWN')
            return session
        if engine._FINISH.match(text.strip()):
            return build_review(session, intelligence=intelligence, extraction=extraction)
        raise ValueError('Answer the follow-up questions together, or continue to review.')
    if _state(session)['rounds_created'] or _state(session)['completed']:
        # A legacy messages client cannot obtain another round by adding text.
        session['current_question'] = None
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
    batch = session.get('followup_batch') or {}
    if batch.get('status') == 'pending':
        batch['status'] = 'dismissed'
        batch['invalidated_reason'] = 'continued_to_review'
        _state(session)['completed'] = True
    _invalidate_baseline_derivatives(session)
    before_count = len(session.get('messages', []))
    engine.build_review(session, correction, provider=_TimedExtractor(session, extraction or get_provider()))
    if session.get('status') in {'interrupted', 'withdrawn'}:
        return session
    if correction:
        session['messages'][before_count:] = [m for m in session['messages'][before_count:] if m['role'] != 'assistant']
    return _synthesize(session, intelligence or get_intelligence())
