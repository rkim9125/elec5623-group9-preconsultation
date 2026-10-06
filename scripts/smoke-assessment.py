"""Explicit billable OpenAI assessment smoke test using synthetic data only.

Uses the existing synthetic v2 fixture or asks that it be generated first. Does
not open the application database, authenticate, send email or use patient files.
Creates a synthetic image and a two-page PDF, then exports the complete report.
"""
from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local/assessment-smoke'
UPLOADS = OUT / 'uploads'
UPLOADS.mkdir(parents=True, exist_ok=True, mode=0o700)
os.environ['UPLOAD_DIR'] = str(UPLOADS)
sys.path.insert(0, str(ROOT / 'backend'))

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from app.product import assessment
from app.product.config import get_settings
from app.product.database import utc_now
from app.product.report_pdf import create_pdf


def run():
    fixture = ROOT / '.local/v2-live-smoke.json'
    if not fixture.exists():
        raise RuntimeError('First create the synthetic fixture with scripts/smoke-product-v2.py.')
    session = deepcopy(json.loads(fixture.read_text()))
    if session.get('patient_id') != 'synthetic-v2-smoke':
        raise RuntimeError('This test accepts only the synthetic v2 fixture.')
    session.update(id='assessment-live-smoke', patient_id='synthetic-assessment-smoke',
                   patient_email='synthetic@example.test', patient_name='Alex Morgan (synthetic)',
                   title='Synthetic multi-concern consultation', model=get_settings().openai_model,
                   status='review', doctor_email=None, shared_at=None)
    session.pop('revision', None)
    session.pop('ai_report', None)
    session['summary'].pop('approved_at', None)
    session['summary'].pop('approved_version', None)
    photo = Image.new('RGB', (1400, 460), '#f7faf7')
    draw = ImageDraw.Draw(photo)
    font = ImageFont.load_default(size=28)
    for index, line in enumerate([
        'SYNTHETIC WALKING DIARY - TEST DATA',
        'Left calf ache after long walks for three weeks.',
        'It settles after resting; I take breaks during longer walks.',
        'This is a patient diary, not a clinical examination.',
    ]):
        draw.text((45, 45 + 78 * index), line, fill='#20473e', font=font)
    photo_path = UPLOADS / 'walking-diary.png'
    photo.save(photo_path)
    pdf_path = UPLOADS / 'sleep-diary.pdf'
    canvas = Canvas(str(pdf_path))
    for number, text in enumerate([
        'Difficulty falling asleep on around three nights per week for two months.',
        'I feel tired during early meetings. Usual bedtime 11 pm, wake time 7 am.',
    ], 1):
        canvas.setFont('Helvetica-Bold', 16)
        canvas.drawString(45, 785, f'SYNTHETIC SLEEP DIARY - PAGE {number}')
        canvas.setFont('Helvetica', 11)
        canvas.drawString(45, 730, text)
        canvas.drawString(45, 695, 'Patient-reported test data. No examination or clinical results.')
        canvas.showPage()
    canvas.save()
    session['attachments'] = []
    for aid, path, mime in [('synthetic-image', photo_path, 'image/png'), ('synthetic-pdf', pdf_path, 'application/pdf')]:
        path.chmod(0o600)
        session['attachments'].append(dict(id=aid, filename=path.name, media_type=mime,
            storage_path=str(path), size_bytes=path.stat().st_size, created_at=utc_now()))
    context, files, fingerprint = assessment.assessment_input(session)
    assert len(files) == 2 and len(context['concerns']) == 3
    started = monotonic()
    raw = assessment.get_assessment_provider().generate(model=session['model'], context=context, files=files)
    validated = assessment._validate(raw, context)
    validated.update(status='ready', model=session['model'], generated_at=utc_now(),
                     input_fingerprint=fingerprint, summary_version=session['summary']['version'],
                     sources=context['sources'])
    session['ai_report'] = validated
    assert assessment.public_report(session)
    assert {item['attachment_id'] for item in validated['attachment_reviews']} == {'synthetic-image', 'synthetic-pdf'}
    complete_pdf = create_pdf(session)
    final_path = OUT / 'complete-report.pdf'
    final_path.write_bytes(complete_pdf)
    final_path.chmod(0o600)
    pdf = PdfReader(BytesIO(complete_pdf))
    assert 'SYNTHETIC SLEEP DIARY - PAGE 1' in pdf.pages[-2].extract_text()
    assert 'SYNTHETIC SLEEP DIARY - PAGE 2' in pdf.pages[-1].extract_text()
    assert sum(len(page.images) for page in pdf.pages) >= 1
    assert 'AI diagnosis & consultation guidance' in ''.join(page.extract_text() for page in pdf.pages[:3])
    record = OUT / 'session.json'
    record.write_text(json.dumps(session, ensure_ascii=False, indent=2))
    record.chmod(0o600)
    result = dict(passed=True, synthetic_only=True, model=session['model'], concerns=len(context['concerns']),
                  attachments_processed=len(validated['attachment_reviews']),
                  diagnostic_possibilities=len(validated['possible_diagnoses']),
                  next_steps=len(validated['next_steps']), pdf_pages=len(pdf.pages),
                  full_original_pdf_pages_preserved=True, image_in_pdf=True,
                  duration_seconds=round(monotonic() - started, 1))
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    run()
