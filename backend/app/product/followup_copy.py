"""Deterministic wording for migrating already-asked dynamic item questions.

The stable field identity and patient-supplied item name are unchanged. Migration
never needs a provider call merely to translate an existing question.
"""
from __future__ import annotations

from .locales import translate_text, field_label

_DYNAMIC = {
    'zh-CN': {
        'name': ('名称', '「{name}」的名称是什么？'),
        'dose': ('剂量', '您目前每次服用多少「{name}」？'),
        'frequency': ('服用频率', '您目前多久服用一次「{name}」？'),
        'actual_use': ('实际用法', '您目前是怎样服用「{name}」的？'),
        'experience': ('使用感受', '关于使用「{name}」的感受，您希望医生了解什么？'),
        'supply': ('剩余数量', '您目前还剩多少「{name}」？'),
        'date': ('日期', '「{name}」是什么时候记录或完成的？'),
        'source': ('来源', '「{name}」的来源是什么？'),
        'unit': ('单位', '「{name}」记录中的单位是什么？'),
        'value': ('记录数值', '「{name}」现有记录中的数值是多少？'),
        'reason': ('原因', '当时告知您进行「{name}」的原因是什么？'),
        'ordering_clinician': ('安排人员', '是谁安排了「{name}」？'),
    },
    'zh-TW': {
        'name': ('名稱', '「{name}」的名稱是什麼？'),
        'dose': ('劑量', '您目前每次服用多少「{name}」？'),
        'frequency': ('服用頻率', '您目前多久服用一次「{name}」？'),
        'actual_use': ('實際用法', '您目前是怎樣服用「{name}」的？'),
        'experience': ('使用感受', '關於使用「{name}」的感受，您希望醫師了解什麼？'),
        'supply': ('剩餘數量', '您目前還剩多少「{name}」？'),
        'date': ('日期', '「{name}」是什麼時候記錄或完成的？'),
        'source': ('來源', '「{name}」的來源是什麼？'),
        'unit': ('單位', '「{name}」記錄中的單位是什麼？'),
        'value': ('記錄數值', '「{name}」現有記錄中的數值是多少？'),
        'reason': ('原因', '當時告知您進行「{name}」的原因是什麼？'),
        'ordering_clinician': ('安排人員', '是誰安排了「{name}」？'),
    },
    'ja': {
        'name': ('名称', '「{name}」の名称は何ですか？'),
        'dose': ('服用量', '現在「{name}」を1回にどのくらい服用していますか？'),
        'frequency': ('服用頻度', '現在「{name}」をどのくらいの頻度で服用していますか？'),
        'actual_use': ('実際の使い方', '現在「{name}」をどのように服用していますか？'),
        'experience': ('使用した感想', '「{name}」を使用した経験について、医師に伝えたいことはありますか？'),
        'supply': ('残量', '現在「{name}」はどのくらい残っていますか？'),
        'date': ('日付', '「{name}」が記録または完了したのはいつですか？'),
        'source': ('情報源', '「{name}」の情報源は何ですか？'),
        'unit': ('単位', '「{name}」の記録に表示されている単位は何ですか？'),
        'value': ('記録の数値', '「{name}」の既存の記録に表示されている数値はいくつですか？'),
        'reason': ('理由', '「{name}」について、どのような理由を説明されましたか？'),
        'ordering_clinician': ('手配した人', '「{name}」を手配したのは誰ですか？'),
    },
    'ko': {
        'name': ('이름', '「{name}」의 이름은 무엇인가요?'),
        'dose': ('복용량', '현재 「{name}」을 한 번에 얼마나 복용하시나요?'),
        'frequency': ('복용 빈도', '현재 「{name}」을 얼마나 자주 복용하시나요?'),
        'actual_use': ('실제 복용 방법', '현재 「{name}」을 어떻게 복용하시나요?'),
        'experience': ('사용 경험', '「{name}」 사용 경험 중 의사에게 알리고 싶은 내용은 무엇인가요?'),
        'supply': ('남은 양', '현재 「{name}」이 얼마나 남아 있나요?'),
        'date': ('날짜', '「{name}」은 언제 기록되거나 완료되었나요?'),
        'source': ('출처', '「{name}」의 출처는 무엇인가요?'),
        'unit': ('단위', '「{name}」 기록에 표시된 단위는 무엇인가요?'),
        'value': ('기록된 수치', '「{name}」의 기존 기록에 표시된 수치는 얼마인가요?'),
        'reason': ('이유', '「{name}」에 대해 어떤 이유를 안내받으셨나요?'),
        'ordering_clinician': ('준비한 사람', '「{name}」을 준비한 사람은 누구인가요?'),
    },
}
_LEGACY_REASON = {
    'en': 'This question was already included in your preparation.',
    'zh-CN': '这是本次就诊准备中已经提出的问题。',
    'zh-TW': '這是本次就診準備中已經提出的問題。',
    'ja': '今回の受診準備ですでに提示された質問です。',
    'ko': '이번 진료 준비에서 이미 제시된 질문입니다.',
}


def legacy_question_copy(session: dict, target: dict, rationale: str | None = None) -> dict:
    locale = session.get('locale', 'en')
    result = {'question': translate_text(target['question'], locale), 'display_label': field_label(target['key'], target.get('label', target['key']), locale),
              'rationale': rationale if locale == 'en' and rationale else _LEGACY_REASON.get(locale, _LEGACY_REASON['en'])}
    templates = _DYNAMIC.get(locale)
    if not templates:
        return result
    for item in session.get('items', []):
        if item.get('concern_id') != target['concern_id'] or not item.get('name'):
            continue
        field = next((name for name, key in item.get('fields', {}).items() if key == target['key']), None)
        if field in templates:
            label, template = templates[field]
            result.update(question=template.format(name=item['name']), display_label=f"{item['name']} · {label}")
            break
    return result

# Lifecycle copy is authored, so a failed AI call never forces an English fallback.
_COPY = {
    'optional_ready': (
        'You can add optional detail or review your notes whenever you are ready.',
        '您可以补充更多细节，或随时检查您的记录。', '您可以補充更多細節，或隨時檢查您的紀錄。',
        '세부 내용을 추가하거나 준비되면 기록을 확인할 수 있습니다.', '詳しい内容を追加するか、いつでもメモを確認できます。'),
    'answers_saved': (
        'Your follow-up answers are saved. You can review your preparation notes now.',
        '追问回答已保存，现在可以查看就诊准备记录。', '追問回答已儲存，現在可以查看就診準備紀錄。',
        '추가 답변이 저장되었습니다. 이제 진료 준비 내용을 확인할 수 있습니다.', '追加の回答を保存しました。診察準備のメモを確認できます。'),
    'baseline_changed': (
        'Your baseline answers changed. Previous follow-up questions were closed; review your updated notes.',
        '基本信息已更新，之前的追问已结束。请检查更新后的记录。', '基本資訊已更新，先前的追問已結束。請檢查更新後的紀錄。',
        '기본 답변이 변경되어 이전 추가 질문이 종료되었습니다. 수정된 기록을 확인해 주세요.', '基本情報が変更されたため、以前の追加質問を終了しました。更新したメモを確認してください。'),
    'remaining_question': (
        'You can answer the remaining question or review your notes.',
        '您可以回答剩余的问题，或直接检查记录。', '您可以回答剩餘的問題，或直接檢查紀錄。',
        '남은 질문에 답하거나 기록을 확인할 수 있습니다.', '残りの質問に答えるか、メモを確認できます。'),
    'ready': (
        'Your baseline and optional details are ready. You can review your preparation notes now.',
        '基本信息和补充回答已准备好，现在可以检查就诊准备记录。', '基本資訊和補充回答已準備好，現在可以檢查就診準備紀錄。',
        '기본 정보와 추가 답변이 준비되었습니다. 이제 진료 준비 기록을 확인할 수 있습니다.', '基本情報と追加の回答がそろいました。診察準備のメモを確認できます。'),
    'batch_reason': (
        'All useful optional questions are grouped in one batch; review follows your answers.',
        '需要补充的问题已一次整理好，回答后即可检查全部记录。', '需要補充的問題已一次整理好，回答後即可檢查全部紀錄。',
        '필요한 추가 질문을 한 번에 모았습니다. 답변 후 전체 기록을 확인할 수 있습니다.', '必要な追加質問をまとめました。回答後にすべてのメモを確認できます。'),
    'direct_saved': (
        'Your answers are saved directly. AI organization is unavailable; you can still review your notes.',
        '您的原始回答已保存。AI 整理暂不可用，仍可查看您的记录。', '您的原始回答已儲存。AI 整理暫不可用，仍可查看您的紀錄。',
        '답변 원문이 저장되었습니다. AI 정리는 사용할 수 없지만 기록을 확인할 수 있습니다.', '回答をそのまま保存しました。AI による整理は利用できませんが、メモを確認できます。'),
    'correction_pending': (
        'Your correction is saved but has not been reconciled. Retry the correction before approving; no updated AI summary has been generated.',
        '修改已保存，但尚未核对完成。请先重试核对，再批准分享；AI 摘要尚未更新。', '修改已儲存，但尚未核對完成。請先重試核對，再批准分享；AI 摘要尚未更新。',
        '수정 내용은 저장되었지만 아직 확인되지 않았습니다. 공유 승인 전에 수정을 다시 시도해 주세요. AI 요약은 아직 갱신되지 않았습니다.', '修正は保存されましたが、まだ照合されていません。共有を承認する前に修正を再試行してください。AI 要約はまだ更新されていません。'),
    'check_translation': (
        'Review the wording and any translations against your original source details before sharing.',
        '分享前，请对照原始信息检查摘要的措辞和翻译。', '分享前，請對照原始資訊檢查摘要的措辭和翻譯。',
        '공유 전에 원본 내용과 비교하여 표현과 번역을 확인해 주세요.', '共有する前に、元の情報と照らし合わせて表現と翻訳を確認してください。'),
    'summary_ready': (
        'Your AI preparation summary is ready. Check the wording, translations and source details before approving.',
        'AI 就诊准备摘要已生成。批准分享前，请检查措辞、翻译和原始信息。', 'AI 就診準備摘要已產生。批准分享前，請檢查措辭、翻譯和原始資訊。',
        'AI 진료 준비 요약이 준비되었습니다. 승인 전에 표현, 번역, 원본 정보를 확인해 주세요.', 'AI による診察準備の要約ができました。承認前に表現、翻訳、元の情報を確認してください。'),
    'extraction_unavailable': (
        'Your response is saved, but AI extraction is unavailable. You can review your structured notes or retry optional follow-up.',
        '回答已保存，但 AI 整理暂不可用。您可以检查记录，或重试补充追问。', '回答已儲存，但 AI 整理暫不可用。您可以檢查紀錄，或重試補充追問。',
        '답변은 저장되었지만 AI 정리를 사용할 수 없습니다. 기록을 확인하거나 추가 질문을 다시 시도할 수 있습니다.', '回答は保存されましたが、AI による整理を利用できません。メモの確認や追加質問の再試行ができます。'),
    'form_organized': (
        'Saved form details were organized using OpenAI.',
        '已使用 OpenAI 整理保存的信息。', '已使用 OpenAI 整理儲存的資訊。',
        'OpenAI 를 사용해 저장된 정보를 정리했습니다.', '保存した情報を OpenAI で整理しました。'),
    'followup_organized': (
        'Your follow-up answers were saved and organized.',
        '追问回答已保存并整理。', '追問回答已儲存並整理。',
        '추가 답변을 저장하고 정리했습니다.', '追加の回答を保存し、整理しました。'),
    'language_unavailable': (
        'The AI wording could not be translated into your selected language. Your answers remain saved; retry translation or review your notes.',
        'AI 内容暂时无法转换为您选择的语言。回答已保存；请重试翻译，或检查已有记录。', 'AI 內容暫時無法轉換為您選擇的語言。回答已儲存；請重試翻譯，或檢查已有紀錄。',
        'AI 내용을 선택한 언어로 번역하지 못했습니다. 답변은 저장되어 있습니다. 번역을 다시 시도하거나 기존 기록을 확인해 주세요.', 'AI の内容を選択した言語に翻訳できませんでした。回答は保存されています。翻訳を再試行するか、既存のメモを確認してください。'),
    'ai_unavailable': (
        'The AI operation could not be completed. Your notes remain saved.',
        'AI 暂时未能完成处理，您的记录已保存。', 'AI 暫時未能完成處理，您的紀錄已儲存。',
        'AI 처리를 완료하지 못했습니다. 기록은 저장되어 있습니다.', 'AI の処理を完了できませんでした。メモは保存されています。'),
}
_LOCALE_INDEX = {'en': 0, 'zh-CN': 1, 'zh-TW': 2, 'ko': 3, 'ja': 4}


def followup_copy(key: str, locale: str = 'en') -> str:
    return _COPY[key][_LOCALE_INDEX.get(locale, 0)]


def localized_lifecycle(text: str, locale: str = 'en') -> str:
    """Translate exact authored messages; never rewrite patient-provided text."""
    if text in _LEGACY_REASON.values():
        return _LEGACY_REASON.get(locale, _LEGACY_REASON['en'])
    for row in _COPY.values():
        if text in row:
            return row[_LOCALE_INDEX.get(locale, 0)]
    return text
