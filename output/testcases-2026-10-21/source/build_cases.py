"""Build fictional, source-mapped manual QA cases. No app/network/database writes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = json.loads((ROOT / 'field-map.json').read_text())
REPORT = json.loads((ROOT / 'report-data.json').read_text())

def answer(text='', choices=(), note=''):
    return {'text': text, 'choice_labels': list(choices), 'note': note}

def profile(values):
    return [dict(step=s['step'], key=s['key'], question=s['question']['zh_CN'], answer=v)
            for s, v in zip(MAP['profile_steps'], values)]

def steps(workflow_id, entries):
    w = next(w for w in MAP['workflows'] if w['workflow_id'] == workflow_id)
    assert len(entries) == len(w['visible_steps'])
    result = []
    for field, entry in zip(w['visible_steps'], entries):
        options = {o['label']['zh_CN']: o['value'] for o in field['options']}
        values = [options[label] for label in entry['choice_labels']]
        stored = ('Selected options:\n' + '\n'.join('- ' + v for v in values)) if values else ''
        if entry['text']:
            stored += ('\n\nAdditional details:\n' if values else '') + entry['text']
        result.append(dict(step=field['step'], key=field['key'], owner=field['owner'],
                           question=field['question']['zh_CN'], control=field['control'],
                           canonical_choices=values, storage_value=stored, **entry))
    return result

bp = REPORT['case02']['home_monitoring']
bp_text = ('家庭上臂式电子血压计，左上臂，坐位休息5分钟后测量。每天07:30和19:30各记录一次，血压单位mmHg，脉搏单位次/分。\n'
           + '\n'.join(f"{r['date']} {r['time']}：{r['systolic_mmhg']}/{r['diastolic_mmhg']}，脉搏{r['pulse_bpm']}" for r in bp['readings'])
           + '\n14次读数的算术平均为140.2/87.1 mmHg，平均脉搏70.9次/分。最后一次为2026-10-20 19:30的141/88，脉搏72。照片对应最后一条记录。')

cases = [
  {
    'id':'TC01', 'folder':'case01', 'name':'Alex Lin (TEST)', 'title':'双膝疼痛：部位多选与既往反应',
    'workflow_id':'WF-01', 'topic':'腿痛', 'age_at_test':38,
    'summary':'38岁男性，长距离步行后双侧膝盖前方酸痛，右膝有一小块瘀痕。用于测试多选、语音、未知Rh、药物历史和图片/PDF的一致性。',
    'profile':profile(['1988-04-12','男性','ABO选 O；Rh选“我不知道”（保存为 O，不是 O+ 或 O−）。',
      '无已确诊的长期疾病。','无手术史。','父亲有高血压。','偏好简体中文；无额外沟通或行动协助需求。']),
    'profile_storage':{'date_of_birth':'1988-04-12','sex_at_birth':'male','blood_group':'O','medical_history':'无已确诊的长期疾病。','surgical_history':'无手术史。','family_history':'父亲有高血压。','accessibility_needs':'偏好简体中文；无额外沟通或行动协助需求。'},
    'steps':steps('WF-01',[
      answer('2026年10月14日长距离步行后，双侧膝盖前方开始酸痛，走路和上下楼梯时比较明显。10月19日注意到右膝前方有一小块淡淡的瘀痕，仍然可以走路。',note='可用语音读这一段：点麦克风 → 说话 → 点方形停止 → 转写自动填入本题原有输入框 → 在输入框中核对、修改 → 继续。'),
      answer('两边都是膝盖前方，右侧比左侧明显；瘀痕只在右膝。',['右侧膝盖 · 正面','左侧膝盖 · 正面'],'切到“正面”，分别点膝盖行的“右”和“左”；应同时保留两处高亮。左右以患者身体为准，照片中的右膝位于画面左侧。'),
      answer('以酸痛和轻微僵硬为主。',['酸痛','僵硬']),
      answer('每天走动时会出现几次，不是一直疼。',['每天多次']),
      answer('长距离步行或上下楼梯时明显。',['步行','上下楼梯']),
      answer('走得久或上下楼梯时更明显；坐下休息大约20分钟后减轻。',['随活动变化','随休息变化']),
      answer('暂停了平时的跑步；仍能走路和完成日常事务，坐着工作与睡眠没有明显受影响。',['运动或活动']),
      answer('希望了解双膝不适和右膝瘀痕的情况，讨论接下来的检查或活动安排。',['了解我的症状','讨论下一步安排']),
      answer('目前每天服用维生素C 1片，每片剂量不清楚。2026年10月19日曾服用对乙酰氨基酚500 mg一次；不是每天服用。没有使用其他药物或吸入剂。'),
      answer('2015年服用阿莫西林后出现皮疹，这是我的回忆，尚未确认是否过敏，没有做过正式过敏检测。'),
      answer('我担心这会影响月底的徒步计划。想问医生目前是否需要调整活动，以及有哪些需要进一步了解的情况。')
    ]),
    'followup_bank':[
      {'topic':'开始时间 / 发展变化','text':'2026年10月14日开始。到10月21日总体差不多，没有持续加重。'},
      {'topic':'持续性 / 频率 / 程度','text':'时有时无，每天活动时出现几次。上下楼梯时大约4/10，休息时大约1/10；不是持续不间断的疼痛。'},
      {'topic':'已经尝试的方法 / 效果','text':'减少长距离步行和跑步，休息后会减轻。2026年10月19日只服过一次对乙酰氨基酚500 mg，效果不确定。'},
      {'topic':'之前就诊 / 检查 / 医生说明','text':'2026年10月20日做过膝部体格检查，记录已上传。未建立明确诊断，没有X光、MRI或化验结果。医疗人员姓名未在本测试资料中提供。'},
      {'topic':'外伤、瘀痕或药物/反应的细节','text':'没有记得明显跌倒或扭伤；10月19日发现右膝淡瘀痕，具体形成原因不清楚。维生素C每片剂量不清楚；阿莫西林后的皮疹是2015年的自述，未正式确认。'}
    ],
    'uploads':[
      {'path':'case01/knee-photo.png','label':'膝部照片 · PNG','action':'上传本图。照片日期2026-10-19；右膝瘀痕在画面左边。','kind':'image'},
      {'path':'case01/medical-exam.pdf','label':'膝部检查表 · PDF（1页）','action':'上传本报告。检查日期2026-10-20；包含生命体征、双膝查体、药物与过敏自述。','kind':'pdf'}
    ],
    'alternatives':[{'path':'case01/medical-exam-page-1.png','label':'检查表 PNG（测试图片OCR时替代同一份PDF）'}],
    'expected':[
      '身体图同时保留“右膝前方”和“左膝前方”；仅右膝有瘀痕，不得误写成左侧或双侧瘀痕。',
      '档案中血型是 O，Rh未知；不得补成 O+。已保存病史应带入本次，不能要求重复输入。',
      '维生素C为当前补充剂且剂量未知；对乙酰氨基酚500 mg是10月19日的一次历史用药，不应变为每日药物。',
      '阿莫西林皮疹应保留“患者自述、未确认”；不得写成已经确诊的过敏或完全没有过敏。',
      '检查表读数应保留：122/78 mmHg、72次/分、36.7°C、178 cm、74 kg；右膝活动范围0–125°，左膝0–130°。',
      '没有影像或化验，不能生成“X光/MRI正常”；照片仅用于测试外观描述，不能作为确诊依据。'
    ],
    'repeat_check':'同一测试患者新建第二次“腿痛”就诊。确认7项档案复用；药物与过敏输入下方显示上次回答及日期。点击“填入本次回答”后，将药物改为“目前每天维生素C 1片，剂量未知；上次提到的对乙酰氨基酚是2026-10-19的一次用药，此后没有再服用。”核对旧记录不被改写。',
  },
  {
    'id':'TC02', 'folder':'case02', 'name':'Maya Chen (TEST)', 'title':'高血压复诊：连续读数与化验附件',
    'workflow_id':'WF-24', 'topic':'已确诊高血压复查', 'age_at_test':55,
    'summary':'55岁女性，已有高血压与血脂异常病史，带7天家庭血压记录和化验报告复查，无新症状。用于测试连续数值、单位、用药及附件提取。',
    'profile':profile(['1971-09-08','女性','ABO选 AB；Rh选“阳性（+）”（保存为 AB+）。',
      '2021年被告知有高血压；2024年被告知有血脂异常。','1999年做过阑尾切除手术。','父亲有高血压，母亲有糖尿病。','偏好简体中文，希望获得清晰的书面用药清单。']),
    'profile_storage':{'date_of_birth':'1971-09-08','sex_at_birth':'female','blood_group':'AB+','medical_history':'2021年被告知有高血压；2024年被告知有血脂异常。','surgical_history':'1999年做过阑尾切除手术。','family_history':'父亲有高血压，母亲有糖尿病。','accessibility_needs':'偏好简体中文，希望获得清晰的书面用药清单。'},
    'steps':steps('WF-24',[
      answer('这次是预约的高血压复查，没有新出现的不适。我想一起看看最近7天的家庭血压记录、10月18日的化验结果和目前的用药情况。'),
      answer('2021年医生告知我有高血压，之后一直定期复查。2024年又被告知血脂异常。具体的个人血压目标我记不清楚，希望这次确认。'),
      answer('2026年10月8日，诊室血压146/90 mmHg，脉搏74次/分。'),
      answer(bp_text,note='直接复制完整14条读数；这一步是文字输入，不需要逐行新建表格。10月20日是附件整理日期，最近一次诊室复查仍是10月8日。'),
      answer('最近整理了7天的家庭血压记录。10月16日早晨外出时漏服了一次氨氯地平，希望讨论怎样更容易记住服药；没有新症状。',['日常作息','居家记录']),
      answer('希望复查已有高血压，讨论家庭血压及化验结果，并核对现在的用药和漏服情况。',['复查已有健康问题','讨论检查结果','讨论用药']),
      answer('氨氯地平（amlodipine）5 mg，每天07:30服一次，仅2026年10月16日漏服一次。阿托伐他汀（atorvastatin）10 mg，每晚服一次。没有使用其他药物、吸入剂或补充剂。'),
      answer('据我所知，没有药物或食物过敏，也没有需要记录的既往药物反应。'),
      answer('希望医生帮我确认个人血压目标，解释这次化验结果，并讨论如何避免忘记服药。没有其他新症状需要补充。')
    ]),
    'followup_bank':[
      {'topic':'家庭读数来源 / 时间 / 单位','text':'家庭上臂式电子血压计，左上臂；坐位休息5分钟后测量。2026-10-14至2026-10-20，每天07:30和19:30各一条。血压单位mmHg，脉搏单位次/分。每次只记录了一条，未提供重复测量值。'},
      {'topic':'用药体验 / 漏服 / 副作用','text':'氨氯地平5 mg每天07:30，只有10月16日漏服一次；阿托伐他汀10 mg每晚。目前未注意到明显药物不适，希望讨论帮助记住服药的方法。'},
      {'topic':'已做检查 / 化验日期','text':'2026年10月18日08:10空腹采血；具体9项数值和单位见已上传PDF第1页。10月20日只是测试附件整理日期，不是另一次诊室复查。'},
      {'topic':'以前就诊 / 医生说明 / 目标','text':'最近一次诊室复查为2026年10月8日，146/90 mmHg，脉搏74。2021年被告知有高血压。个人目标值和医疗人员姓名未在本测试资料中提供，我不确定。'},
      {'topic':'新症状 / 生活影响 / 其他担忧','text':'本次是预约复查，没有新症状，日常活动没有新的受限。主要希望理解家庭记录和检查结果，并讨论漏服药的情况。'}
    ],
    'uploads':[
      {'path':'case02/bp-monitor-photo.png','label':'血压计照片 · PNG','action':'上传本图。显示2026-10-20 19:30：141/88 mmHg，脉搏72，对应日志最后一条。','kind':'image'},
      {'path':'case02/checkup-and-bp-log.pdf','label':'化验表与7天血压日志 · PDF（2页）','action':'上传完整2页PDF。第1页为9项空腹化验；第2页为14次家庭血压和脉搏。','kind':'pdf'}
    ],
    'alternatives':[{'path':f'case02/checkup-and-bp-log-page-{n}.png','label':f'报告第{n}页 PNG（测试图片OCR时替代PDF）'} for n in [1,2]],
    'expected':[
      '保留“预约复诊、没有新症状”；不应把本次写成新发症状问诊，也不应强制新增疼痛程度。',
      '档案血型是 AB+；高血压2021年、血脂异常2024年及阑尾切除1999年的信息保持一致。',
      '14次家庭读数不能与诊室146/90混在一起计算。若显示均值，应为140.2/87.1 mmHg、脉搏70.9次/分；最新读数141/88、72与照片吻合。',
      '必须保留采血日期10月18日与诊室复查10月8日的区别，不能把附件整理日期10月20日当作采血或诊室复查日期。',
      '氨氯地平5 mg每天早晨、阿托伐他汀10 mg每晚；仅10月16日漏服一次，不能扩写成长期不规律服药。',
      'PDF两页均可被处理。化验值及单位应与原文一致；不得把肌酐74 µmol/L写成74 mg/dL或自行添加报告未给出的参考范围。'
    ],
    'repeat_check':'同一测试患者再次新建“已确诊高血压复查”。档案应自动带入；上次药物和无已知过敏回答只作为可点击候选。不要把10月14–20日的旧血压当成今天新测值；若再次使用，应明确写“历史记录，日期不变”。'
  }
]

data = {
 'title':'PreConsult：两套可照填的虚构测试病例', 'as_of':'2026-10-21',
 'notice':'所有人物、图片、数值和医疗检查表均为虚构测试数据，不是真实医疗记录。',
 'execution_status':'这是测试材料包；未替用户注册、修改现有患者档案、上传资料或向医生分享。',
 'setup':[
   '打开 http://127.0.0.1:8000/#/patient，语言选择“简体中文”。本说明对应2026-10-21本地代码；应用默认语言仍为英语。',
   '准备两个你控制且能收验证码的独立测试邮箱，分别用于TC01与TC02；与医生邮箱也必须不同。邮箱填你的实际测试邮箱，验证码填收到的验证码；没有固定测试密码。',
   '登录时选择“患者”。若页面要求姓名，分别填 Alex Lin (TEST) 或 Maya Chen (TEST)；已有测试账号可在“我的账号”修改名称。不要把两例混在同一个患者档案里。',
   '在“我的账号”或新建页的“添加档案”中，依照本例7步保存健康背景。新建就诊时开启“本次就诊使用已保存的信息”。',
   '点“新建就诊准备”，选择本例指定症状卡片。高级选项保留 gpt-6-astra；勾选AI处理同意，再点“开始吧”。如显示就诊标题，可使用本例TC编号加标题。',
   '每个问题先点指定选项，再把“填写内容”复制到文字框；复制内容不包含系统的 Selected options 等内部格式。每步点“继续”，最后点“检查回答”。'
 ],
 'voice_check':[
   '在TC01第1题用语音读出给定文字。先授予浏览器麦克风权限，然后录音。',
   '点方形停止后应开始转写，结果直接填入本题原有的可编辑输入框；不出现额外的转写确认步骤，也无需先点发送箭头。',
   '在原输入框中检查日期、“双侧”和“右膝”等关键字，并按需修改；完成后直接点“继续”或当前页面的提交按钮。停止录音只回填文字，不应自动提交或跳到下一题。'
 ],
 'attachment_steps':[
   '在“添加文件或返回某个问题”展开区，或右侧“辅助文件”区域，上传本例列出的1张照片与1份PDF。建议在最终AI分析前上传。',
   '只选择本例文件，不要把另一病例的资料混入。PDF页面PNG是OCR替代测试用：同一次正常测试无需将PDF和它的页面PNG重复上传。',
   '若提供“提取详情”，点击后核对日期、患者、左右侧、单位，再确认纳入。识别不清的值应回到原报告核对，不猜测。',
   '支持PDF、PNG、JPG、WebP，单个文件上限10 MB；本包的每个上传文件均小于上限。'
 ],
 'followup_instructions':[
   '点击开始AI分析与追问后，每题应独立占一个Wizard步骤，显示进度；通常一次最多5题，完成后统一检查和提交。',
   'AI会根据已填写及附件选择问题，下面每例的5组是事实答案库，不保证出现5题或固定顺序；已有答案被识别后可以少问或不问。',
   'A/B/C选项与病例事实吻合时才选择，再按需补充；不吻合则自定义填写。没有资料的剂量、日期或医疗人员姓名，选“我不知道”或跳过，不编造。',
   '完成一题后测试“返回”再前进，答案应保留；完成部分题目后刷新，应恢复已存草稿。全部答完点检查回答，逐项确认后再统一提交。正常情况下不应无故启动第二轮。'
 ],
 'review_and_share':[
   '审核页逐项核对：姓名、出生日期、血型、部位/症状、时间、药物与过敏、附件、AI分析。具体措辞或分析结论不必与示例完全一致，但不得捏造病例事实。',
   '若出现旧版“相关病史”“最担心的事”“想问医生的问题”三个展开项：病史应来自档案；担忧和咨询问题已合并填在“还有什么希望医生了解的”，不必再重复输入。',
   '仅在你要实际测试分享时，填写已注册的医生邮箱 jtomtan@qq.com（tomtan，末尾没有额外的g），确认患者邮箱与它不同。',
   '检查内容后勾选批准分享，点击“批准并分享”。这是会改变本地分享状态的手动步骤，本材料包未代为执行。',
   '用另一个浏览器配置或无痕窗口打开 http://127.0.0.1:8000/#/doctor，选医生并用该邮箱收到的验证码登录。应该看到获授权的对应病例、审核后的摘要和附件；不应串到另一个患者。',
   '可再从患者端撤回分享，刷新医生页验证访问已撤销。未注册邮箱的负向测试：应显示医生需先注册的提示并保留草稿，不应显示成功。'
 ],
 'cases':cases,
 'quality_checks':[
   '每例7个档案字段；TC01固定11题，TC02固定9题；条件项或AI问题可能随证据出现。',
   '测试材料中的每个关键数值、时间、左右侧都有明确来源；病例间不混用。',
   '材料包生成及验证不依赖调用AI服务，未验证实际模型输出；实际跑测时记录差异，而不是声称已经通过。'
 ],
 'generation':{'images':'Built-in image_gen tool','prompts':'source/image-prompts.json','reports':'ReportLab; exact values from report-data.json','field_map':'field-map.json'}
}

(ROOT / 'testcases.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
for c in cases:
    rows=[data['notice'],c['id']+' | '+c['title'],c['name'],'\n【健康档案】']
    for p in c['profile']: rows += [f"{p['step']}. {p['question']}",p['answer'],'']
    rows += ['【健康信息：'+c['topic']+'】']
    for s in c['steps']:
        rows += [f"{s['step']}. {s['question']}"]
        if s['choice_labels']: rows += ['选择：'+'、'.join(s['choice_labels'])]
        if s['text']: rows += [s['text']]
        if s['note']: rows += ['操作：'+s['note']]
        rows += ['']
    rows += ['【AI追问参考，不保证固定题目】']
    for f in c['followup_bank']: rows += [f['topic'],f['text'],'']
    rows += ['【验收重点】'] + c['expected'] + ['\n【同一患者再次使用】',c['repeat_check']]
    (ROOT/c['folder']/'answers.txt').write_text('\n'.join(rows)+'\n')
print('Built testcases.json and 2 case answer text files.')
