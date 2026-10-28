"""Bounded checks on model-authored prose, never on the patient's own words.

These checks reduce instruction echo; they are not a semantic jailbreak detector.
The security boundary remains server-side ownership and the absence of model
tools, shell access, database queries, or an application-action dispatcher.
"""
from __future__ import annotations

import re
import unicodedata


_SECRET = re.compile(r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|re_[A-Za-z0-9_-]{24,})\b')
_COMMAND = re.compile(
    r'(?i)\b(?:rm\s+-[a-z]*[rf][a-z]*\s+|remove-item\s+[^\n;]{0,80}-(?:recurse|force)|'
    r'(?:drop|truncate)\s+(?:table|database)\s+|(?:delete|wipe|erase|destroy|format)\s+'
    r'(?:(?:the|your|this|entire|all|operating)\s+){0,4}(?:system|server|database|filesystem|hard drive)\b|'
    r'(?:retrieve|fetch|show|export|download|reveal)\s+[^.!?\n]{0,45}'
    r'(?:another|other|all)\s+patients?[’\x27]?\s+(?:records?|information|data|details|files)|'
    r'(?:reveal|print|display|return|expose)\s+(?:(?:the|your|server|secret)\s+){0,3}(?:api keys?|credentials?|environment variables?))|'
    r'(?:删除|刪除|清空|摧毁|摧毀).{0,8}(?:系统|系統|服务器|伺服器|数据库|資料庫)|'
    r'(?:获取|獲取|取得|显示|顯示|导出|匯出|下载|下載).{0,12}(?:其他|别的|別的|另一位|所有).{0,4}(?:患者|病人).{0,6}(?:信息|資訊|资料|資料|病历|病歷|记录|記錄)|'
    r'(?:透露|输出|輸出|显示|顯示).{0,8}(?:API.?密钥|API.?密鑰|环境变量|環境變數)|'
    r'(?:システム|サーバー|データベース).{0,8}(?:削除|消去|破壊)|'
    r'(?:他の|別の|全ての)患者.{0,8}(?:情報|記録|データ).{0,8}(?:取得|表示|開示|出力)|'
    r'(?:시스템|서버|데이터베이스).{0,8}(?:삭제|파괴|지우)|'
    r'(?:다른|모든)\s*환자.{0,8}(?:정보|기록|데이터).{0,8}(?:가져|조회|공개|출력)'
)
_DENIAL = re.compile(
    r'(?i)\b(?:cannot|can\x27t|can’t|will not|won\x27t|won’t|do not|don\x27t|don’t|must not|never|unable to|refuse to)\b[^.;!?\n]{0,70}$|'
    r'(?:不能|不会|不會|不应|不應|不要|拒绝|拒絕)[^。！？\n]{0,60}$'
)
_REPORTED = re.compile(
    r'(?i)\b(?:the patient|patient|user)\s+(?:reports?|reported|describes?|described|quoted|mentions?|mentioned|asks?|asked)\b[^.;!?\n]{0,90}$|'
    r'(?:患者|病人|用户|用戶)(?:表示|提到|描述|引用|担心|擔心)[^。！？\n]{0,80}$'
)
_DENIAL_AFTER = re.compile(
    r'^(?:しません|できません|しない|することはできません|하지 않습니다|할 수 없습니다|하지 마세요)'
)


def unsafe_model_instruction(text: str) -> bool:
    """Reject explicit action echo, while retaining denials and reported worries."""
    normalized = unicodedata.normalize('NFKC', text)
    normalized = re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060\ufeff]', '', normalized)
    if _SECRET.search(normalized):
        return True
    for match in _COMMAND.finditer(normalized):
        prefix = re.split(r'[.;!?。！？\n]|\b(?:but|however)\b', normalized[:match.start()], flags=re.I)[-1]
        suffix = normalized[match.end():].lstrip()
        if _DENIAL.search(prefix) or _REPORTED.search(prefix) or _DENIAL_AFTER.match(suffix):
            continue
        return True
    return False


def instruction_failure(locale: str = 'en') -> str:
    messages = {
        'en': 'The AI draft contained unrelated instructions. Your notes and file are unchanged. Please retry or enter the details yourself.',
        'zh-CN': 'AI 草稿包含无关指令。您的记录和文件未被修改。请重试或自行填写相关信息。',
        'zh-TW': 'AI 草稿包含無關指令。您的記錄和檔案未被修改。請重試或自行填寫相關資訊。',
        'ko': 'AI 초안에 관련 없는 지시가 포함되어 있습니다. 기록과 파일은 변경되지 않았습니다. 다시 시도하거나 내용을 직접 입력해 주세요.',
        'ja': 'AI の下書きに無関係な指示が含まれていました。記録とファイルは変更されていません。再試行するか、内容を直接入力してください。',
    }
    return messages.get(locale, messages['en'])
