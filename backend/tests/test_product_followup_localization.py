"""Patient-language AI copy keeps evidence/IDs stable; all providers are synthetic."""
from copy import deepcopy

import pytest

from app.product import intelligence as ai, pipeline
from app.product.locales import prose_matches_locale, translate_text
from .test_product_followup_batch import prepared, answers
from .test_product_intelligence import baseline


LOCALIZED = {
    'zh-CN': ('帮助记录症状的变化。', '患者报告症状持续2周。', '帮助描述本次就诊情况。'),
    'zh-TW': ('幫助記錄症狀的變化。', '患者報告症狀持續2週。', '幫助描述本次就診情況。'),
    'ko': ('증상의 변화를 기록하는 데 도움이 됩니다.', '환자는 증상이 2주 동안 지속되었다고 보고합니다.', '이번 진료에서 경험을 설명하는 데 도움이 됩니다.'),
    'ja': ('症状の変化を記録するためです。', '患者は症状が2週間続いていると述べています。', '今回の受診で経験を説明するためです。'),
}
TARGET = {'target_id': 'target-course', 'concern_id': 'concern-test', 'key': 'symptom_course',
          'question': 'How has it changed since you first noticed it?', 'label': 'Symptom course'}


def plan(locale, *, value='Comes and goes'):
    return {'questions': [{'target_id': TARGET['target_id'], 'question': translate_text(TARGET['question'], locale),
        'display_label': {'zh-CN': '症状变化', 'zh-TW': '症狀變化', 'ko': '증상 변화', 'ja': '症状の変化'}[locale],
        'rationale': LOCALIZED[locale][0], 'options': [{'label': 'Comes and goes', 'value': value},
                                                     {'label': 'Present all the time', 'value': 'Present all the time'}]}],
        'overview': {'text': '', 'source_ids': []}, 'suggested_concern_ids': []}


@pytest.mark.parametrize('locale', LOCALIZED)
def test_translated_choices_submit_patient_language_and_empty_overview_is_localized(locale):
    result = ai.validate_plan(plan(locale), [], [], [TARGET], locale=locale)
    question = result['questions'][0]
    assert question['target']['target_id'] == TARGET['target_id']
    for key in ('question', 'display_label', 'rationale'):
        assert prose_matches_locale(question[key], locale)
    assert prose_matches_locale(result['overview'], locale)
    for option in question['options']:
        assert option['label'] == option['value'] and prose_matches_locale(option['value'], locale)
    assert [option['id'] for option in question['options']] == ['A', 'B']


@pytest.mark.parametrize('locale', LOCALIZED)
def test_localized_label_cannot_conceal_untranslated_submitted_value(locale):
    data = plan(locale, value='I notice this only when I sit by the window.')
    with pytest.raises(ai.IntelligenceUnavailable, match='selected patient language'):
        ai.validate_plan(data, [], [], [TARGET], locale=locale)


@pytest.mark.parametrize('locale', LOCALIZED)
def test_unvalidated_overview_uses_patient_language_fallback(locale):
    data = plan(locale)
    data['overview'] = {'text': 'This cannot be supported by any source.', 'source_ids': ['invented']}
    result = ai.validate_plan(data, [], [], [TARGET], locale=locale)
    assert result['overview_fallback'] and prose_matches_locale(result['overview'], locale)


@pytest.mark.parametrize('locale', LOCALIZED)
def test_synthesis_localizes_canonical_title_but_preserves_original_sources(locale):
    session = baseline()
    session['locale'] = locale
    concern = session['concerns'][0]
    concern['slots']['concern_description']['value'] = 'two weeks'
    raw_title = concern['title']
    sources, concerns = ai.current_sources(session), ai.current_concerns(session)
    source = next(s for s in sources if s['concern_id'] == concern['id'] and s['key'] == 'concern_description')
    data = {'patient_overview': [{'text': LOCALIZED[locale][1], 'source_ids': [source['id']]}],
            'clinician_brief': [], 'appointment_agenda': [], 'uncertainties': [],
            'concern_summaries': [{'concern_id': concern['id'], 'title': 'Wrong model title',
                                  'summary': LOCALIZED[locale][1], 'source_ids': [source['id']]}]}
    result = ai.validate_synthesis(data, sources, concerns, locale=locale)
    assert result['concern_summaries'][0]['title'] == translate_text(raw_title, locale)
    assert concern['title'] == raw_title and source['value'] == 'two weeks'
    assert result['patient_overview'][0]['source_ids'] == [source['id']]
    data['patient_overview'][0]['text'] = 'Patient reports symptoms for two weeks.'
    with pytest.raises(ai.IntelligenceUnavailable, match='selected patient language'):
        ai.validate_synthesis(data, sources, concerns, locale=locale)


def test_live_provider_repairs_wrong_language_once_without_expanding_targets(monkeypatch):
    calls = []
    bad = plan('zh-CN')
    bad['questions'][0]['rationale'] = 'An unregistered English reason that should have been translated.'
    outputs = [bad, plan('zh-CN')]
    def request(self, model, prompt, data, schema, name, max_output):
        calls.append({'prompt': prompt, 'data': deepcopy(data)})
        return outputs.pop(0)
    monkeypatch.setattr(ai.OpenAIIntelligence, '_request', request)
    result = ai.OpenAIIntelligence().plan(model='synthetic', sources=[], concerns=[], targets=[TARGET], locale='zh-CN')
    assert result == plan('zh-CN') and len(calls) == 2
    assert calls[0]['data'] == calls[1]['data']
    assert 'previous response failed' in calls[1]['prompt']


def test_wrong_language_after_repair_is_not_displayed(monkeypatch):
    data = plan('zh-CN')
    data['questions'][0]['rationale'] = 'An unregistered English reason.'
    calls = []
    def request(*args, **kwargs):
        calls.append(1)
        return data
    monkeypatch.setattr(ai.OpenAIIntelligence, '_request', request)
    with pytest.raises(ai.IntelligenceUnavailable, match='selected patient language'):
        ai.OpenAIIntelligence().plan(model='synthetic', sources=[], concerns=[], targets=[TARGET], locale='zh-CN')
    assert len(calls) == 2


class Translator:
    def __init__(self):
        self.calls = []

    def translate_presentation(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        labels = {
            'Symptom pattern': {'zh-CN': '症状规律', 'zh-TW': '症狀規律', 'ko': '증상 양상', 'ja': '症状の現れ方'},
            'Severity': {'zh-CN': '严重程度', 'zh-TW': '嚴重程度', 'ko': '심한 정도', 'ja': '症状の程度'},
        }
        assert all(key.endswith('.why') or text in labels for key, text in kwargs['texts'].items()), kwargs['texts']
        return {key: labels[text][kwargs['locale']] if text in labels else LOCALIZED[kwargs['locale']][2] for key, text in kwargs['texts'].items()}


@pytest.mark.parametrize('locale', LOCALIZED)
def test_switch_language_preserves_pending_question_drafts_identities_and_budget(locale):
    session, _, _ = prepared()
    pipeline.save_followup_draft(session, session['followup_batch']['id'], answers(session)[:1])
    original, slots, state = deepcopy(session['followup_batch']), deepcopy(session['concerns']), deepcopy(session['_followup'])
    session['locale'] = locale
    provider = Translator()
    pipeline.relocalize_pending_followup(session, intelligence=provider)
    current = session['followup_batch']
    assert current['id'] == original['id'] and current['round'] == original['round'] == 1
    assert current['draft_answers'] == original['draft_answers']
    assert session['concerns'] == slots and session['_followup'] == state
    assert current['locale'] == locale and len(provider.calls) == 1
    for before, after in zip(original['questions'], current['questions']):
        assert all(before[key] == after[key] for key in ('id', 'key', 'target_id', 'concern_id'))
        assert all(prose_matches_locale(after[key], locale) for key in ('question', 'display_label', 'why'))
        assert [o['id'] for o in before['options']] == [o['id'] for o in after['options']]
        assert all(prose_matches_locale(o['value'], locale) for o in after['options'])
    snapshot = deepcopy(session)
    pipeline.relocalize_pending_followup(session, intelligence=provider)
    assert session == snapshot and len(provider.calls) == 1


def test_failed_pending_translation_is_atomic():
    session, _, _ = prepared()
    session['locale'] = 'zh-CN'
    before = deepcopy(session)
    class InvalidTranslator:
        def translate_presentation(self, **kwargs):
            return {'invented-id': '这是无效的翻译。'}
    with pytest.raises(ai.IntelligenceUnavailable):
        pipeline.relocalize_pending_followup(session, intelligence=InvalidTranslator())
    assert session == before


@pytest.mark.parametrize('translated', [
    [{'id': 'one', 'text': '剂量为10 mg。'}],
    [{'id': 'one', 'text': 'Dose is 5 mg.'}],
    [{'id': 'one', 'text': '患者记录了剂量。'}],
    [],
])
def test_translation_cannot_change_measurements_language_or_omit_strings(translated):
    with pytest.raises(ai.IntelligenceUnavailable):
        ai.validate_presentation_translation({'translations': translated}, {'one': 'Dose is 5 mg.'}, 'zh-CN')


@pytest.mark.parametrize('locale', LOCALIZED)
def test_ai_failure_message_remains_in_patient_language(locale):
    message = pipeline._safe_failure_message(ai.IntelligenceUnavailable('Unknown provider failure'), locale)
    assert prose_matches_locale(message, locale)


def test_translated_non_numeric_idioms_are_not_new_measurements():
    original = {'one': 'The discomfort is constant.'}
    result = ai.validate_presentation_translation({'translations': [{'id': 'one', 'text': '不适一直存在。'}]}, original, 'zh-CN')
    assert result['one'] == '不适一直存在。'
    assert ai._numeric_tokens('500 mg，2周前，每天一次。') == {'500', '2', '1'}


def test_english_synthesis_can_keep_a_source_medicine_name_without_leaving_prose_untranslated():
    sources = [{'id': 'name-source', 'concern_id': 'session', 'key': 'medication.test.name',
                'value': '阿莫西林', 'status': 'FILLED', 'label': 'Medicine name'}]
    data = {'patient_overview': [{'text': 'Patient reports taking 阿莫西林.', 'source_ids': ['name-source']}],
            'clinician_brief': [], 'appointment_agenda': [], 'uncertainties': [], 'concern_summaries': []}
    assert ai.validate_synthesis(data, sources, [], locale='en')['patient_overview'] == data['patient_overview']
    data['patient_overview'][0]['text'] = '患者正在服用阿莫西林。'
    with pytest.raises(ai.IntelligenceUnavailable, match='selected patient language'):
        ai.validate_synthesis(data, sources, [], locale='en')


def test_legacy_english_batch_without_locale_migrates_without_provider_call():
    session, _, _ = prepared()
    session['followup_batch'].pop('locale')
    session['locale'] = 'en'
    pipeline.save_followup_draft(session, session['followup_batch']['id'], answers(session)[:1])
    original = deepcopy(session['followup_batch'])
    state = deepcopy(session['_followup'])

    class MustNotTranslate:
        def translate_presentation(self, **kwargs):
            pytest.fail('Existing English presentation must not need a remote translation.')

    pipeline.relocalize_pending_followup(session, intelligence=MustNotTranslate())
    current = session['followup_batch']
    assert current['locale'] == 'en'
    assert current['id'] == original['id'] and current['round'] == original['round']
    assert current['questions'] == original['questions']
    assert current['overview'] == original['overview']
    assert current['draft_answers'] == original['draft_answers']
    assert session['_followup'] == state


def test_legacy_non_english_prose_still_translates_when_switching_to_english():
    session, _, _ = prepared()
    session['followup_batch'].pop('locale')
    session['locale'] = 'en'
    question = session['followup_batch']['questions'][0]
    question['why'] = '记录这次不适随时间发生的变化。'
    calls = []

    class EnglishTranslator:
        def translate_presentation(self, **kwargs):
            calls.append(deepcopy(kwargs))
            return {key: 'Record how this discomfort has changed over time.' for key in kwargs['texts']}

    pipeline.relocalize_pending_followup(session, intelligence=EnglishTranslator())
    assert len(calls) == 1
    assert calls[0]['texts'] == {question['id'] + '.why': '记录这次不适随时间发生的变化。'}
    assert session['followup_batch']['questions'][0]['why'] == 'Record how this discomfort has changed over time.'


def test_empty_legacy_rationale_uses_authored_copy_without_translation_call():
    session, _, _ = prepared()
    for question in session['followup_batch']['questions']:
        question.update(why='', options=[])
    session['followup_batch']['overview'] = ''
    original = deepcopy(session['followup_batch'])
    state = deepcopy(session['_followup'])

    class MustNotTranslate:
        def translate_presentation(self, **kwargs):
            pytest.fail(f"Authored defaults must not need a provider: {kwargs['texts']}")

    for locale in ('zh-CN', 'en'):
        session['locale'] = locale
        pipeline.relocalize_pending_followup(session, intelligence=MustNotTranslate())
        current = session['followup_batch']
        assert all(prose_matches_locale(q['why'], locale) for q in current['questions'])
        assert current['id'] == original['id'] and current['round'] == original['round']
        assert [q['id'] for q in current['questions']] == [q['id'] for q in original['questions']]
        assert current['draft_answers'] == original['draft_answers']
        assert session['_followup'] == state
