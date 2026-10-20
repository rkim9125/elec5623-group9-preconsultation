"""Authored structural copy for the factual report; patient evidence is untouched."""
ROWS = [
    ('not explored', '尚未讨论', '尚未討論', '아직 다루지 않음', '未確認'),
    ('partially prepared', '已准备部分信息', '已準備部分資訊', '일부 정보 준비됨', '一部の情報を準備済み'),
    ('prepared with gaps', '已准备，部分信息未提供', '已準備，部分資訊未提供', '준비됨, 일부 정보 미제공', '準備済み・一部情報なし'),
    ('preparation fields supplied', '准备信息已填写', '準備資訊已填寫', '준비 정보 입력 완료', '準備情報を入力済み'),
    ('PATIENT PREPARATION NOTES', '就诊准备记录', '就診準備紀錄', '환자 진료 준비 기록', '受診準備の記録'),
    ('Patient-reported information for a planned consultation. This record does not establish a diagnosis or whether it is safe to wait.',
     '为计划中的就诊整理的患者自述。本记录不构成诊断，也不能判断是否可以安全等待。',
     '為計畫中的就診整理的患者自述。本紀錄不構成診斷，也不能判斷是否可以安全等待。',
     '예정된 진료를 위해 환자가 직접 제공한 정보입니다. 이 기록은 진단이나 안전하게 기다릴 수 있는지에 대한 판단이 아닙니다.',
     '予定した受診に向けて患者ご自身が伝えた情報です。この記録は診断や、安全に待てるかどうかの判断を示すものではありません。'),
    ('Reason, priorities and shared background', '就诊原因、重点与健康背景', '就診原因、重點與健康背景', '진료 이유, 우선순위 및 공통 배경', '受診理由・優先事項・共通の背景'),
    ('No details supplied for this section.', '本部分尚未提供详情。', '本部分尚未提供詳情。', '이 항목에는 제공된 내용이 없습니다.', 'この項目の詳細はまだ提供されていません。'),
    ('Your corrections are reflected in this draft. Superseded wording remains in your private conversation.',
     '您的更正已体现在此草稿中。旧内容仅保留在您的私人对话记录中。', '您的更正已反映在此草稿中。舊內容僅保留在您的私人對話紀錄中。',
     '수정 사항이 이 초안에 반영되었습니다. 이전 내용은 비공개 대화 기록에 남아 있습니다.', '修正内容はこの下書きに反映されています。以前の内容は非公開の会話記録に残ります。'),
    ('Patient notes not yet structured', '尚未整理到具体项目的患者补充', '尚未整理至具體項目的患者補充', '아직 항목별로 정리되지 않은 환자 메모', 'まだ項目別に整理されていない患者のメモ'),
    ('Attachments for clinician review', '供医生查看的附件', '供醫師查看的附件', '의료진 검토용 첨부자료', '医療者の確認用添付資料'),
    ('uploaded by the patient; contents not interpreted by this tool', '患者上传的原始资料；此记录未解读其内容', '患者上傳的原始資料；此紀錄未解讀其內容', '환자가 업로드한 원본 자료이며 이 기록에서는 내용을 해석하지 않았습니다', '患者がアップロードした原本です。この記録では内容を解釈していません'),
    ('Unknown, skipped and uncollected information', '未知、跳过和尚未收集的信息', '未知、略過和尚未收集的資訊', '불확실하거나 건너뛴 정보 및 아직 수집되지 않은 정보', '不明・回答を見送った情報・未収集の情報'),
    ('Shared information', '共同信息', '共同資訊', '공통 정보', '共通の情報'),
    ('Patient corrections awaiting reconciliation', '等待核对整合的患者更正', '等待核對整合的患者更正', '확인 및 반영을 기다리는 환자 수정 사항', '確認・反映待ちの患者による修正'),
    ('Not yet collected', '尚未收集', '尚未收集', '아직 수집되지 않음', '未収集'),
    ('Unknown or uncertain', '未知或不确定', '未知或不確定', '모르거나 확실하지 않음', '不明または不確か'),
    ('Patient chose not to include', '患者选择不包含此信息', '患者選擇不包含此資訊', '환자가 포함하지 않기로 선택함', '患者が記載しないことを選択'),
    ('Selected options:', '已选选项：', '已選選項：', '선택한 항목:', '選択した項目：'),
    ('Additional details:', '补充说明：', '補充說明：', '추가 설명:', '補足：'),
]


def summary_text(text, locale='en'):
    languages = ('en', 'zh-CN', 'zh-TW', 'ko', 'ja')
    index = languages.index(locale) if locale in languages else 0
    for row in ROWS:
        if text in row:
            return row[index]
    from .locales import translate_text
    return translate_text(text, locale)
