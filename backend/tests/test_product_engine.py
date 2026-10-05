"""Patient-state invariants across all 30 workflows; no network or real data."""
from copy import deepcopy
import pytest
from app.product.engine import new_intake, process_message, build_review
from app.product.provider import ProviderUnavailable
from app.product.workflows import WORKFLOWS, question_definitions

PATIENT = {'id': 'test-patient', 'email': 'patient@example.test', 'name': 'Test Patient'}
class Stub:
    def __init__(self, **data):
        self.data = {'new_concerns': [], 'facts': [], 'signals': [], 'items': [], 'priority_order': [], 'needs_clarification': False, 'correction_complete': True, **data}
        self.calls = 0
    def extract(self, session, text, *, correction=False):
        self.calls += 1
        return deepcopy(self.data)
class Down:
    def extract(self, *args, **kwargs): raise ProviderUnavailable('OpenAI unavailable for this test.')
def fact(cid, key, value, **kwargs):
    return {'concern_id': cid, 'key': key, 'value': value, 'evidence': value, 'certainty': 'stated', 'operation': 'set', **kwargs}
def signal(cid, key, evidence, present=True):
    return {'concern_id': cid, 'key': key, 'evidence': evidence, 'present': present}
def new(ids=None): return new_intake(PATIENT, 'gpt-6-sol', ids or [])

@pytest.mark.parametrize('workflow', WORKFLOWS, ids=lambda w: w['id'])
def test_all_30_catalogue_banks_registered_and_questionable(workflow):
    assert 6 <= len(workflow['questions']) <= 7
    assert all(q['key'] and q['question'].endswith('?') for q in workflow['questions'])
    rows=question_definitions(workflow['id']); assert len({q['key'] for q in rows}) == len(rows)
    s=new([workflow['id']]); process_message(s,'I am preparing for my booked appointment.',provider=Stub())
    assert s['status']=='active' and s['current_question']
    build_review(s); assert s['summary']['version']==1 and s['status']=='review'

def test_detailed_opening_fills_future_targets_and_preserves_approximation():
    s=new(['WF-01']); cid=s['concerns'][0]['id']
    text='My left lower leg has been aching about two weeks, especially on stairs.'
    p=Stub(facts=[fact(cid,'leg.pain_site','left lower leg'),fact(cid,'leg.pain_character','aching'),fact(cid,'symptom_onset','about two weeks'),fact(cid,'leg.activity_context','stairs')])
    process_message(s,text,provider=p)
    for _ in range(4): process_message(s,'','skip',provider=p)
    assert s['concerns'][0]['slots']['symptom_onset']['value']=='about two weeks'
    assert s['current_question']['key'] not in {'leg.pain_site','leg.pain_character','symptom_onset','leg.activity_context'}
    assert p.calls==1

def test_twelve_concerns_and_timelines_are_isolated():
    s=new(); parts=[f'Concern {i} is my leg pain for {i} weeks' for i in range(1,13)]
    p=Stub(new_concerns=[{'ref':f'n{i}','workflow_id':'WF-01','title':f'Concern {i}','evidence':parts[i-1]} for i in range(1,13)],facts=[fact(f'n{i}','symptom_onset',f'{i} weeks') for i in range(1,13)])
    process_message(s,'; '.join(parts),provider=p)
    assert len(s['concerns'])==12 and len({c['id'] for c in s['concerns']})==12
    assert [c['slots']['symptom_onset']['value'] for c in s['concerns']]==[f'{i} weeks' for i in range(1,13)]
    assert all('current_medications' not in c['slots'] for c in s['concerns'])
    build_review(s); assert len([x for x in s['summary']['sections'] if x.get('concern_id')])==12

def test_patient_chosen_agenda_order_has_no_clinical_priority():
    s=new(['WF-01','WF-08']); chosen=s['concerns'][1]['id']
    process_message(s,'I want to prepare sleep first.',provider=Stub(priority_order=[{'concern_id':chosen,'evidence':'sleep first'}]))
    assert s['priority_order'][0]==chosen
    for _ in range(3): process_message(s,'','skip',provider=Stub())
    assert s['current_question']['concern_id']==chosen

@pytest.mark.parametrize('wid,key,flag',[
 ('WF-01','leg.reported_event','injury'),('WF-01','leg.pain_spread','spreading'),('WF-03','neck_shoulder.turning_detail','head_turning'),
 ('WF-05','headache.diary_details','diary'),('WF-06','dizziness.position_detail','position_change'),('WF-07','fatigue.routine_change','routine_change'),
 ('WF-08','sleep.waking_duration','night_waking'),('WF-09','cough.reported_mucus','mucus'),('WF-10','nasal.season_detail','seasonal'),
 ('WF-11','voice_change_description','voice_change'),('WF-12','hearing_context','hearing_concern'),('WF-13','eye_lens_context','contact_lenses'),
 ('WF-18','leakage_context','leakage'),('WF-20','skin_appearance','visible_skin_change'),('WF-26','asthma.action_plan','action_plan'),
 ('WF-27','medication_supply','prescription_goal'),('WF-28','previous_tests.report_passage','report_available'),('WF-29','prevention_invitation.date','invitation')])
def test_conditional_details_require_explicit_evidence(wid,key,flag):
    s=new([wid]); c=s['concerns'][0]; assert c['slots'][key]['status']=='NOT_APPLICABLE'
    process_message(s,'An explicit patient observation.',provider=Stub(signals=[signal(c['id'],flag,'explicit patient observation')]))
    assert c['slots'][key]['status']=='MISSING'

@pytest.mark.parametrize('wid',['WF-24','WF-25','WF-26','WF-27','WF-28','WF-29'])
def test_review_only_workflows_do_not_require_symptom_history(wid):
    c=new([wid])['concerns'][0]
    assert all(c['slots'][key]['status']=='NOT_APPLICABLE' for key in ('symptom_onset','symptom_course','severity','functional_impact'))

def test_unknown_skip_resolution_not_information_and_not_reasked():
    s=new(['WF-01']);process_message(s,'','unknown',provider=Stub());process_message(s,'','skip',provider=Stub())
    assert s['shared_slots']['main_concern']['status']=='UNCERTAIN' and s['shared_slots']['appointment_goal']['status']=='SKIPPED'
    assert s['plan']['resolution']>s['plan']['coverage']
    assert s['current_question']['key'] not in {'main_concern','appointment_goal'}

def test_sensitive_permission_decline_closes_module():
    s=new(['WF-19']);c=s['concerns'][0]
    process_message(s,'My periods changed.',provider=Stub(facts=[fact(c['id'],'menstrual_current_pattern','periods changed')]))
    assert c['slots']['menstrual_current_pattern']['status']=='NOT_APPLICABLE'
    for _ in range(3):process_message(s,'','skip',provider=Stub())
    assert s['current_question']['key']=='sensitive_permission'
    process_message(s,'','skip',provider=Stub())
    assert c['slots']['menstrual_current_pattern']['status']=='SKIPPED'

def test_sensitive_permission_revoke_removes_previously_shared_detail():
    s=new(['WF-19']);c=s['concerns'][0];cid=c['id']
    process_message(s,'Yes, include personal details. My cycle is 35 days.',provider=Stub(signals=[signal(cid,'sensitive_permission','Yes, include personal details')],facts=[fact(cid,'menstrual_current_pattern','35 days')]))
    assert c['slots']['menstrual_current_pattern']['status']=='FILLED'
    build_review(s);build_review(s,'Actually, do not include personal details.',provider=Stub(signals=[signal(cid,'sensitive_permission','do not include personal details',False)]))
    assert c['slots']['menstrual_current_pattern']['status']=='SKIPPED'
    assert '35 days' not in s['summary']['text']

def test_review_correction_preserves_review_history_and_monotonic_version():
    s=new(['WF-01']);cid=s['concerns'][0]['id']
    process_message(s,'My left leg hurts.',provider=Stub(facts=[fact(cid,'leg.pain_site','left leg')]))
    build_review(s);first=s['summary']['version']
    build_review(s,'Actually, I meant right leg.',provider=Stub(facts=[fact(cid,'leg.pain_site','right leg')]))
    slot=s['concerns'][0]['slots']['leg.pain_site']
    assert s['status']=='review' and s['current_question'] is None and s['summary']['version']==first+1
    assert slot['value']=='right leg' and slot['history'][0]['value']=='left leg'
    assert 'left leg' not in s['summary']['text']
    s['summary']=None;s['status']='active';build_review(s);assert s['summary']['version']==first+2

def test_correction_redacts_removed_fact_from_aggregate_narratives():
    s=new(['WF-01']);cid=s['concerns'][0]['id'];text='My leg hurts, and I smoke. I am allergic to penicillin.'
    process_message(s,text,provider=Stub(facts=[fact(cid,'concern_description',text),fact('session','allergies','allergic to penicillin')]))
    build_review(s);build_review(s,'Remove allergic to penicillin.',provider=Stub(facts=[fact('session','allergies','allergic to penicillin',operation='remove')]))
    assert 'penicillin' not in s['summary']['text']
    assert s['shared_slots']['main_concern']['exclude_from_handoff']

def test_unannounced_conflict_remains_uncertain():
    s=new(['WF-01']);cid=s['concerns'][0]['id']
    for side in ('left leg','right leg'):process_message(s,side,provider=Stub(facts=[fact(cid,'leg.pain_site',side)]))
    assert s['concerns'][0]['slots']['leg.pain_site']['status']=='UNCERTAIN'

def test_ungrounded_extraction_and_unknown_fields_are_rejected():
    s=new(['WF-01']);c=s['concerns'][0]
    process_message(s,'I have leg discomfort.',provider=Stub(facts=[fact(c['id'],'symptom_onset','four years'),fact(c['id'],'diagnosis','leg discomfort')],signals=[signal(c['id'],'injury','fall')]))
    assert c['slots']['symptom_onset']['status']=='MISSING' and c['slots']['leg.reported_event']['status']=='NOT_APPLICABLE'
    assert len(s['audit'][-1]['rejected'])==3 and 'diagnosis' not in c['slots']

def test_safety_runs_before_every_correction_and_never_becomes_review():
    s=new(['WF-28']);build_review(s);p=Stub();build_review(s,'Actually I have chest pain right now.',provider=p)
    assert p.calls==0 and s['status']=='interrupted' and s['summary'] is None
    build_review(s);assert s['status']=='interrupted'

def test_consent_withdrawal_blocks_handoff_but_sharing_withdrawal_can_resume():
    s=new(['WF-01']);p=Stub();process_message(s,'I withdraw my consent.',provider=p)
    assert p.calls==0 and s['status']=='withdrawn' and not s['consent']
    with pytest.raises(ValueError):build_review(s)
    with pytest.raises(ValueError):process_message(s,'More details',provider=p)
    s=new(['WF-01']);s['status']='withdrawn';process_message(s,'More information.',provider=p);assert s['status']=='active'

def test_patient_finish_keeps_all_unexplored_concerns_and_turn_cap_keeps_gaps():
    s=new(['WF-01','WF-08','WF-27']);process_message(s,'Finish and review',provider=Stub())
    assert s['plan']['stop_reason']=='PATIENT_FINISH' and all(c['preparation_status']=='not explored' for c in s['concerns'])
    assert all(c['title'] in s['summary']['text'] for c in s['concerns'])
    s=new(['WF-01']);s['plan']['max_turns']=1;process_message(s,'My leg hurts.',provider=Stub())
    assert s['status']=='review' and s['plan']['stop_reason']=='TURN_LIMIT' and any(g['status']=='MISSING' for g in s['summary']['gaps'])

def test_unavailable_provider_preserves_notes_without_fake_extraction():
    s=new(['WF-01']);process_message(s,'My left leg aches.',provider=Down())
    assert s['ai_status']['mode']=='unavailable' and s['shared_slots']['main_concern']['value']=='My left leg aches.'
    assert s['concerns'][0]['slots']['leg.pain_site']['status']=='MISSING'
    key=s['current_question']['key'];process_message(s,'I also have poor sleep.',provider=Down())
    assert s['shared_slots'][key]['status']=='MISSING' and s['unclassified_notes'][0]['text']=='I also have poor sleep.'

def test_pending_correction_survives_unrelated_success_until_exact_retry():
    s=new(['WF-01']);cid=s['concerns'][0]['id'];build_review(s);text='Actually remove smoking.'
    build_review(s,text,provider=Down());assert s['summary']['needs_reconciliation']
    build_review(s,'Actually onset Tuesday.',provider=Stub(facts=[fact(cid,'symptom_onset','Tuesday')]))
    assert s['summary']['needs_reconciliation']
    build_review(s,text,provider=Stub(facts=[fact('session','relevant_history','smoking',operation='remove')]))
    assert not s['summary']['needs_reconciliation']

def test_repeated_medicines_keep_independent_unknown_doses():
    s=new(['WF-27']);text='I take medicine A 5 mg daily and medicine B, dose unknown.'
    p=Stub(items=[{'kind':'medication','concern_id':'session','existing_item_id':None,'name':'medicine A','evidence':'medicine A 5 mg daily','fields':[{'key':'dose','value':'5 mg','evidence':'5 mg','certainty':'stated'}]}, {'kind':'medication','concern_id':'session','existing_item_id':None,'name':'medicine B','evidence':'medicine B, dose unknown','fields':[{'key':'dose','value':'unknown','evidence':'dose unknown','certainty':'unknown'},'invalid']}])
    process_message(s,text,provider=p);a,b=s['items'];slots=s['shared_slots']
    assert a['id']!=b['id'] and slots[a['fields']['dose']]['value']=='5 mg'
    assert slots[b['fields']['dose']]['status']=='UNCERTAIN' and slots[b['fields']['frequency']]['status']=='MISSING'

def test_reading_units_stay_unknown_and_are_not_interpreted():
    s=new(['WF-25']);cid=s['concerns'][0]['id'];text='My glucose reading was 8; I do not know the unit.'
    process_message(s,text,provider=Stub(items=[{'kind':'reading','concern_id':cid,'existing_item_id':None,'name':'glucose reading','evidence':'glucose reading was 8','fields':[{'key':'value','value':'8','evidence':'8','certainty':'stated'},{'key':'unit','value':'do not know','evidence':'do not know the unit','certainty':'unknown'}]}]))
    item=s['items'][0];slots=s['concerns'][0]['slots'];assert slots[item['fields']['unit']]['status']=='UNCERTAIN'
    assert slots[item['fields']['date']]['status']=='MISSING';build_review(s)
    assert 'mmol' not in s['summary']['text'] and 'normal range' not in s['summary']['text']

def test_suggested_questions_never_attributed_without_patient_input():
    s=new(['WF-01']);build_review(s);assert 'Could we discuss' not in s['summary']['text']
    assert s['shared_slots']['clinician_questions']['status']=='MISSING'

def test_partial_correction_acceptance_still_blocks_approval():
    s=new(['WF-01']);cid=s['concerns'][0]['id'];build_review(s)
    build_review(s,'Remove smoking and change onset to Tuesday.',provider=Stub(facts=[fact(cid,'symptom_onset','Tuesday')],correction_complete=False))
    assert s['summary']['needs_reconciliation']

def test_rejected_part_of_correction_does_not_silently_disappear():
    s=new(['WF-01']);cid=s['concerns'][0]['id'];build_review(s)
    build_review(s,'Change onset to Tuesday and remove smoking.',provider=Stub(facts=[fact(cid,'symptom_onset','Tuesday'),fact('session','invented_history','smoking',operation='remove')]))
    assert s['summary']['needs_reconciliation']

def test_ambiguous_route_gets_one_neutral_clarification():
    s=new();process_message(s,'I want to discuss a concern.',provider=Stub(needs_clarification=True))
    assert s['current_question']['key']=='topic_clarification'
    process_message(s,'I cannot say more.','skip',provider=Stub())
    assert s['current_question']['key']!='topic_clarification'

def test_sensitive_original_story_is_not_shared_without_topic_permission():
    s=new(['WF-19']);process_message(s,'My periods are 35 days apart.',provider=Stub());build_review(s)
    assert '35 days' not in s['summary']['text']

def test_removal_plus_unrelated_accepted_fact_still_requires_reconciliation():
    s=new(['WF-01']);cid=s['concerns'][0]['id'];build_review(s)
    build_review(s,'Remove smoking and change onset to Tuesday.',provider=Stub(facts=[fact(cid,'symptom_onset','Tuesday')],correction_complete=True))
    assert s['summary']['needs_reconciliation']

def test_patient_can_remove_entire_concern_without_leaking_old_narrative():
    s=new(['WF-01','WF-08']);cid=s['concerns'][0]['id'];build_review(s)
    build_review(s,'Remove leg pain from my notes.',provider=Stub(remove_concerns=[{'concern_id':cid,'evidence':'Remove leg pain'}]))
    assert len(s['concerns'])==1 and s['concerns'][0]['workflow_id']=='WF-08'
    assert 'Leg pain' not in s['summary']['text'] and not s['summary']['needs_reconciliation']

def _medicine_session():
    s=new(['WF-27'])
    opening='I take Vitamin D 1000 IU daily and medicine B 5 mg weekly.'
    process_message(s,opening,provider=Stub(facts=[fact('session','current_medications','Vitamin D 1000 IU daily and medicine B 5 mg weekly')],items=[
        {'kind':'medication','concern_id':'session','existing_item_id':None,'name':'Vitamin D','evidence':'Vitamin D 1000 IU daily','fields':[{'key':'dose','value':'1000 IU','evidence':'1000 IU','certainty':'stated'},{'key':'frequency','value':'daily','evidence':'daily','certainty':'stated'}]},
        {'kind':'medication','concern_id':'session','existing_item_id':None,'name':'medicine B','evidence':'medicine B 5 mg weekly','fields':[{'key':'dose','value':'5 mg','evidence':'5 mg','certainty':'stated'},{'key':'frequency','value':'weekly','evidence':'weekly','certainty':'stated'}]},
    ]))
    build_review(s)
    return s

def test_remove_medicine_fields_does_not_require_repeating_old_dose_or_frequency():
    from app.product.routes import clinician_public_session
    import json
    s=_medicine_session();a=s['items'][0]
    text='Please remove Vitamin D and all of its dose and frequency details from my record.'
    keys=['current_medications',*a['fields'].values()]
    build_review(s,text,provider=Stub(facts=[fact('session',key,'',evidence=text,operation='remove') for key in keys]))
    assert not s['summary']['needs_reconciliation']
    clinician=json.dumps(clinician_public_session(s))
    for removed in ['Vitamin D','1000 IU','daily']:
        assert removed not in s['summary']['text'] and removed not in clinician
    assert 'medicine B' in s['summary']['text'] and '5 mg' in s['summary']['text']

def test_remove_complete_item_withholds_broad_inventory_and_preserves_other_medicines():
    from app.product.routes import clinician_public_session
    import json
    s=_medicine_session();a=s['items'][0]
    text='Please remove Vitamin D and all of its dose and frequency details from my record.'
    build_review(s,text,provider=Stub(remove_items=[{'item_id':a['id'],'evidence':text}]))
    assert not s['summary']['needs_reconciliation']
    assert len(s['items'])==1 and s['items'][0]['name']=='medicine B'
    assert all(key not in s['shared_slots'] for key in a['fields'].values())
    clinician=json.dumps(clinician_public_session(s))
    for removed in ['Vitamin D','1000 IU','daily']:
        assert removed not in s['summary']['text'] and removed not in clinician
    assert 'medicine B' in s['summary']['text']

def test_unknown_deletion_target_or_ungrounded_request_remains_unreconciled():
    s=_medicine_session();text='Remove that medicine.'
    build_review(s,text,provider=Stub(remove_items=[{'item_id':'invented-item','evidence':text}]))
    assert s['summary']['needs_reconciliation'] and len(s['items'])==2

def test_form_followup_answer_does_not_become_the_entire_reason_for_visit():
    from app.product import forms
    s = forms.initialize(new(['WF-08']))
    forms.apply_baseline(s, [], complete=True)
    cid = s['concerns'][0]['id']
    s['current_question'] = {'concern_id': cid, 'key': 'symptom_onset', 'question': 'When did it begin?'}
    process_message(s, 'About two months ago.', provider=Stub(facts=[fact(cid, 'symptom_onset', 'About two months ago.')]))
    assert s['concerns'][0]['slots']['symptom_onset']['value'] == 'About two months ago.'
    assert s['shared_slots']['main_concern']['status'] == 'MISSING'
    assert s['shared_slots']['main_concern']['value'] is None

def _v2_form_medicine_session(*, custom_title='Work certificate', custom_description='I need paperwork for my employer.'):
    from app.product import forms
    s=forms.initialize(new(['WF-01']),[custom_title]);leg,custom=s['concerns']
    forms.apply_baseline(s,[
        {'concern_id':'session','key':'current_medications','value':'Vitamin D 1000 IU daily','status':'FILLED'},
        {'concern_id':leg['id'],'key':'concern_description','value':'我的左小腿疼了三周。','status':'FILLED'},
        {'concern_id':leg['id'],'key':'leg.pain_site','value':'left calf','status':'FILLED'},
        {'concern_id':custom['id'],'key':'concern_description','value':custom_description,'status':'FILLED'},
    ],complete=True)
    process_message(s,'Vitamin D 1000 IU daily',provider=Stub(items=[
        {'kind':'medication','concern_id':'session','existing_item_id':None,'name':'Vitamin D','evidence':'Vitamin D 1000 IU daily',
         'fields':[{'key':'dose','value':'1000 IU','evidence':'1000 IU','certainty':'stated'},{'key':'frequency','value':'daily','evidence':'daily','certainty':'stated'}]},
    ]))
    build_review(s)
    return s,leg,custom

def test_v2_shared_medicine_removal_preserves_unrelated_form_narratives_and_custom_title():
    from app.product.routes import clinician_public_session
    import json
    s,leg,custom=_v2_form_medicine_session();item=s['items'][0]
    text='Remove Vitamin D and its details.'
    build_review(s,text,provider=Stub(remove_items=[{'item_id':item['id'],'evidence':text}]))
    assert not s['summary']['needs_reconciliation']
    assert custom['title']=='Work certificate'
    assert not custom['slots']['concern_description'].get('exclude_from_handoff')
    assert not leg['slots']['concern_description'].get('exclude_from_handoff')
    assert 'I need paperwork for my employer.' in s['summary']['text']
    assert '我的左小腿疼了三周。' in s['summary']['text']
    public=json.dumps(clinician_public_session(s),ensure_ascii=False)
    assert 'Work certificate' in public and 'Vitamin D' not in public and '1000 IU' not in public

def test_v2_removed_medicine_cannot_survive_in_another_form_narrative_or_title():
    from app.product.routes import clinician_public_session
    import json
    s,leg,custom=_v2_form_medicine_session(custom_title='Vitamin D paperwork',custom_description='My paperwork includes Vitamin D.')
    item=s['items'][0];text='Remove Vitamin D and its details.'
    build_review(s,text,provider=Stub(remove_items=[{'item_id':item['id'],'evidence':text}]))
    assert custom['slots']['concern_description']['exclude_from_handoff']
    assert 'Vitamin D' not in json.dumps(clinician_public_session(s),ensure_ascii=False)
    assert '我的左小腿疼了三周。' in s['summary']['text']

def test_v2_own_scope_site_correction_withholds_bilingual_old_narrative_only_in_that_scope():
    s,leg,custom=_v2_form_medicine_session()
    text='Actually the affected site is my right calf.'
    build_review(s,text,provider=Stub(facts=[fact(leg['id'],'leg.pain_site','right calf')]))
    assert leg['slots']['concern_description']['exclude_from_handoff']
    assert '我的左小腿疼了三周。' not in s['summary']['text']
    assert 'right calf' in s['summary']['text']
    assert custom['title']=='Work certificate' and 'I need paperwork for my employer.' in s['summary']['text']

def test_v2_newly_corrected_narrative_is_current_and_can_be_shared():
    s,leg,custom=_v2_form_medicine_session()
    text='Actually my right calf has a dull ache.'
    build_review(s,text,provider=Stub(facts=[fact(leg['id'],'concern_description','my right calf has a dull ache')]))
    assert not leg['slots']['concern_description'].get('exclude_from_handoff')
    assert 'my right calf has a dull ache' in s['summary']['text']
    assert '我的左小腿疼了三周。' not in s['summary']['text']
    assert 'I need paperwork for my employer.' in s['summary']['text']

def test_v2_removal_still_redacts_a_newly_extracted_duplicate_of_removed_item():
    from app.product.routes import clinician_public_session
    import json
    s,leg,custom=_v2_form_medicine_session();item=s['items'][0]
    text='Remove Vitamin D and its details.'
    build_review(s,text,provider=Stub(remove_items=[{'item_id':item['id'],'evidence':text}],facts=[fact('session','relevant_history','Vitamin D')]))
    assert 'Vitamin D' not in json.dumps(clinician_public_session(s),ensure_ascii=False)
    assert custom['title']=='Work certificate' and 'I need paperwork for my employer.' in s['summary']['text']
