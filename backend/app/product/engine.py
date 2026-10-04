"""Evidence-bound, multi-concern preparation engine.

The model proposes extraction. Code owns applicability, consent, interruptions,
question selection, provenance, stopping and the summary. These preparation
workflows do not determine diagnosis, urgency, or medical completeness.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
import re
import uuid

from app.core.safety import check_safety
from .provider import ExtractionProvider, ProviderUnavailable, get_provider
from .workflows import (WORKFLOWS, SHARED_QUESTIONS, CORE_QUESTIONS, SIGNALS,
                        CONDITIONS, SYMPTOM_FIELDS, get_workflow, question_definitions)

POLICY_VERSION = 'patient-agenda-missing-only-1.0'
_UNKNOWN = re.compile(r"^(?:i (?:do not|don't|don’t) know|unknown|not sure|i(?:'m| am) not sure|i (?:cannot|can't|can’t) remember)[.! ]*$", re.I)
_SKIP = re.compile(r"^(?:(?:i )?(?:would )?(?:prefer|rather) not (?:to )?(?:answer|say|include (?:that|this))|skip(?: (?:this|that)(?: question)?)?|no comment)[.! ]*$", re.I)
_FINISH = re.compile(r'^(?:finish(?: and review)?|review(?: my (?:notes|summary))?|done|stop asking questions)[.! ]*$', re.I)
_WITHDRAW = re.compile(r'\b(?:i withdraw (?:my )?consent|i revoke (?:my )?consent|stop processing my (?:data|information)|i no longer consent)\b', re.I)
_REMOVAL = re.compile(r'\b(?:remove|delete|omit|leave out|do not include|don.t include|stop sharing|no longer (?:include|share))\b', re.I)
_CORRECTION = re.compile(r'\b(?:actually|correction|i meant|correct (?:that|this)|change (?:that|this)|remove|delete|do not include|don.t include)\b', re.I)
_NO = re.compile(r'^(?:no|no thanks|no thank you|not now|prefer not|i (?:do not|don.t) want to)[.! ]*$', re.I)
_YES = re.compile(r'^(?:yes|yes please|sure|okay|ok|i agree|i consent)[.! ]*$', re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex


def _slot(key: str, *, question: str = '', condition: str | None = None) -> dict:
    return {'label': key.replace('.', ' · ').replace('_', ' ').capitalize(),
            'value': None, 'status': 'MISSING', 'question': question,
            'condition': condition, 'evidence': None, 'history': []}


def _message(session: dict, role: str, text: str) -> dict:
    msg = {'id': _id(), 'role': role, 'text': text, 'created_at': _now()}
    session['messages'].append(msg)
    session['updated_at'] = msg['created_at']
    return msg


def _concern(session: dict, concern_id: str) -> dict | None:
    return next((c for c in session['concerns'] if c['id'] == concern_id), None)


def _owner_slots(session: dict, concern_id: str) -> dict | None:
    if concern_id == 'session':
        return session['shared_slots']
    concern = _concern(session, concern_id)
    return concern['slots'] if concern else None


def _add_concern(session: dict, workflow_id: str, title: str | None = None, evidence: dict | None = None) -> dict:
    workflow = get_workflow(workflow_id)
    c = {'id': _id(), 'workflow_id': workflow_id,
         'title': title or (workflow['title'] if workflow else 'Additional concern'),
         'slots': {}, 'signals': {}, 'entry_evidence': evidence,
         'preparation_status': 'not explored'}
    for q in question_definitions(workflow_id):
        key = q['key']
        if key in SHARED_QUESTIONS or key == 'summary_review':
            continue
        c['slots'][key] = _slot(key, question=q['question'], condition=q.get('condition', CONDITIONS.get(key)))
    # Topic selection permits the matching preparation module, not a diagnosis.
    symptom_topic = workflow_id in {f'WF-{n:02}' for n in range(1, 21)} | {'WF-22'}
    c['signals']['current_symptom'] = {'present': symptom_topic, 'evidence': evidence, 'basis': 'selected_topic'}
    if workflow_id in {'WF-05', 'WF-06', 'WF-14', 'WF-17'}:
        c['signals']['episodes'] = {'present': True, 'evidence': evidence, 'basis': 'selected_recurring_topic'}
    session['concerns'].append(c)
    return c


def new_intake(patient: dict, model: str, workflow_ids: list[str], title: str | None = None) -> dict:
    unknown = [w for w in workflow_ids if not get_workflow(w)]
    if unknown:
        raise ValueError('Choose a valid preparation topic.')
    max_turns = max(10, min(240, int(os.getenv('INTAKE_MAX_TURNS', '100'))))
    session = {
        'id': _id(), 'title': title or 'Appointment preparation',
        'patient_id': patient['id'], 'patient_email': patient.get('email', ''),
        'patient_name': patient.get('name', ''), 'created_at': _now(), 'updated_at': _now(),
        'status': 'active', 'model': model, 'consent': True, 'concerns': [],
        'shared_slots': {k: _slot(k, question=q) for k, q in SHARED_QUESTIONS.items()},
        'messages': [], 'plan': {'workflow_ids': [], 'rationale': '', 'next_target': None,
                               'coverage': 0, 'resolution': 0, 'turns': 0, 'max_turns': max_turns,
                               'policy_version': POLICY_VERSION, 'stop_reason': None},
        'current_question': None, 'summary': None, 'attachments': [], 'items': [], 'audit': [],
        'priority_order': [], 'ai_status': {'mode': 'unavailable', 'message': 'Adaptive extraction will connect when you send your first answer.'},
    }
    for workflow_id in dict.fromkeys(workflow_ids):
        if workflow_id != 'WF-30':
            _add_concern(session, workflow_id, evidence={'source': 'patient_selection', 'workflow_id': workflow_id})
    session['agenda_mode'] = 'WF-30' in workflow_ids or len(session['concerns']) > 1
    _apply_conditions(session)
    _select_question(session)
    _message(session, 'assistant', 'Let’s prepare notes for your planned appointment. You control what you share, and you can skip a question or finish at any time. This tool does not diagnose or assess whether it is safe to wait.\n\n' + session['current_question']['question'])
    return session


def _signal(c: dict, name: str) -> bool:
    return c.get('signals', {}).get(name, {}).get('present') is True


def _apply_conditions(session: dict) -> list[dict]:
    changes = []
    multi = session.get('agenda_mode') or len(session['concerns']) > 1
    for key in ('agenda_items', 'priority_concern', 'preparation_focus'):
        slot = session['shared_slots'][key]
        _set_applicable(slot, bool(multi), changes, 'session', key)
    for c in session['concerns']:
        wf = c['workflow_id']
        sensitive = wf == 'WF-19'
        permission = c['slots']['sensitive_permission']
        denied = permission['status'] == 'SKIPPED' or (permission['status'] == 'FILLED' and not _signal(c, 'sensitive_permission'))
        if sensitive and not _signal(c, 'sensitive_permission'):
            session['shared_slots']['main_concern']['exclude_from_handoff'] = True
            c['slots']['concern_description']['exclude_from_handoff'] = True
            c['title'] = get_workflow(wf)['title']
        for key, slot in c['slots'].items():
            applicable = True
            condition = slot.get('condition')
            if condition:
                applicable = _signal(c, condition)
            if key in SYMPTOM_FIELDS:
                applicable = _signal(c, 'current_symptom')
            if key.startswith('previous_consultation.') and key != 'previous_consultation.exists':
                applicable = _signal(c, 'previous_consultation')
                if wf == 'WF-24' and key == 'previous_consultation.date':
                    applicable = True
            if key == 'previous_actions':
                applicable = _signal(c, 'current_symptom') or wf in {'WF-21', 'WF-22', 'WF-23', 'WF-26', 'WF-27'}
            if key == 'previous_tests':
                applicable = _signal(c, 'previous_consultation') or _signal(c, 'previous_tests') or wf in {'WF-25', 'WF-29'}
            if wf == 'WF-26' and key in {'functional_impact', 'sleep_impact'}:
                applicable = _signal(c, 'breathing_concern')
            if key.startswith(('bp_readings.', 'glucose_readings.')) and any(i['kind'] == 'reading' and i['concern_id'] == c['id'] for i in session['items']):
                applicable = False
            if key.startswith('previous_tests.') and any(i['kind'] == 'test' and i['concern_id'] == c['id'] for i in session['items']):
                applicable = False
            if key == 'sensitive_permission':
                applicable = sensitive or _signal(c, 'sensitive_connection')
            elif key == 'optional_personal_detail':
                applicable = _signal(c, 'sensitive_connection') and _signal(c, 'sensitive_permission')
            elif sensitive and (key != 'concern_description' or denied):
                applicable = applicable and _signal(c, 'sensitive_permission')
                if denied and slot['status'] != 'SKIPPED':
                    _update_slot(slot, None, 'SKIPPED', permission.get('evidence'), correction=True)
            _set_applicable(slot, applicable, changes, c['id'], key)
        # Onset and overall duration share supplied time evidence, never fabricate dates.
        onset, duration = c['slots'].get('symptom_onset'), c['slots'].get('symptom_duration')
        if onset and duration:
            for known, other, known_key in ((onset, duration, 'symptom_onset'), (duration, onset, 'symptom_duration')):
                if known['status'] in {'FILLED', 'UNCERTAIN', 'SKIPPED'} and (other['status'] == 'MISSING' or other.get('reused_from') == known_key):
                    other.update(value=known['value'], status=known['status'], evidence=deepcopy(known.get('evidence')), reused_from=known_key)
    return changes


def _set_applicable(slot: dict, applicable: bool, changes: list, owner: str, key: str) -> None:
    before = slot['status']
    if applicable and before == 'NOT_APPLICABLE':
        slot['status'] = 'MISSING'
    elif not applicable and before == 'MISSING':
        slot['status'] = 'NOT_APPLICABLE'
    # Never erase supplied evidence or a refusal when a condition changes.
    if before != slot['status']:
        changes.append({'concern_id': owner, 'key': key, 'from': before, 'to': slot['status']})


def _metrics(session: dict) -> None:
    slots = list(session['shared_slots'].values()) + [s for c in session['concerns'] for s in c['slots'].values()]
    applicable = [s for s in slots if s['status'] != 'NOT_APPLICABLE']
    n = len(applicable)
    session['plan'].update(
        coverage=round(sum(s['status'] == 'FILLED' for s in applicable) / n, 4) if n else 0,
        resolution=round(sum(s['status'] in {'FILLED', 'UNCERTAIN', 'SKIPPED'} for s in applicable) / n, 4) if n else 0,
        applicable_fields=n, supplied_fields=sum(s['status'] == 'FILLED' for s in applicable),
        workflow_ids=list(dict.fromkeys(c['workflow_id'] for c in session['concerns'])),
    )
    if session.get('agenda_mode') and 'WF-30' not in session['plan']['workflow_ids']:
        session['plan']['workflow_ids'].append('WF-30')


def _eligible(session: dict) -> list[dict]:
    result = []
    def add(owner: str, key: str, slot: dict) -> None:
        if slot['status'] == 'MISSING':
            result.append({'key': key, 'question': slot['question'], **({'concern_id': owner} if owner != 'session' else {})})
    shared = session['shared_slots']
    early = ['main_concern', 'topic_clarification', 'priority_concern', 'appointment_goal', 'current_medications', 'allergies']
    for key in early:
        if key in shared:
            add('session', key, shared[key])
    order = session.get('priority_order', [])
    concerns = sorted(session['concerns'], key=lambda c: order.index(c['id']) if c['id'] in order else len(order) + session['concerns'].index(c))
    for c in concerns:
        keys = list(c['slots'])
        # A targeted topic-permission gate precedes optional intimate detail.
        priority = ['sensitive_permission', 'concern_description', 'symptom_onset', 'functional_impact']
        for key in dict.fromkeys(priority + keys):
            slot = c['slots'][key]
            add(c['id'], key, slot)
    for key, slot in shared.items():
        if key not in early:
            add('session', key, slot)
    return result


def _select_question(session: dict) -> list[dict]:
    _metrics(session)
    eligible = _eligible(session)
    question = deepcopy(eligible[0]) if eligible else None
    session['current_question'] = question
    session['plan']['next_target'] = question
    session['plan']['rationale'] = (
        'Patient-selected agenda order; one applicable missing field at a time. Shared medicines and allergies are asked once. Unknown and skipped fields are not repeated.'
        if question else 'No unanswered applicable preparation fields remain. The patient can review the recorded account.'
    )
    return eligible


def _update_slot(slot: dict, value: str | None, status: str, evidence: dict, *, correction: bool = False) -> None:
    old = {k: deepcopy(slot.get(k)) for k in ('value', 'status', 'evidence')}
    if old['status'] in {'FILLED', 'UNCERTAIN', 'SKIPPED'} and old['value'] != value:
        slot.setdefault('history', []).append({**old, 'superseded_at': _now(), 'reason': 'patient_correction' if correction else 'additional_statement'})
        if old['status'] == 'FILLED' and status == 'FILLED' and not correction:
            slot.update(value=f"Earlier: {old['value']} | Later: {value}", status='UNCERTAIN', evidence=evidence,
                        conflict=True, alternatives=[old, {'value': value, 'status': status, 'evidence': evidence}])
            return
    slot.update(value=value, status=status, evidence=evidence)
    if correction:
        slot.pop('conflict', None)
        slot.pop('alternatives', None)
        slot.pop('reused_from', None)


def _valid_span(text: str, evidence: object, value: object | None = None) -> bool:
    return isinstance(evidence, str) and bool(evidence.strip()) and evidence in text and (value is None or (isinstance(value, str) and bool(value.strip()) and value in evidence))


def _provenance(msg: dict, span: str, source: str = 'patient_text') -> dict:
    return {'message_id': msg['id'], 'span': span, 'source': source, 'recorded_at': msg['created_at']}


def _accept_extraction(session: dict, data: dict, msg: dict, correction: bool) -> dict:
    accepted, rejected = [], []
    superseded = []
    aliases = {}
    text = msg['text']
    for candidate in data.get('new_concerns', [])[:60]:
        if not isinstance(candidate, dict):
            rejected.append({'type': 'concern', 'reason': 'invalid_shape'}); continue
        workflow_id = candidate.get('workflow_id')
        if (not get_workflow(workflow_id) and workflow_id != 'GENERAL') or workflow_id == 'WF-30' or not _valid_span(text, candidate.get('evidence'), candidate.get('title')):
            rejected.append({'type': 'concern', 'reason': 'unregistered_or_unsupported_route'}); continue
        ref = candidate.get('ref')
        if not isinstance(ref, str) or ref in aliases or _concern(session, ref) or ref == 'session':
            rejected.append({'type': 'concern', 'reason': 'invalid_reference'}); continue
        c = _add_concern(session, workflow_id, candidate['title'], _provenance(msg, candidate['evidence']))
        aliases[ref] = c['id']
        _update_slot(c['slots']['concern_description'], candidate['evidence'], 'FILLED', _provenance(msg, candidate['evidence']))
        c['preparation_status'] = 'in progress'
        accepted.append({'type': 'concern', 'concern_id': c['id'], 'workflow_id': workflow_id})
    if len(session['concerns']) > 1:
        session['agenda_mode'] = True
    if data.get('needs_clarification') and not aliases and not session.get('_route_clarification_asked'):
        session['shared_slots']['topic_clarification'] = _slot('topic_clarification', question='Which concern would you like to prepare first? Please describe it in your own words, or choose a topic.')
        session['_route_clarification_asked'] = True
    elif aliases and 'topic_clarification' in session['shared_slots']:
        _update_slot(session['shared_slots']['topic_clarification'], text, 'FILLED', _provenance(msg, text))
    for signal in data.get('signals', [])[:400]:
        if not isinstance(signal, dict):
            continue
        cid = aliases.get(signal.get('concern_id'), signal.get('concern_id'))
        c = _concern(session, cid)
        if c is None or signal.get('key') not in SIGNALS or not isinstance(signal.get('present'), bool) or not _valid_span(text, signal.get('evidence')):
            rejected.append({'type': 'signal', 'reason': 'unsupported_owner_label_or_evidence'}); continue
        # A declined permission cannot be reopened by inferred context.
        if signal['key'] == 'sensitive_permission' and signal['present']:
            if c['slots']['sensitive_permission']['status'] == 'SKIPPED' and not correction:
                rejected.append({'type': 'signal', 'reason': 'permission_previously_declined'}); continue
        c['signals'][signal['key']] = {'present': signal['present'], 'evidence': _provenance(msg, signal['evidence'])}
        if signal['key'] == 'sensitive_permission':
            _update_slot(c['slots']['sensitive_permission'], signal['evidence'], 'FILLED' if signal['present'] else 'SKIPPED', _provenance(msg, signal['evidence']), correction=correction)
        accepted.append({'type': 'signal', 'concern_id': cid, 'key': signal['key'], 'present': signal['present']})
    activations = _apply_conditions(session)
    for fact in data.get('facts', [])[:600]:
        if not isinstance(fact, dict):
            continue
        cid = aliases.get(fact.get('concern_id'), fact.get('concern_id'))
        key = fact.get('key')
        slots = _owner_slots(session, cid)
        is_removal = fact.get('operation') == 'remove'
        if slots is None or key not in slots or not _valid_span(text, fact.get('evidence'), None if is_removal else fact.get('value')):
            rejected.append({'type': 'fact', 'key': key, 'reason': 'unsupported_owner_field_or_evidence'}); continue
        if fact.get('certainty') not in {'stated', 'unknown', 'declined'} or fact.get('operation', 'set') not in {'set', 'remove'}:
            rejected.append({'type': 'fact', 'key': key, 'reason': 'invalid_state'}); continue
        c = _concern(session, cid)
        slot = slots[key]
        if c and c['workflow_id'] == 'WF-19' and key not in {'concern_description', 'sensitive_permission'} and not _signal(c, 'sensitive_permission'):
            rejected.append({'type': 'fact', 'key': key, 'reason': 'sensitive_permission_required'}); continue
        if slot['status'] == 'SKIPPED' and not correction:
            rejected.append({'type': 'fact', 'key': key, 'reason': 'previously_declined'}); continue
        if correction and slot.get('value') and (fact.get('operation') == 'remove' or slot['value'] != fact['value']):
            superseded.append({'owner': cid, 'key': key, 'value': slot['value'], 'removal': fact.get('operation') == 'remove'})
        if fact.get('operation') == 'remove':
            if not correction:
                rejected.append({'type': 'fact', 'key': key, 'reason': 'removal_requires_patient_correction'}); continue
            _update_slot(slot, None, 'SKIPPED', _provenance(msg, fact['evidence']), correction=True)
            slot['exclude_from_handoff'] = True
            if key.startswith(('medication.', 'test.', 'reading.')):
                slot['label'] = 'Removed record detail'
                slot['question'] = ''
        else:
            state = {'stated': 'FILLED', 'unknown': 'UNCERTAIN', 'declined': 'SKIPPED'}[fact['certainty']]
            _update_slot(slot, fact['value'], state, _provenance(msg, fact['evidence']), correction=correction)
        if c:
            c['preparation_status'] = 'in progress'
        accepted.append({'type': 'fact', 'concern_id': cid, 'key': key, 'operation': fact.get('operation', 'set')})
    for removal in data.get('remove_concerns', [])[:60]:
        if not isinstance(removal, dict): continue
        old = _concern(session, removal.get('concern_id'))
        if not correction or not old or not _valid_span(text, removal.get('evidence')):
            rejected.append({'type': 'concern_removal', 'reason': 'unsupported_removal'}); continue
        session.setdefault('_removed_concerns', []).append({'concern': deepcopy(old), 'evidence': _provenance(msg, removal['evidence'])})
        session['concerns'].remove(old)
        session['items'] = [item for item in session['items'] if item['concern_id'] != old['id']]
        accepted.append({'type': 'concern_removal', 'concern_id': old['id'], 'operation': 'remove'})
    _accept_items(session, data.get('items', []), aliases, msg, correction, accepted, rejected)
    for removal in data.get('remove_items', [])[:100]:
        if not isinstance(removal, dict): continue
        old = next((item for item in session['items'] if item['id'] == removal.get('item_id')), None)
        if not correction or not old or not _valid_span(text, removal.get('evidence')):
            rejected.append({'type': 'item_removal', 'reason': 'unsupported_removal'}); continue
        owner_slots = _owner_slots(session, old['concern_id'])
        removed_slots = {key: deepcopy(owner_slots[key]) for key in old['fields'].values() if key in owner_slots}
        session.setdefault('_removed_items', []).append({'item': deepcopy(old), 'slots': removed_slots, 'evidence': _provenance(msg, removal['evidence'])})
        for key in old['fields'].values():
            owner_slots.pop(key, None)
        session['items'].remove(old)
        superseded.append({'owner': old['concern_id'], 'key': '', 'value': old['name'], 'removal': True})
        accepted.append({'type': 'item_removal', 'item_id': old['id'], 'operation': 'remove'})
    if correction:
        _redact_superseded(session, superseded, msg)
    priority = []
    for entry in data.get('priority_order', [])[:60]:
        if not isinstance(entry, dict): continue
        cid = aliases.get(entry.get('concern_id'), entry.get('concern_id'))
        if _concern(session, cid) and _valid_span(text, entry.get('evidence')) and cid not in priority:
            priority.append(cid)
    if priority:
        session['priority_order'] = priority + [c['id'] for c in session['concerns'] if c['id'] not in priority]
        chosen = next(entry['evidence'] for entry in data['priority_order'] if aliases.get(entry.get('concern_id'), entry.get('concern_id')) == priority[0])
        for key in ('priority_concern', 'preparation_focus'):
            _update_slot(session['shared_slots'][key], chosen, 'FILLED', _provenance(msg, chosen), correction=correction)
    if session['concerns'] and session['shared_slots']['agenda_items']['status'] == 'MISSING':
        # Derive agenda labels from distinct patient-selected/extracted concerns.
        session['shared_slots']['agenda_items'].update(status='FILLED', value='; '.join(c['title'] for c in session['concerns']), evidence={'source': 'concern_entries', 'concern_ids': [c['id'] for c in session['concerns']]})
    return {'accepted': accepted, 'rejected': rejected, 'activations': activations}



def _redact_superseded(session: dict, superseded: list[dict], msg: dict) -> None:
    """Never leak an old fact through another broad narrative after a correction.

    Current structured values supersede aggregate prose. Original messages and
    provenance remain private patient history, never the approved handoff.
    """
    session['_has_corrections'] = True
    for item in session['items']:
        slots = _owner_slots(session, item['concern_id'])
        name_key = item['fields'].get('name')
        if name_key and slots.get(name_key, {}).get('exclude_from_handoff'):
            item.setdefault('_original_name', item['name'])
            item['name'] = {'medication': 'Unnamed medicine', 'test': 'Unnamed test', 'reading': 'Unnamed reading'}[item['kind']]
            for field, key in item['fields'].items():
                if key in slots:
                    slots[key]['label'] = f"{item['name']} · {field.replace('_', ' ')}"
                    slots[key]['question'] = '' if slots[key].get('exclude_from_handoff') else slots[key]['question'].replace(item['_original_name'], item['name'])
    narrative_keys = {'main_concern', 'agenda_items', 'priority_concern', 'preparation_focus', 'concern_description'}
    changed_owners = {entry['owner'] for entry in superseded}
    for owner, slots in [('session', session['shared_slots'])] + [(c['id'], c['slots']) for c in session['concerns']]:
        for key, slot in slots.items():
            if key in narrative_keys:
                slot['exclude_from_handoff'] = True
                continue
            value = slot.get('value')
            if not isinstance(value, str): continue
            for prior in superseded:
                # New corrected fields are already handled; other matching prose
                # is withheld rather than rewritten by an ungrounded heuristic.
                if owner == prior['owner'] and key == prior['key']: continue
                if prior['value'].casefold() in value.casefold():
                    _update_slot(slot, None, 'SKIPPED', _provenance(msg, msg['text']), correction=True)
                    slot['exclude_from_handoff'] = True
                    break
    for c in session['concerns']:
        if c['id'] in changed_owners or 'session' in changed_owners:
            w = get_workflow(c['workflow_id'])
            c['title'] = w['title'] if w else 'Additional appointment concern'


def _accept_items(session: dict, items: list, aliases: dict, msg: dict, correction: bool, accepted: list, rejected: list) -> None:
    fields_by_kind = {
        'medication': ['name', 'dose', 'frequency'],
        'test': ['name', 'date', 'ordering_clinician', 'reason', 'source'],
        'reading': ['value', 'source', 'unit', 'date'],
    }
    questions = {
        'name': 'What is the name of {name}?', 'dose': 'What dose do you currently take of {name}?',
        'frequency': 'How often do you currently take {name}?', 'actual_use': 'How are you currently taking {name}?',
        'experience': 'What would you like the clinician to know about your experience with {name}?',
        'supply': 'How much of {name} do you currently have?', 'date': 'When was {name} recorded or completed?',
        'source': 'What is the source of {name}?', 'unit': 'What unit is shown for {name}?',
        'value': 'What value is shown in the existing record for {name}?',
        'reason': 'What reason were you given for {name}?', 'ordering_clinician': 'Who arranged {name}?',
    }
    for candidate in items[:100]:
        if not isinstance(candidate, dict): continue
        kind = candidate.get('kind')
        cid = aliases.get(candidate.get('concern_id'), candidate.get('concern_id'))
        if kind == 'medication': cid = 'session'
        slots = _owner_slots(session, cid)
        if kind not in fields_by_kind or slots is None or not _valid_span(msg['text'], candidate.get('evidence'), candidate.get('name')):
            rejected.append({'type': 'item', 'reason': 'invalid_item_or_provenance'}); continue
        existing_id = candidate.get('existing_item_id')
        item = next((x for x in session['items'] if x['id'] == existing_id and x['kind'] == kind and x['concern_id'] == cid), None)
        if existing_id and item is None:
            rejected.append({'type': 'item', 'reason': 'unknown_item_reference'}); continue
        if item is None:
            # Exact repeat mention is one item; similar names are never guessed to match.
            item = next((x for x in session['items'] if x['kind'] == kind and x['concern_id'] == cid and x['name'].casefold() == candidate['name'].casefold()), None)
        if item is None:
            item = {'id': _id(), 'kind': kind, 'concern_id': cid, 'name': candidate['name'], 'evidence': _provenance(msg, candidate['evidence']), 'fields': {}}
            session['items'].append(item)
            for key in fields_by_kind[kind]:
                fq = f"{kind}.{item['id']}.{key}"
                item['fields'][key] = fq
                slots[fq] = _slot(f"{candidate['name']} · {key}", question=questions[key].format(name=candidate['name']))
            if kind in {'medication', 'test'}:
                _update_slot(slots[item['fields']['name']], candidate['name'], 'FILLED', _provenance(msg, candidate['name']))
        for field in (candidate.get('fields') if isinstance(candidate.get('fields'), list) else [])[:20]:
            if not isinstance(field, dict):
                rejected.append({'type': 'item_field', 'reason': 'invalid_shape'}); continue
            key = field.get('key')
            allowed = set(fields_by_kind[kind]) | ({'actual_use', 'experience', 'supply'} if kind == 'medication' else set())
            if key not in allowed or not _valid_span(msg['text'], field.get('evidence'), field.get('value')) or field.get('certainty') not in {'stated', 'unknown', 'declined'}:
                rejected.append({'type': 'item_field', 'key': key, 'reason': 'invalid_field_or_evidence'}); continue
            if key not in item['fields']:
                fq = f"{kind}.{item['id']}.{key}"
                item['fields'][key] = fq
                slots[fq] = _slot(f"{item['name']} · {key}", question=questions[key].format(name=item['name']))
            slot = slots[item['fields'][key]]
            _update_slot(slot, field['value'], {'stated': 'FILLED', 'unknown': 'UNCERTAIN', 'declined': 'SKIPPED'}[field['certainty']], _provenance(msg, field['evidence']), correction=correction)
        accepted.append({'type': 'item', 'item_id': item['id'], 'kind': kind})


def _interrupt(session: dict, msg: dict) -> bool:
    result = check_safety(msg['text'])
    if not result.triggered:
        return False
    session['status'] = 'interrupted'
    session['current_question'] = None
    session['summary'] = None
    session['plan'].update(next_target=None, stop_reason='SCOPE_SAFETY_INTERRUPTION', rationale='The predefined interruption paused preparation. This is not a clinical assessment.')
    session['interruption'] = {'category': result.category, 'message': result.message, 'message_id': msg['id'], 'clinical_validation': 'Fixed prototype rules; clinical review pending.'}
    _message(session, 'assistant', result.message or 'Preparation is paused. This tool cannot assess urgent situations. If you are in immediate danger, call 000.')
    session['audit'].append({'message_id': msg['id'], 'event': 'safety_interruption', 'category': result.category})
    return True


def _direct_answer(session: dict, msg: dict, action: str, *, correction: bool = False) -> bool:
    target = session.get('current_question')
    if not target:
        return False
    cid, key = target.get('concern_id', 'session'), target['key']
    slots = _owner_slots(session, cid)
    if slots is None or key not in slots:
        return False
    slot = slots[key]
    state = 'UNCERTAIN' if action == 'unknown' else 'SKIPPED' if action == 'skip' else 'FILLED'
    _update_slot(slot, msg['text'] or None, state, _provenance(msg, msg['text'], 'direct_patient_response'), correction=correction)
    c = _concern(session, cid)
    if c:
        c['preparation_status'] = 'in progress'
        if key == 'sensitive_permission':
            granted = state == 'FILLED' and bool(_YES.match(msg['text']))
            c['signals']['sensitive_permission'] = {'present': granted, 'evidence': _provenance(msg, msg['text'])}
            if not granted:
                slot['status'] = 'SKIPPED' if action == 'skip' or _NO.match(msg['text']) else 'UNCERTAIN'
    return True


def process_message(session: dict, text: str, action: str = 'answer', *, provider: ExtractionProvider | None = None) -> dict:
    """Apply one patient message; provider injection enables deterministic tests."""
    if action not in {'answer', 'unknown', 'skip'}:
        raise ValueError('Choose answer, unknown, or skip.')
    if not session.get('consent'):
        raise ValueError('Consent was withdrawn. Start a new preparation if you want to continue.')
    if session['status'] in {'approved', 'interrupted'}:
        raise ValueError('This preparation cannot accept new answers in its current state.')
    text = text.strip()
    if not text and action == 'answer':
        raise ValueError('Enter an answer, choose skip, or finish and review.')
    if len(text) > 30000:
        raise ValueError('Please keep each message under 30,000 characters.')
    text = text or ("I don't know." if action == 'unknown' else 'Prefer not to answer.')
    was_review = session['status'] == 'review'
    msg = _message(session, 'patient', text)
    # Every patient text, including controls and corrections, hits the fixed gate.
    if _interrupt(session, msg):
        return session
    if _WITHDRAW.search(text):
        session.update(consent=False, status='withdrawn', summary=None, current_question=None)
        session['plan'].update(next_target=None, stop_reason='CONSENT_WITHDRAWN')
        _message(session, 'assistant', 'Your consent has been withdrawn. Preparation has stopped and no new handoff will be generated.')
        return session
    if _FINISH.match(text):
        session['plan']['stop_reason'] = 'PATIENT_FINISH'
        return _render_review(session)
    if action == 'answer' and _UNKNOWN.match(text): action = 'unknown'
    if action == 'answer' and _SKIP.match(text): action = 'skip'
    correction = was_review or bool((_CORRECTION.search(text) or _REMOVAL.search(text)))
    target_before = deepcopy(session.get('current_question'))
    session['plan']['turns'] += 1
    session['status'] = 'active'
    accepted = {'accepted': [], 'rejected': [], 'activations': []}
    if action != 'answer':
        _direct_answer(session, msg, action, correction=correction)
        accepted['accepted'].append({'type': 'patient_control', 'action': action, 'target': target_before})
    else:
        # The initial narrative itself is an explicitly supplied reason for visit.
        if target_before and target_before['key'] in {'main_concern', 'topic_clarification'}:
            _direct_answer(session, msg, action, correction=correction)
        # Permission is an explicit control and remains available if OpenAI is down.
        permission_control = target_before and target_before['key'] == 'sensitive_permission' and (_YES.match(text) or _NO.match(text))
        if permission_control:
            _direct_answer(session, msg, action, correction=correction)
        try:
            extraction = (provider or get_provider()).extract(session, text, correction=correction)
            if not isinstance(extraction, dict):
                raise ProviderUnavailable('OpenAI returned an unusable extraction. Your original message is saved.')
            accepted = _accept_extraction(session, extraction, msg, correction)
            session['ai_status'] = {'mode': 'live', 'model': session['model'], 'message': 'OpenAI extraction completed. Validated patient evidence drives the next question.'}
            # Unmapped material remains visible for review without fabricated facts.
            removal_applied = any(change.get('operation') == 'remove' or (change.get('type') == 'signal' and change.get('key') == 'sensitive_permission' and change.get('present') is False) for change in accepted['accepted'])
            removal_unresolved = bool(_REMOVAL.search(text)) and not removal_applied
            if correction and (not accepted['accepted'] or accepted['rejected'] or extraction.get('correction_complete') is not True or removal_unresolved):
                session.setdefault('unreconciled_corrections', []).append({'text': text, 'message_id': msg['id']})
            elif correction:
                session['unreconciled_corrections'] = [pending for pending in session.get('unreconciled_corrections', []) if pending['text'].strip() != text]
        except ProviderUnavailable as exc:
            session['ai_status'] = {'mode': 'unavailable', 'model': session['model'], 'message': str(exc)}
            if correction:
                session.setdefault('unreconciled_corrections', []).append({'text': text, 'message_id': msg['id']})
            elif not permission_control and target_before and target_before['key'] != 'main_concern':
                session.setdefault('unclassified_notes', []).append({'text': text, 'message_id': msg['id'], 'question': target_before['question']})
                _message(session, 'assistant', 'Your response was saved as a note. It has not been assigned to a structured field because adaptive extraction is unavailable.')
            if not session['concerns'] and target_before and target_before['key'] == 'main_concern':
                c = _add_concern(session, 'GENERAL', 'Your appointment concern', _provenance(msg, text))
                _update_slot(c['slots']['concern_description'], text, 'FILLED', _provenance(msg, text))
                c['preparation_status'] = 'in progress'
    accepted['activations'].extend(_apply_conditions(session))
    # A consented, volunteered narrative supplies main concern even during a resumed draft.
    if session['concerns'] and session['shared_slots']['main_concern']['status'] == 'MISSING':
        session['shared_slots']['main_concern'].update(status='FILLED', value=text, evidence=_provenance(msg, text))
    eligible = _select_question(session)
    session['audit'].append({'message_id': msg['id'], 'target_before': target_before,
                             **accepted, 'eligible_targets': [{'key': q['key'], 'concern_id': q.get('concern_id')} for q in eligible],
                             'locked_next_target': deepcopy(session['current_question']),
                             'template_fallback': True, 'policy_version': POLICY_VERSION})
    if was_review:
        session['plan']['stop_reason'] = 'PATIENT_FINISH'
        return _render_review(session)
    if session['plan']['turns'] >= session['plan']['max_turns']:
        session['plan']['stop_reason'] = 'TURN_LIMIT'
        return _render_review(session)
    if not eligible:
        session['plan']['stop_reason'] = 'NO_ELIGIBLE_TARGETS'
        return _render_review(session)
    question = session['current_question']
    c = _concern(session, question.get('concern_id', ''))
    intro = f"For {c['title']}: " if c and len(session['concerns']) > 1 else ''
    prefix = ''
    if session['ai_status']['mode'] == 'unavailable':
        prefix = 'Adaptive AI is unavailable. Your answer is saved, and the guided questions remain available.\n\n'
    _message(session, 'assistant', prefix + intro + question['question'])
    return session


def build_review(session: dict, correction: str | None = None, *, provider: ExtractionProvider | None = None) -> dict:
    if not session.get('consent'):
        raise ValueError('Consent was withdrawn. A new handoff cannot be generated.')
    if session['status'] == 'interrupted':
        return session
    if session['status'] == 'approved':
        raise ValueError('Withdraw sharing before changing approved preparation notes.')
    if correction is not None and correction.strip():
        # Preserve review mode through extraction, including scope interruption.
        session['status'] = 'review'
        return process_message(session, correction, provider=provider)
    session['plan']['stop_reason'] = 'PATIENT_FINISH'
    return _render_review(session)


def _render_review(session: dict) -> dict:
    if not session.get('consent') or session['status'] == 'interrupted':
        return session
    _apply_conditions(session)
    _metrics(session)
    version = max(session.get('_summary_version', 0), (session.get('summary') or {}).get('version', 0)) + 1
    session['_summary_version'] = version
    gaps, sections = [], []
    shared_entries = []
    def entries(owner: str, slots: dict) -> list[dict]:
        result = []
        for key, slot in slots.items():
            if key in {'sensitive_permission', 'summary_review'} or slot.get('reused_from') or slot.get('exclude_from_handoff'):
                continue
            status = slot['status']
            if status == 'NOT_APPLICABLE': continue
            if status == 'FILLED':
                result.append({'key': key, 'label': slot['label'], 'value': slot['value'], 'evidence': deepcopy(slot.get('evidence')), 'status': status})
            else:
                gap = {'concern_id': owner, 'key': key, 'label': slot['label'], 'status': status,
                       'description': {'MISSING': 'Not yet collected', 'UNCERTAIN': 'Unknown or uncertain', 'SKIPPED': 'Patient chose not to include'}[status]}
                if status == 'UNCERTAIN' and slot.get('value'):
                    gap['patient_words'] = slot['value']
                gaps.append(gap)
        return result
    shared_entries = entries('session', session['shared_slots'])
    sections.append({'title': 'Reason, priorities and shared background', 'entries': shared_entries})
    for c in session['concerns']:
        facts = entries(c['id'], c['slots'])
        applicable = [s for k, s in c['slots'].items() if s['status'] != 'NOT_APPLICABLE' and k != 'sensitive_permission']
        if c['preparation_status'] == 'not explored':
            status = 'not explored'
        elif any(s['status'] == 'MISSING' for s in applicable):
            status = 'partially prepared'
        else:
            status = 'prepared with gaps' if any(s['status'] != 'FILLED' for s in applicable) else 'preparation fields supplied'
        c['preparation_status'] = status
        sections.append({'title': c['title'], 'concern_id': c['id'], 'workflow_id': c['workflow_id'], 'preparation_status': status, 'entries': facts})
    lines = ['PATIENT PREPARATION NOTES', 'Patient-reported information for a planned consultation. This record does not establish a diagnosis or whether it is safe to wait.', '']
    for section in sections:
        suffix = f" — {section['preparation_status']}" if section.get('preparation_status') else ''
        lines.append(section['title'] + suffix)
        for entry in section['entries']:
            lines.append(f"• {entry['label']}: {entry['value']}")
        if not section['entries']:
            lines.append('• No details supplied for this section.')
        lines.append('')
    if session.get('_has_corrections'):
        lines.extend(['Original broad narrative has been superseded by your corrections. Only the current structured details below are intended for sharing; your original messages remain in your private conversation.', ''])
    if session.get('unclassified_notes') and not session.get('_has_corrections'):
        lines.append('Patient notes not yet structured')
        lines.extend(f"• {note['text']}" for note in session['unclassified_notes'])
        lines.append('')
    if session.get('attachments'):
        lines.append('Attachments for clinician review')
        for attachment in session['attachments']:
            lines.append(f"• {attachment.get('filename') or attachment.get('name', 'Uploaded file')} (uploaded by the patient; contents not interpreted by this tool)")
        lines.append('')
    if gaps:
        lines.append('Unknown, skipped and uncollected information')
        names = {c['id']: c['title'] for c in session['concerns']}
        for gap in gaps:
            scope = names.get(gap['concern_id'], 'Shared information')
            words = f" — {gap['patient_words']}" if gap.get('patient_words') else ''
            lines.append(f"• {scope} / {gap['label']}: {gap['description']}{words}")
    pending = session.get('unreconciled_corrections', [])
    if pending:
        lines.extend(['', 'Patient corrections awaiting reconciliation'])
        lines.extend(f"• {correction['text']}" for correction in pending)
    session['summary'] = {'version': version, 'text': '\n'.join(lines), 'sections': sections, 'gaps': gaps,
                          'needs_reconciliation': bool(pending), 'generated_at': _now(),
                          'provenance': 'Deterministically rendered from validated patient slots; no generated clinical conclusions.'}
    session['status'] = 'review'
    session['current_question'] = None
    session['plan']['next_target'] = None
    session['updated_at'] = _now()
    _message(session, 'assistant', 'Your draft is ready to review. Check the details and gaps, correct or remove anything, then approve only what you want to share.' if not pending else 'Your correction is saved, but could not be reconciled with the draft. Please resolve it before approving these notes.')
    return session
