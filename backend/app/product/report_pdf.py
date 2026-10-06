"""Private, complete consultation PDFs with every original supported attachment.

Rendering is deliberately local: a PDF download never calls an AI provider or
changes patient approval. Only current, shareable sources enter the document.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .auth import require_user
from .intelligence import current_sources
from .media import attachment_path, authorized, validate_document

router = APIRouter(tags=['Consultation reports'])
_INK = colors.HexColor('#24473e')
_TEAL = colors.HexColor('#176f64')
_MUTED = colors.HexColor('#63756f')
_LINE = colors.HexColor('#d9e5df')
_PALE = colors.HexColor('#f0f6f1')
_NON_ASCII = re.compile(r'([^\x00-\x7f]+)')
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_MARGIN = 46
_WIDTH = _PAGE_WIDTH - 2 * _MARGIN
_DISCLAIMER = ('AI-generated preliminary assessment, not a confirmed diagnosis. '
               'A qualified clinician must verify the information, examine the patient where needed, '
               'and make diagnosis and treatment decisions. No clinician approval is implied by sharing this report.')

# Embed a Unicode subset when the host supplies one. Standard PDF CJK fonts are
# a fallback for other deployments; Western interface text uses Helvetica.
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
_UNICODE_FONT = None
for _font_path in (
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
    '/usr/share/fonts/truetype/arphic/uming.ttc',
):
    if Path(_font_path).is_file():
        try:
            pdfmetrics.registerFont(TTFont('PreConsultUnicode', _font_path, subfontIndex=0))
            _UNICODE_FONT = 'PreConsultUnicode'
            break
        except Exception:
            continue


def _markup(value: object) -> str:
    """User and model text is always data, never ReportLab markup."""
    text = _CONTROL.sub('', str(value if value is not None else ''))
    pieces = []
    for part in _NON_ASCII.split(text):
        encoded = escape(part).replace('\n', '<br/>')
        if _NON_ASCII.fullmatch(part or '') and (_UNICODE_FONT or re.search(r'[\u2e80-\u9fff\uac00-\ud7ff\uf900-\ufaff\uff00-\uffef]', part)):
            font = _UNICODE_FONT or ('HYSMyeongJo-Medium' if re.search(r'[\uac00-\ud7ff]', part) else 'STSong-Light')
            encoded = f'<font name="{font}">{encoded}</font>'
        pieces.append(encoded)
    return ''.join(pieces)


_STYLES = {
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=15, textColor=_INK,
                           spaceAfter=7, splitLongWords=True, alignment=TA_LEFT),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=12, textColor=_MUTED,
                            spaceAfter=5, splitLongWords=True),
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=27, leading=32, textColor=_INK,
                            spaceAfter=13, keepWithNext=True),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=17, leading=22,
                              textColor=_TEAL, spaceBefore=19, spaceAfter=10, keepWithNext=True),
    'subheading': ParagraphStyle('subheading', fontName='Helvetica-Bold', fontSize=11, leading=16,
                                 textColor=_INK, spaceBefore=10, spaceAfter=6, keepWithNext=True),
}


def _p(text: object, style: str = 'body') -> Paragraph:
    return Paragraph(_markup(text), _STYLES[style])


def _footer(pdf, document):
    pdf.saveState()
    pdf.setStrokeColor(_LINE)
    pdf.line(_MARGIN, 37, _PAGE_WIDTH - _MARGIN, 37)
    pdf.setFont('Helvetica', 8)
    pdf.setFillColor(_MUTED)
    pdf.drawString(_MARGIN, 24, 'PreConsult  |  Private health information')
    pdf.drawRightString(_PAGE_WIDTH - _MARGIN, 24, f'Report page {document.page}')
    pdf.restoreState()


def _paragraphs(text: object, style: str = 'body') -> list:
    # Split exceptionally long source values into independently flowing blocks.
    # This avoids an unsplittable Table or KeepTogether hiding original wording.
    value = str(text if text is not None else '')
    return [_p(value[i:i + 1800], style) for i in range(0, len(value), 1800)] or [_p('', style)]


def _reference_numbers(ids: list, source_numbers: dict) -> str:
    numbers = list(dict.fromkeys(source_numbers[s] for s in ids if s in source_numbers))
    return f" [Sources {', '.join(str(n) for n in numbers)}]" if numbers else ''


def _cited(story: list, entries: list, source_numbers: dict):
    for entry in entries or []:
        if isinstance(entry, dict):
            story.extend(_paragraphs(str(entry.get('text', '')) + _reference_numbers(entry.get('source_ids', []), source_numbers)))


def _assessment(story: list, report: dict | None, source_numbers: dict):
    story.append(_p('AI diagnosis & consultation guidance', 'heading'))
    if not report:
        story.append(_p('Not generated for this version. Open this consultation in PreConsult and generate an AI assessment to include it in a new PDF.'))
        return
    notice = Table([[_p('PRELIMINARY AI ASSESSMENT — CLINICIAN REVIEW REQUIRED', 'subheading')],
                    [_p(_DISCLAIMER, 'small')]], colWidths=[_WIDTH - 22])
    notice.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), _PALE), ('BOX', (0, 0), (-1, -1), .5, _LINE),
                               ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11),
                               ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story.extend([notice, Spacer(1, 9), _p(f"Model: {report.get('model', 'Unavailable')}  |  Generated: {report.get('generated_at', 'Unavailable')}  |  Summary version: {report.get('summary_version', 'Unavailable')}", 'small')])
    _cited(story, [report.get('overview', {})], source_numbers)
    story.append(_p('Possible diagnoses to discuss', 'subheading'))
    diagnoses = report.get('possible_diagnoses', [])
    if not diagnoses:
        story.append(_p('The available information does not support a useful diagnostic hypothesis.'))
    for item in diagnoses:
        story.append(_p(item.get('name', 'Possible cause'), 'subheading'))
        story.extend(_paragraphs(str(item.get('explanation', '')) + _reference_numbers(item.get('source_ids', []), source_numbers)))
        for value in item.get('supporting_evidence', []):
            story.extend(_paragraphs('Supporting information: ' + value))
        for value in item.get('uncertainties', []):
            story.extend(_paragraphs('Uncertainty / limitation: ' + value))
    guidance = report.get('care_guidance', {})
    story.append(_p('Consultation timing & care guidance', 'subheading'))
    story.append(_p(f"{str(guidance.get('urgency', 'uncertain')).capitalize()} — {guidance.get('timeframe', '')}"))
    story.extend(_paragraphs(str(guidance.get('reason', '')) + _reference_numbers(guidance.get('source_ids', []), source_numbers)))
    for title, key in [('Recommended next steps', 'next_steps'), ('Warning symptoms & when to seek help', 'red_flags'),
                       ('Information still needed', 'missing_information')]:
        story.append(_p(title, 'subheading'))
        _cited(story, report.get(key, []), source_numbers)
    if report.get('attachment_reviews'):
        story.append(_p('AI reading of attachments', 'subheading'))
        for item in report['attachment_reviews']:
            story.append(_p(f"{item.get('filename', 'Attachment')} — {item.get('status', 'limited')}", 'subheading'))
            story.extend(_paragraphs(str(item.get('findings', '')) + _reference_numbers(item.get('source_ids', []), source_numbers)))
            story.extend(_paragraphs('Limitations: ' + str(item.get('limitations', ''))))
    if report.get('limitations'):
        story.append(_p('Assessment limitations', 'subheading'))
        for value in report['limitations']:
            story.extend(_paragraphs(value))


def _main_document(intake: dict, report: dict | None, attachments: list[dict]) -> bytes:
    summary = intake['summary']
    synthesis = summary.get('synthesis') or {}
    # Use current, shareable values only; model text cannot invent source records.
    sources = current_sources(intake)
    source_ids = {source['id'] for source in sources}
    for source in (report or {}).get('sources', []):
        if source['id'] not in source_ids and source['id'].startswith('attachment_'):
            sources.append(source)
            source_ids.add(source['id'])
    source_numbers = {source['id']: index + 1 for index, source in enumerate(sources)}
    currently_shared = intake.get('status') == 'approved' and bool(summary.get('approved_at'))
    sharing_label = ('Patient-approved sharing' if currently_shared else
                     'Sharing withdrawn — patient copy' if intake.get('status') == 'withdrawn' else
                     'Patient draft — not yet approved for sharing')
    story = [_p('PRECONSULT  /  CONSULTATION REPORT', 'small'),
             _p(intake.get('title') or 'Your consultation report', 'title'),
             _p(f"Patient: {intake.get('patient_name') or intake.get('patient_email') or 'Patient'}", 'body'),
             _p(f"Prepared: {summary.get('generated_at', 'Not recorded')}  |  Version {summary.get('version', 1)}", 'small'),
             _p(sharing_label, 'small')]
    if currently_shared:
        story.append(_p('Shared with: ' + str(intake.get('doctor_email') or 'Authorised clinician'), 'small'))
    _assessment(story, report, source_numbers)
    story.append(_p('Patient-provided consultation summary', 'heading'))
    story.append(_p('Patient-reported facts and AI-assisted wording. Verify details with the patient; this section is not a diagnostic conclusion.', 'small'))
    if synthesis.get('status') == 'live':
        for heading, key in [('Patient overview', 'patient_overview'), ('Clinician brief', 'clinician_brief')]:
            if synthesis.get(key):
                story.append(_p(heading, 'subheading'))
                _cited(story, synthesis[key], source_numbers)
        for concern in synthesis.get('concern_summaries', []):
            story.append(_p(concern.get('title', 'Concern'), 'subheading'))
            story.extend(_paragraphs(str(concern.get('summary', '')) + _reference_numbers(concern.get('source_ids', []), source_numbers)))
        for heading, key in [('Appointment agenda', 'appointment_agenda'), ('Uncertainties in the summary', 'uncertainties')]:
            if synthesis.get(key):
                story.append(_p(heading, 'subheading'))
                _cited(story, synthesis[key], source_numbers)
    elif summary.get('sections'):
        for section in summary['sections']:
            story.append(_p(section.get('title', 'Patient information'), 'subheading'))
            for entry in section.get('entries', []):
                story.extend(_paragraphs(f"{entry.get('label', '')}: {entry.get('value', '')}"))
        for gap in summary.get('gaps', []):
            story.extend(_paragraphs(f"{gap.get('label', '')}: {gap.get('description', 'Not supplied')}"))
    else:
        story.extend(_paragraphs(summary.get('text', 'No summary text is available.')))
    story.append(_p('Current source information', 'heading'))
    story.append(_p('Original wording is retained below. Unknown, omitted and uncollected information is not a negative finding. Source numbers refer to this report only.', 'small'))
    concern_names = {concern['id']: concern.get('title', 'Concern') for concern in intake.get('concerns', [])}
    status_names = {'FILLED': 'Reported', 'UNCERTAIN': 'Unknown or uncertain', 'MISSING': 'Not collected', 'SKIPPED': 'Patient chose not to include'}
    for index, source in enumerate(sources, 1):
        scope = concern_names.get(source.get('concern_id'))
        label = source.get('label', source.get('key', 'Source'))
        status = status_names.get(source.get('status'), 'Reported')
        story.append(_p(f"[{index}] {scope + ' / ' if scope else ''}{label} — {status}", 'subheading'))
        story.extend(_paragraphs(source.get('value') if source.get('value') is not None else 'No value supplied.'))
    story.append(_p('Attachment appendix', 'heading'))
    if not attachments:
        story.append(_p('No attachments were uploaded for this consultation.'))
    else:
        story.append(_p('Every uploaded attachment follows this report. Image pages show the complete image, scaled to fit without cropping. PDF pages retain their original page layout; interactive actions are disabled.', 'small'))
        for index, attachment in enumerate(attachments, 1):
            count = attachment['page_count']
            description = (f'{count} original PDF page' + ('s' if count != 1 else '') if attachment['media_type'] == 'application/pdf'
                           else f'All {count} image frames' if count > 1 else 'Complete uploaded image')
            story.append(_p(f"A{index}. {attachment['filename']} — {description}"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=_MARGIN, leftMargin=_MARGIN,
                            topMargin=45, bottomMargin=54, title='PreConsult consultation report',
                            author='PreConsult', pageCompression=1)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _attachment_page(attachment: dict, number: int, image_data: bytes | None = None, frame_index: int = 0) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    frame_label = f"  /  FRAME {frame_index + 1} OF {attachment['page_count']}" if image_data is not None and attachment['page_count'] > 1 else ''
    title = _p(f"ATTACHMENT A{number}" + frame_label, 'small')
    _, height = title.wrap(_WIDTH, 60)
    title.drawOn(pdf, _MARGIN, _PAGE_HEIGHT - 45 - height)
    name = _p(attachment['filename'], 'heading')
    _, height = name.wrap(_WIDTH, 150)
    top = _PAGE_HEIGHT - 70 - height
    name.drawOn(pdf, _MARGIN, top)
    if image_data is not None:
        # Convert orientation and transparency locally; preserve the entire image.
        with Image.open(BytesIO(image_data)) as original:
            original.seek(frame_index)
            image = ImageOps.exif_transpose(original)
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                rgb = Image.new('RGB', rgba.size, 'white')
                rgb.paste(rgba, mask=rgba.getchannel('A'))
                image = rgb
            elif image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            available_height = top - 90
            scale = min(_WIDTH / image.width, available_height / image.height)
            width, height = image.width * scale, image.height * scale
            x, y = (_PAGE_WIDTH - width) / 2, 65 + (available_height - height) / 2
            pdf.drawImage(ImageReader(image), x, y,
                          width=width, height=height, preserveAspectRatio=True)
            pdf.setStrokeColor(_LINE)
            pdf.setLineWidth(.5)
            pdf.rect(x, y, width, height, stroke=1, fill=0)
    else:
        content = _p(f"The following {attachment['page_count']} page(s) reproduce this uploaded PDF. Original page sizes and visible content are retained. Active links, scripts and embedded executable content are disabled.")
        _, height = content.wrap(_WIDTH, 300)
        content.drawOn(pdf, _MARGIN, top - 30 - height)
    pdf.setFont('Helvetica', 8)
    pdf.setFillColor(_MUTED)
    pdf.drawString(_MARGIN, 26, 'PreConsult  |  Patient-uploaded attachment  |  Private health information')
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


_ACTIVE_KEYS = {'/A', '/AA', '/JS', '/JavaScript', '/OpenAction', '/Launch', '/EmbeddedFiles', '/AF',
                '/XFA', '/RichMediaContent', '/RichMediaSettings', '/Movie', '/Sound', '/3DD', '/3DA', '/3DV'}
_PRINTABLE_ANNOTATIONS = {'/Text', '/FreeText', '/Line', '/Square', '/Circle', '/Polygon', '/PolyLine',
                          '/Highlight', '/Underline', '/Squiggly', '/StrikeOut', '/Stamp', '/Ink', '/Popup', '/Caret', '/Widget'}


def _remove_active_content(node, seen: set[int]):
    """Retain static annotations/appearance while removing executable actions."""
    try:
        node = node.get_object()
    except AttributeError:
        pass
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, DictionaryObject):
        for key in list(node):
            if str(key) in _ACTIVE_KEYS:
                del node[key]
        annotations = node.get('/Annots')
        if hasattr(annotations, 'get_object'):
            annotations = annotations.get_object()
        if annotations:
            node[NameObject('/Annots')] = ArrayObject([value for value in annotations if str(value.get_object().get('/Subtype')) in _PRINTABLE_ANNOTATIONS])
        for child in list(node.values()):
            _remove_active_content(child, seen)
    elif isinstance(node, (ArrayObject, list)):
        for child in node:
            _remove_active_content(child, seen)


def create_pdf(intake: dict) -> bytes:
    """Build all-or-nothing: a missing source never produces a partial PDF."""
    from .assessment import public_report

    attachments = []
    for attachment in intake.get('attachments', []):
        try:
            data = attachment_path(attachment).read_bytes()
            validate_document(data, attachment['media_type'])
            if attachment['media_type'] == 'application/pdf':
                count = len(PdfReader(BytesIO(data)).pages)
            else:
                with Image.open(BytesIO(data)) as image:
                    count = getattr(image, 'n_frames', 1)
        except Exception:
            raise HTTPException(409, 'A supporting attachment is missing or unreadable. Restore or remove it before downloading a complete report.') from None
        if count > 30:
            raise HTTPException(422, 'An animated attachment contains more than 30 frames. Replace it with a still image or a PDF of up to 30 pages before downloading the complete report.')
        attachments.append({**attachment, 'data': data, 'page_count': count})
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(_main_document(intake, public_report(intake), attachments))), import_outline=False)
    for number, attachment in enumerate(attachments, 1):
        is_pdf = attachment['media_type'] == 'application/pdf'
        if is_pdf:
            writer.append(PdfReader(BytesIO(_attachment_page(attachment, number))), import_outline=False)
            source = PdfReader(BytesIO(attachment['data']))
            for page in source.pages:
                copied = writer.add_page(page, excluded_keys=['/AA', '/A', '/OpenAction', '/Thumb'])
                _remove_active_content(copied, set())
        else:
            for frame_index in range(attachment['page_count']):
                writer.append(PdfReader(BytesIO(_attachment_page(attachment, number, attachment['data'], frame_index))), import_outline=False)
    writer.add_metadata({'/Title': 'PreConsult consultation report', '/Author': 'PreConsult',
                         '/Subject': 'Patient information and preliminary AI assessment with complete uploaded attachments'})
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@router.get('/intakes/{intake_id}/report.pdf')
def download_report(intake_id: str, user=Depends(require_user)):
    intake = authorized(intake_id, user)
    if not intake.get('summary') or intake.get('status') not in {'review', 'approved', 'withdrawn'}:
        raise HTTPException(409, 'Prepare a consultation summary before downloading the report.')
    if intake['summary'].get('needs_reconciliation'):
        raise HTTPException(409, 'Resolve pending corrections before downloading the report.')
    try:
        result = create_pdf(intake)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, 'The complete report could not be rendered. Check the uploaded files and try again.') from None
    # Access may be withdrawn while a large appendix is being rendered. A changed
    # revision also means this output is no longer the current complete report.
    current = authorized(intake_id, user)
    if current.get('revision') != intake.get('revision'):
        raise HTTPException(409, 'The consultation changed while the report was being prepared. Download it again.')
    return Response(result, media_type='application/pdf', headers={
        'Content-Disposition': 'attachment; filename="preconsult-consultation-report.pdf"',
        'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "sandbox; default-src 'none'",
    })
