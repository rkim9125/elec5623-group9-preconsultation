"""Generate wholly synthetic upload fixtures. Contains no real patient records."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "case01", ROOT / "case02"):
    directory.mkdir(parents=True, exist_ok=True)

FONT_ROOT = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("ReportRegular", str(FONT_ROOT / "Arial.ttf")))
pdfmetrics.registerFont(TTFont("ReportBold", str(FONT_ROOT / "Arial Bold.ttf")))
pdfmetrics.registerFont(TTFont("ReportChinese", str(FONT_ROOT / "Arial Unicode.ttf")))
pdfmetrics.registerFontFamily("ReportRegular", normal="ReportRegular", bold="ReportBold")

W, H = A4
LEFT, RIGHT = 42, W - 42
CONTENT = RIGHT - LEFT
INK = colors.HexColor("#183D36")
TEAL = colors.HexColor("#24776A")
MUTED = colors.HexColor("#566B64")
LINE = colors.HexColor("#D7E2DC")
PALE = colors.HexColor("#EEF4EE")
CREAM = colors.HexColor("#FFFBF2")
AMBER = colors.HexColor("#765A1F")

READINGS_RAW = [
    (138, 86, 70), (142, 88, 72), (140, 87, 69), (144, 89, 73),
    (141, 88, 71), (145, 90, 75), (136, 84, 68), (139, 86, 70),
    (143, 89, 72), (140, 87, 71), (137, 85, 69), (138, 86, 70),
    (139, 87, 70), (141, 88, 72),
]
READINGS = [
    {"date": (date(2026, 10, 14) + timedelta(days=i // 2)).isoformat(),
     "time": "07:30" if i % 2 == 0 else "19:30", "systolic_mmhg": s,
     "diastolic_mmhg": d, "pulse_bpm": p}
    for i, (s, d, p) in enumerate(READINGS_RAW)
]
AVERAGE = {
    "systolic_mmhg": round(mean(x[0] for x in READINGS_RAW), 1),
    "diastolic_mmhg": round(mean(x[1] for x in READINGS_RAW), 1),
    "pulse_bpm": round(mean(x[2] for x in READINGS_RAW), 1),
}
DATA = {
    "notice": "SYNTHETIC TEST DATA / 虚构测试数据 / 非真实医疗文件",
    "purpose": "Application testing only. No real patient or clinician. No diagnostic interpretation or treatment advice.",
    "case01": {
        "id": "TC01", "patient_name": "Alex Lin (TEST)", "date_of_birth": "1988-04-12", "sex": "Male",
        "examination_date": "2026-10-20", "onset_date": "2026-10-14",
        "reported_symptoms": "Bilateral anterior knee ache after a long walk; discomfort on stairs; able to walk.",
        "photo_date": "2026-10-19", "photo_description": "Small, faint bruise on the right anterior knee.",
        "vitals": {"blood_pressure_mmhg": "122/78", "pulse_bpm": 72, "temperature_c": 36.7, "height_cm": 178, "weight_kg": 74},
        "examination": {
            "right_knee": "Mild localized anterior tenderness; small fading bruise approximately 3 x 2 cm; motion 0-125 degrees.",
            "left_knee": "Mild anterior tenderness; no bruise; motion 0-130 degrees.",
            "shared_findings": "No visible effusion. Able to walk; discomfort on stairs."
        },
        "medications": [
            {"name": "Vitamin C", "amount": "1 tablet per day", "strength": "Unknown"},
            {"name": "Paracetamol", "amount": "500 mg, one dose on 2026-10-19", "status": "Historical single dose; not daily"}
        ],
        "allergies": "Rash after amoxicillin in 2015, patient reported and unconfirmed; no formal allergy testing.",
        "investigations": "No X-ray or MRI in this test case. No laboratory tests ordered or available.",
        "assessment": "Knee discomfort, patient reported; diagnosis not established in this synthetic record."
    },
    "case02": {
        "id": "TC02", "patient_name": "Maya Chen (TEST)", "date_of_birth": "1971-09-08", "sex": "Female",
        "review_date": "2026-10-20", "visit_reason": "Booked review; no new symptoms reported.",
        "reported_history": ["Hypertension, patient-reported prior diagnosis in 2021", "Hyperlipidemia, patient-reported prior diagnosis in 2024"],
        "medications": [
            {"name": "Amlodipine", "amount": "5 mg daily at 07:30", "adherence": "Missed only the 2026-10-16 dose"},
            {"name": "Atorvastatin", "amount": "10 mg nightly"}
        ],
        "allergies": "No known drug or food allergies, patient reported.",
        "last_clinic_review": {"date": "2026-10-08", "blood_pressure_mmhg": "146/90", "pulse_bpm": 74},
        "blood_collection": {"date": "2026-10-18", "time": "08:10", "fasting": True,
            "results": [
                {"test": "Sodium", "value": 140, "unit": "mmol/L"},
                {"test": "Potassium", "value": 4.2, "unit": "mmol/L"},
                {"test": "Creatinine", "value": 74, "unit": "umol/L"},
                {"test": "eGFR", "value": 82, "unit": "mL/min/1.73 m2"},
                {"test": "Fasting glucose", "value": 5.4, "unit": "mmol/L"},
                {"test": "Total cholesterol", "value": 5.2, "unit": "mmol/L"},
                {"test": "LDL cholesterol", "value": 3.0, "unit": "mmol/L"},
                {"test": "HDL cholesterol", "value": 1.4, "unit": "mmol/L"},
                {"test": "Triglycerides", "value": 1.7, "unit": "mmol/L"},
            ]},
        "home_monitoring": {"device": "Fictional upper-arm monitor", "arm": "Left", "preparation": "Seated, rested 5 minutes", "readings_per_session": 1,
            "readings": READINGS, "arithmetic_average": AVERAGE,
            "interpretation": "Descriptive arithmetic average of 14 synthetic readings only; not a diagnosis."}
    }
}


def text(c, x, y, value, size=9.5, font="ReportRegular", color=INK):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, str(value))


def para(c, value, x, top, width=CONTENT, size=9.5, leading=14, color=INK):
    style = ParagraphStyle("p", fontName="ReportRegular", fontSize=size, leading=leading, textColor=color, alignment=TA_LEFT)
    p = Paragraph(value, style)
    _, h = p.wrap(width, H)
    p.drawOn(c, x, top - h)
    return top - h


def pill(c, x, y, width, label, value):
    c.setFillColor(PALE)
    c.roundRect(x, y - 50, width, 50, 8, stroke=0, fill=1)
    text(c, x + 12, y - 16, label.upper(), 7.5, "ReportBold", MUTED)
    text(c, x + 12, y - 37, value, 14, "ReportBold")


def page(c, case_id, patient, dob, sex, heading, subtitle, document_date, page_number, pages):
    c.setFillColor(TEAL)
    c.rect(0, H - 8, W, 8, stroke=0, fill=1)
    c.setFillColor(CREAM)
    c.roundRect(LEFT, H - 68, CONTENT, 44, 7, stroke=0, fill=1)
    text(c, LEFT + 13, H - 41, "SYNTHETIC TEST DATA", 11, "ReportBold", AMBER)
    text(c, LEFT + 13, H - 57, "虚构测试数据 / 非真实医疗文件", 9, "ReportChinese", AMBER)
    text(c, RIGHT - 53, H - 47, case_id, 16, "ReportBold", AMBER)
    text(c, LEFT, H - 102, heading, 24, "ReportBold")
    text(c, LEFT, H - 123, subtitle, 10, "ReportRegular", MUTED)
    c.setStrokeColor(LINE)
    c.line(LEFT, H - 140, RIGHT, H - 140)
    text(c, LEFT, H - 161, "TEST SUBJECT", 7.5, "ReportBold", MUTED)
    text(c, LEFT, H - 180, patient, 13, "ReportBold")
    text(c, LEFT + 210, H - 161, "DATE OF BIRTH / SEX", 7.5, "ReportBold", MUTED)
    text(c, LEFT + 210, H - 180, f"{dob} / {sex}", 10)
    text(c, LEFT + 379, H - 161, "RECORD DATE", 7.5, "ReportBold", MUTED)
    text(c, LEFT + 379, H - 180, document_date, 10)
    c.line(LEFT, 55, RIGHT, 55)
    text(c, LEFT, 39, "Application testing only. No real patient, clinician or issuing institution.", 7.6, color=MUTED)
    text(c, LEFT, 27, "No diagnostic interpretation or treatment recommendations are supplied.", 7.6, color=MUTED)
    c.setFont("ReportBold", 8)
    c.drawRightString(RIGHT, 33, f"{page_number} / {pages}")


def section(c, title, y):
    c.setFillColor(TEAL)
    c.roundRect(LEFT, y - 12, 3, 15, 1.5, stroke=0, fill=1)
    text(c, LEFT + 11, y - 9, title, 11.5, "ReportBold")
    return y - 24


def row_table(c, headers, rows, widths, top, row_h=25, size=9.3):
    c.setFillColor(PALE)
    c.roundRect(LEFT, top - 27, CONTENT, 27, 5, stroke=0, fill=1)
    x = LEFT
    for h, width in zip(headers, widths):
        text(c, x + 11, top - 18, h, 8.2, "ReportBold", MUTED)
        x += width
    y = top - 27
    for i, row in enumerate(rows):
        if i % 2 == 1:
            c.setFillColor(colors.HexColor("#F8FAF7"))
            c.rect(LEFT, y - row_h, CONTENT, row_h, stroke=0, fill=1)
        x = LEFT
        for value, width in zip(row, widths):
            text(c, x + 11, y - (row_h + size) / 2 + 2, value, size)
            x += width
        c.setStrokeColor(LINE)
        c.setLineWidth(0.35)
        c.line(LEFT, y - row_h, RIGHT, y - row_h)
        y -= row_h
    return y


def case01():
    path = ROOT / "case01" / "medical-exam.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("TC01 | Synthetic knee examination record")
    c.setAuthor("Synthetic application test fixture")
    page(c, "TC01", "Alex Lin (TEST)", "1988-04-12", "Male", "Knee examination record", "Sample attachment / 膝部检查记录".split(" / ")[0], "2026-10-20", 1, 1)
    y = H - 206
    specs = [("BLOOD PRESSURE", "122/78 mmHg"), ("PULSE", "72 bpm"), ("TEMPERATURE", "36.7 C")]
    width = (CONTENT - 20) / 3
    for i, (label, value) in enumerate(specs):
        pill(c, LEFT + i * (width + 10), y, width, label, value)
    text(c, LEFT + 1, y - 68, "Height 178 cm   |   Weight 74 kg", 9, color=MUTED)
    y = section(c, "Reported history", y - 89)
    y = para(c, "Bilateral anterior knee ache after a long walk, beginning <b>2026-10-14</b>. Able to walk, with discomfort on stairs. The test photo dated <b>2026-10-19</b> shows a small, faint bruise on the right anterior knee.", LEFT, y)
    y = section(c, "Recorded examination findings", y - 21)
    y = row_table(c, ["LOCATION", "FINDING", "MOTION"], [
        ("Right knee", "Mild anterior tenderness", "0-125 degrees"),
        ("", "Fading bruise, approx. 3 x 2 cm", ""),
        ("Left knee", "Mild anterior tenderness; no bruise", "0-130 degrees")
    ], [90, 288, CONTENT - 378], y, row_h=24, size=9)
    y = para(c, "<b>Shared finding:</b> No visible effusion.", LEFT, y - 12)
    y = section(c, "Medication and allergy history", y - 19)
    y = para(c, "<b>Vitamin C:</b> 1 tablet daily; tablet strength unknown.<br/><b>Paracetamol:</b> 500 mg once on 2026-10-19; a historical single dose, not daily use.<br/><b>Amoxicillin reaction:</b> Rash in 2015, patient reported and unconfirmed. No formal allergy testing.", LEFT, y)
    y = section(c, "Investigations and assessment", y - 18)
    y = para(c, "No X-ray or MRI in this test case. No laboratory tests ordered or available.<br/><b>Assessment:</b> Knee discomfort, patient reported; diagnosis not established in this synthetic record.", LEFT, y)
    assert y > 74, y
    c.showPage()
    c.save()
    return path


def case02():
    path = ROOT / "case02" / "checkup-and-bp-log.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("TC02 | Synthetic checkup and home blood pressure log")
    c.setAuthor("Synthetic application test fixture")
    page(c, "TC02", "Maya Chen (TEST)", "1971-09-08", "Female", "Checkup & blood results", "Sample attachment - booked review, no new symptoms reported", "2026-10-20", 1, 2)
    y = section(c, "Patient-reported background", H - 207)
    y = para(c, "Prior hypertension diagnosis in <b>2021</b> and hyperlipidemia diagnosis in <b>2024</b>.<br/><b>Allergies:</b> No known drug or food allergies, patient reported.", LEFT, y)
    y = section(c, "Current medicines", y - 17)
    y = para(c, "<b>Amlodipine:</b> 5 mg daily at 07:30. Missed only the 2026-10-16 dose.<br/><b>Atorvastatin:</b> 10 mg nightly.", LEFT, y)
    y = section(c, "Last documented clinic review", y - 17)
    y = para(c, "<b>2026-10-08:</b> Blood pressure 146/90 mmHg; pulse 74 bpm.", LEFT, y)
    y = section(c, "Synthetic blood test results", y - 20)
    y = para(c, "Collection: <b>2026-10-18 at 08:10</b>   |   Fasting sample", LEFT, y, size=9, color=MUTED)
    values = DATA["case02"]["blood_collection"]["results"]
    rows = [(r["test"], f'{r["value"]:.1f}' if isinstance(r["value"], float) else str(r["value"]), r["unit"]) for r in values]
    y = row_table(c, ["TEST", "VALUE", "UNIT"], rows, [238, 89, CONTENT - 327], y - 12, row_h=24, size=9.3)
    y = para(c, "No reference ranges, diagnostic interpretation or clinical flags are supplied. These values are fictional inputs for upload and information-extraction testing.", LEFT, y - 13, size=8.7, leading=12.5, color=MUTED)
    assert y > 74, y
    c.showPage()
    page(c, "TC02", "Maya Chen (TEST)", "1971-09-08", "Female", "Home blood pressure log", "Sample attachment - 14 documented readings over 7 days", "2026-10-20", 2, 2)
    y = H - 207
    pill(c, LEFT, y, (CONTENT - 10) * 0.61, "Mean blood pressure", f'{AVERAGE["systolic_mmhg"]:.1f} / {AVERAGE["diastolic_mmhg"]:.1f} mmHg')
    pill(c, LEFT + (CONTENT - 10) * 0.61 + 10, y, (CONTENT - 10) * 0.39, "Mean pulse", f'{AVERAGE["pulse_bpm"]:.1f} bpm')
    y = para(c, "Arithmetic average of the 14 synthetic readings below. Descriptive only; not a diagnosis.", LEFT, y - 61, size=8.4, leading=12, color=MUTED)
    y = para(c, "<b>Recording context:</b> Fictional upper-arm monitor; left arm; seated after 5 minutes of rest. One documented reading per session; no repeat readings supplied.", LEFT, y - 11, size=9, leading=13)
    rows = [(r["date"], r["time"], str(r["systolic_mmhg"]), str(r["diastolic_mmhg"]), str(r["pulse_bpm"])) for r in READINGS]
    y = row_table(c, ["DATE", "TIME", "SYS (mmHg)", "DIA (mmHg)", "PULSE (bpm)"], rows, [122, 80, 103, 103, CONTENT - 408], y - 17, row_h=23, size=9)
    y = para(c, "<b>Medication note:</b> The 2026-10-16 amlodipine dose was missed. No cause-and-effect interpretation is attached to these readings.<br/><b>Image cross-check:</b> The synthetic monitor image represents the final row: 2026-10-20 at 19:30, 141/88 mmHg, pulse 72 bpm.", LEFT, y - 15, size=8.7, leading=12.5, color=MUTED)
    assert y > 74, y
    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    data_path = ROOT / "report-data.json"
    data_path.write_text(json.dumps(DATA, ensure_ascii=False, indent=2) + "\n")
    paths = [case01(), case02()]
    print(json.dumps({"outputs": [str(p) for p in paths], "average": AVERAGE}, indent=2))
