"""Authored symptom-history copy is complete without translating patient evidence."""
from copy import deepcopy

import pytest

from app.product import engine, forms, oldcarts, presentation
from app.product.followup_copy import legacy_question_copy
from app.product.locales import field_label, prose_matches_locale, translate_text


PATIENT_LOCALES = ('zh-CN', 'zh-TW', 'ko', 'ja')
STORY_COPY = (
    'Your symptom story',
    'Patient-reported details and remaining gaps. This is not a medical completeness or safety score.',
    'Recorded', 'Partly recorded', 'Not yet recorded', 'Not sure',
    'Chose not to answer', 'Not applicable', 'Spreading or radiation',
    'Radiation or spread',
)


@pytest.mark.parametrize('locale', PATIENT_LOCALES)
def test_all_new_history_questions_labels_and_states_are_authored_in_patient_language(locale):
    """An untranslated source label must not leak into the wizard or PDF."""
    sources = list(STORY_COPY) + [label for _, label in oldcarts.DIMENSIONS]
    sources += [text for pair in oldcarts.NEW_QUESTIONS.values() for text in pair]
    for source in sources:
        localized = translate_text(source, locale)
        assert localized != source, (locale, source)
        assert prose_matches_locale(localized, locale), (locale, source, localized)
    for key, (label, _) in oldcarts.NEW_QUESTIONS.items():
        assert field_label(key, label, locale) == translate_text(label, locale)
        # Engine source labels also derive from the stable key, unlike the
        # curated wizard label. Fallbacks and report rows must localize both.
        source_label = key.replace('_', ' ').capitalize()
        assert field_label(key, source_label, locale) != source_label


@pytest.mark.parametrize('locale', PATIENT_LOCALES)
def test_new_history_answer_aids_translate_labels_values_and_helpers(locale):
    """The text actually submitted by a choice is as localized as its label."""
    for key in ('symptom_onset_character', 'symptom_episode_duration', 'severity',
                'aggravating_factors', 'relieving_factors'):
        guidance = presentation.for_field('WF-01', key)
        assert guidance
        sources = [guidance['helper']]
        sources += [option[k] for option in guidance['options'] for k in ('label', 'value')]
        for source in sources:
            localized = translate_text(source, locale)
            assert localized != source, (locale, key, source)
            assert prose_matches_locale(localized, locale), (locale, key, source)
    # A failure to distinguish the direction would change the patient's account.
    for worsening, relieving in (
        ('What makes it worse', 'What helps'),
        ('I have not noticed anything that makes it worse.', 'I have not noticed anything that eases it.'),
    ):
        assert translate_text(worsening, locale) != translate_text(relieving, locale)


@pytest.mark.parametrize('locale', PATIENT_LOCALES)
def test_existing_history_followup_can_be_reworded_without_rewriting_patient_evidence(locale):
    session = forms.initialize(engine.new_intake({'id': 'patient'}, 'synthetic', ['WF-01']))
    session['locale'] = locale
    concern = session['concerns'][0]
    patient_text = 'Rest sometimes helps, but I am not sure. 左小腿。'
    forms.apply_baseline(session, [{'concern_id': concern['id'], 'key': 'concern_description',
                                    'value': patient_text, 'status': 'FILLED'}])
    before = deepcopy(session)
    for key, (label, question) in oldcarts.NEW_QUESTIONS.items():
        target = {'concern_id': concern['id'], 'key': key, 'label': key.replace('_', ' ').capitalize(), 'question': question}
        copy = legacy_question_copy(session, target)
        for name in ('question', 'display_label', 'rationale'):
            assert prose_matches_locale(copy[name], locale), (key, name, copy[name])
        assert copy['question'] != question
        assert copy['display_label'] == field_label(key, target['label'], locale)
    assert session == before
    assert concern['slots']['concern_description']['value'] == patient_text
