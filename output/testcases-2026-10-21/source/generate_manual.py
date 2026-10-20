"""Printable Chinese test instructions, built from the parent-owned canonical JSON."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "testcases.json").read_text())
DEST = ROOT / "manual.pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("ManualChinese", str(FONT_DIR / "Arial Unicode.ttf")))
pdfmetrics.registerFont(TTFont("ManualLatinBold", str(FONT_DIR / "Arial Bold.ttf")))
pdfmetrics.registerFontFamily("ManualChinese", normal="ManualChinese", bold="ManualChinese", italic="ManualChinese", boldItalic="ManualChinese")
W, H = A4
M = 43
CW = W - M * 2
INK = colors.HexColor("#193E36")
MUTED = colors.HexColor("#526A62")
TEAL = colors.HexColor("#1D7566")
PALE = colors.HexColor("#EFF5EF")
LINE = colors.HexColor("#D9E4DB")
CREAM = colors.HexColor("#FFFAED")
AMBER = colors.HexColor("#785820")

STYLES = {
    "body": ParagraphStyle("body", fontName="ManualChinese", fontSize=9.6, leading=15.6, textColor=INK, wordWrap="CJK", spaceAfter=7),
    "small": ParagraphStyle("small", fontName="ManualChinese", fontSize=8.6, leading=13.2, textColor=MUTED, wordWrap="CJK", spaceAfter=5),
    "heading": ParagraphStyle("heading", fontName="ManualChinese", fontSize=22, leading=29, textColor=INK, wordWrap="CJK", spaceAfter=10),
    "subheading": ParagraphStyle("subheading", fontName="ManualChinese", fontSize=12, leading=18, textColor=TEAL, wordWrap="CJK", spaceBefore=10, spaceAfter=6),
    "question": ParagraphStyle("question", fontName="ManualChinese", fontSize=11, leading=17, textColor=INK, wordWrap="CJK", spaceAfter=7),
    "label": ParagraphStyle("label", fontName="ManualChinese", fontSize=8.7, leading=13.5, textColor=TEAL, wordWrap="CJK", spaceAfter=4),
    "table": ParagraphStyle("table", fontName="ManualChinese", fontSize=9, leading=14.1, textColor=INK, wordWrap="CJK"),
    "tableSmall": ParagraphStyle("tableSmall", fontName="ManualChinese", fontSize=8.4, leading=12.8, textColor=INK, wordWrap="CJK"),
}


def p(text, style="body"):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), STYLES[style])


def title(kicker, text, subtitle=""):
    out = [p(kicker, "label"), p(text, "heading")]
    if subtitle:
        out.append(p(subtitle, "small"))
    return out


def numbered(items, start=1, style="body"):
    return [p(f"{i:02d}  {item}", style) for i, item in enumerate(items, start)]


def note(text):
    table = Table([[p(text, "small")]], colWidths=[CW])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E9DAB7")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def profile(case):
    rows = [[p("步骤 / 基本信息", "label"), p("填写内容", "label")]]
    rows.extend([[p(f'{r["step"]:02d}  {r["question"]}', "table"), p(r["answer"], "table")] for r in case["profile"]])
    t = Table(rows, colWidths=[172, CW - 172], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFBF8")]),
    ]))
    return t


def attachments(case):
    out = [p("本例上传文件", "subheading")]
    for r in case["uploads"]:
        out.extend([p(r["path"], "label"), p(r["action"], "small")])
    out.append(p("图片 OCR 替代附件", "subheading"))
    for r in case["alternatives"]:
        out.append(p(f'{r["path"]}\n{r["label"]}', "small"))
    return out


def question(r, compact=False):
    answer_style = "small" if compact else "body"
    out = [p(f'第 {r["step"]} 题   {r["question"]}', "question")]
    if r["choice_labels"]:
        out.append(p("先选：" + "；".join(r["choice_labels"]), "label"))
    else:
        out.append(p("直接填写 / 语音输入", "label"))
    out.append(p(r["text"], answer_style))
    if r.get("note"):
        out.append(p("操作提示：" + r["note"], "small"))
    out.append(Spacer(1, 8 if compact else 13))
    return KeepTogether(out)


def followup(case):
    out = []
    for i, r in enumerate(case["followup_bank"], 1):
        out.extend([p(f'{i:02d}  {r["topic"]}', "subheading"), p(r["text"])])
    return out


def bp_question(r):
    lines = r["text"].splitlines()
    out = [p(f'第 {r["step"]} 题   {r["question"]}', "question"), p("填写：先复制测量说明，再复制全部 14 行及最后的统计说明。", "label"), p(lines[0], "small")]
    rows = [[p("日期与时间", "label"), p("血压 / mmHg", "label"), p("脉搏 / 次每分", "label")]]
    for line in lines[1:-1]:
        when, rest = line.split("：", 1)
        bp, pulse = rest.split("，脉搏")
        rows.append([p(when, "tableSmall"), p(bp, "tableSmall"), p(pulse, "tableSmall")])
    t = Table(rows, colWidths=[240, 135, CW - 375], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F9F4")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    out.extend([t, Spacer(1, 7), p(lines[-1], "small"), p("操作提示：" + r["note"], "small")])
    return out


PAGE_TITLES = [
    "开始前：账号、语言与语音", "TC01：健康档案与上传文件", "TC01：健康信息 1-4",
    "TC01：健康信息 5-8", "TC01：健康信息 9-11 与预期", "TC01：AI 追问参考答案",
    "TC02：健康档案与上传文件", "TC02：健康信息 1-4 与血压记录", "TC02：健康信息 5-9",
    "TC02：AI 追问参考答案", "附件核对与 TC02 预期", "审核、分享与最终核对"
]


def decorate(c, doc):
    n = doc.page
    c.setFillColor(TEAL)
    c.rect(0, H - 7, W, 7, fill=1, stroke=0)
    c.setFillColor(CREAM)
    c.roundRect(M, H - 56, CW, 32, 6, fill=1, stroke=0)
    c.setFont("ManualLatinBold", 8.8)
    c.setFillColor(AMBER)
    c.drawString(M + 10, H - 38, "SYNTHETIC TEST DATA")
    c.setFont("ManualChinese", 8.5)
    c.drawString(M + 163, H - 38, "虚构测试数据 / 非真实医疗文件")
    c.setStrokeColor(LINE)
    c.line(M, 49, W - M, 49)
    c.setFillColor(MUTED)
    c.setFont("ManualChinese", 7.2)
    c.drawString(M, 33, "PreConsult 测试材料包 · 2026-10-21 · 未代为注册、上传或分享")
    c.drawRightString(W - M, 33, f"{n:02d} / 12")
    c.setTitle("PreConsult 两套典型测试病例：逐步填写手册")
    c.setAuthor("Synthetic application test fixture")


def main():
    a, b = DATA["cases"]
    pages = []
    pages.append([
        *title("PRECONSULT  /  TEST CASE MANUAL", "两套病例，逐步照填", "患者端、附件提取、AI Wizard 与医生分享的手动验收材料"),
        note(DATA["notice"] + " " + DATA["execution_status"]), Spacer(1, 9),
        p("先完成这 6 步", "subheading"), *numbered(DATA["setup"]),
        p("语音交互专项检查", "subheading"), *numbered(DATA["voice_check"], style="small"),
        p("阅读路线", "subheading"),
        p("TC01 双膝疼痛：第 2-6 页；TC02 高血压复查：第 7-10 页；附件核对与通用验收：第 11-12 页。每例独立患者账号，按顺序完成档案、症状问题、附件与追问。", "small"),
    ])
    pages.append([
        *title("TC01  /  WF-01 · 腿痛", a["title"], a["summary"]),
        p("患者姓名：" + a["name"] + "。先保存以下 7 项健康背景。", "body"),
        profile(a), Spacer(1, 7), *attachments(a),
    ])
    pages.append([
        *title("TC01  /  健康信息 WIZARD", "第 1-4 题", "有选项时先点选，再填写正文；每题完成后点“继续”。"),
        *[question(r) for r in a["steps"][:4]],
        note("身体部位可多选。右膝和左膝都选择“正面”，不是以照片观看者的左右来判断。"),
    ])
    pages.append([
        *title("TC01  /  健康信息 WIZARD", "第 5-8 题", "保留日常影响与本次就诊目标；不必重复已存的基本病史。"),
        *[question(r) for r in a["steps"][4:8]],
    ])
    pages.append([
        *title("TC01  /  健康信息 WIZARD", "第 9-11 题与核对", "药物与反应要保留时间、剂量及不确定性。"),
        *[question(r, compact=True) for r in a["steps"][8:]],
        p("TC01 关键预期结果", "subheading"), *numbered(a["expected"], style="small"),
    ])
    pages.append([
        *title("TC01  /  AI 分析与追问", "5 组事实参考答案", "这些是答案库，不是固定会出现的 5 道题。根据实际追问选择对应事实。"),
        note("每题一个 Wizard 步骤。建议选项吻合才点选；否则自定义。已知信息不要重复捏造，未知值用“我不知道”或跳过。"),
        *followup(a),
        p("第二次就诊：记忆与历史回答检查", "subheading"), p(a["repeat_check"]),
    ])
    pages.append([
        *title("TC02  /  WF-24 · 已确诊高血压复查", b["title"], b["summary"]),
        p("患者姓名：" + b["name"] + "。使用与 TC01 不同的测试账号。", "body"),
        profile(b), Spacer(1, 7), *attachments(b),
    ])
    pages.append([
        *title("TC02  /  健康信息 WIZARD", "第 1-4 题与读数", "家庭血压为历史记录；不得把旧日期替换成今天。"),
        *[question(r, compact=True) for r in b["steps"][:3]],
        *bp_question(b["steps"][3]),
    ])
    pages.append([
        *title("TC02  /  健康信息 WIZARD", "第 5-9 题", "检查单位、用药时间与漏服次数；本次为预约复查，没有新症状。"),
        *[question(r, compact=True) for r in b["steps"][4:]],
    ])
    pages.append([
        *title("TC02  /  AI 分析与追问", "5 组事实参考答案", "AI 可以少问或不问；只按病例已提供的信息回答。"),
        *followup(b),
        p("第二次就诊：旧读数不可变成新数据", "subheading"), p(b["repeat_check"]),
        note("如果追问个人血压目标值或医疗人员姓名，本材料没有提供，选择“我不知道”；不要自行推定。"),
    ])
    pages.append([
        *title("附件与结果核对", "数值、来源与交互", "重点核对多个附件的日期、左右侧和单位；不要只看摘要是否流畅。"),
        p("上传附件：共同操作", "subheading"), *numbered(DATA["attachment_steps"], style="small"),
        p("AI Wizard：共同交互检查", "subheading"), *numbered(DATA["followup_instructions"], style="small"),
        p("TC02 关键预期结果", "subheading"), *numbered(b["expected"], style="small"),
    ])
    pages.append([
        *title("最终人工验收", "审核、分享与撤回", "分享仅由你在核对后手动执行；生成本材料没有改变任何患者或医生记录。"),
        *numbered(DATA["review_and_share"]),
        p("材料范围与验证边界", "subheading"), *numbered(DATA["quality_checks"], style="small"),
        p("随包数据与来源", "subheading"),
        p("testcases.json：所有逐题答案、选项、验收要点的结构化版本。\nreport-data.json：检查表与 14 次血压的结构化原始值。\nfield-map.json：当前工作流字段与控件映射。\nsource/image-prompts.json：两张测试图片的生成提示。", "small"),
        note("测试执行结果请另行记录。本文提供的是可复现的输入和预期，不表示实际模型、上传服务或医生分享流程已跑通。"),
    ])
    doc = SimpleDocTemplate(str(DEST), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=76, bottomMargin=67, pageCompression=1)
    story = []
    for i, section in enumerate(pages):
        if i:
            story.append(PageBreak())
        story.extend(section)
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    print(json.dumps({"path": str(DEST), "planned_pages": len(pages), "bytes": DEST.stat().st_size}))


if __name__ == "__main__":
    main()
