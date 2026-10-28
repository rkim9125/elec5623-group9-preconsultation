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
from .locales import field_label, translate_text, workflow_title
from .report_copy import report_locale, report_text
from .summary_copy import summary_text

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

# Embed a Unicode subset when the host supplies one. Standard PDF CJK fonts are
# a fallback for other deployments; Western interface text uses Helvetica.
pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
pdfmetrics.registerFont(UnicodeCIDFont('HYSMyeongJo-Medium'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
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
            embedded_supports_text = (_UNICODE_FONT and all(ord(char) in pdfmetrics.getFont(_UNICODE_FONT).face.charWidths
                                                          for char in part if not char.isspace()))
            font = _UNICODE_FONT if embedded_supports_text else ('HYSMyeongJo-Medium' if re.search(r'[\uac00-\ud7ff]', part) else
                                     'HeiseiMin-W3' if re.search(r'[\u3040-\u30ff]', part) else 'STSong-Light')
            encoded = f'<font name="{font}">{encoded}</font>'
        pieces.append(encoded)
    return ''.join(pieces)


_STYLES = {
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=15, textColor=_INK,
                           spaceAfter=7, splitLongWords=True, alignment=TA_LEFT, wordWrap='CJK'),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=12, textColor=_MUTED,
                            spaceAfter=5, splitLongWords=True, wordWrap='CJK'),
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=27, leading=32, textColor=_INK,
                            spaceAfter=13, keepWithNext=True, wordWrap='CJK'),
    'heading': ParagraphStyle('heading', fontName='Helvetica-Bold', fontSize=17, leading=22,
                              textColor=_TEAL, spaceBefore=19, spaceAfter=10, keepWithNext=True, wordWrap='CJK'),
    'subheading': ParagraphStyle('subheading', fontName='Helvetica-Bold', fontSize=11, leading=16,
                                 textColor=_INK, spaceBefore=10, spaceAfter=6, keepWithNext=True, wordWrap='CJK'),
}


def _p(text: object, style: str = 'body') -> Paragraph:
    return Paragraph(_markup(text), _STYLES[style])


def _footer(pdf, document, locale='en'):
    pdf.saveState()
    pdf.setStrokeColor(_LINE)
    pdf.line(_MARGIN, 37, _PAGE_WIDTH - _MARGIN, 37)
    left = _p('PreConsult  |  ' + report_text(locale, 'private'), 'small')
    left.wrap(_WIDTH - 130, 20)
    left.drawOn(pdf, _MARGIN, 20)
    right = _p(report_text(locale, 'page', page=document.page), 'small')
    right.wrap(125, 20)
    right.drawOn(pdf, _PAGE_WIDTH - _MARGIN - 125, 20)
    pdf.restoreState()


def _paragraphs(text: object, style: str = 'body') -> list:
    # Split exceptionally long source values into independently flowing blocks.
    # This avoids an unsplittable Table or KeepTogether hiding original wording.
    value = str(text if text is not None else '')
    return [_p(value[i:i + 1800], style) for i in range(0, len(value), 1800)] or [_p('', style)]


def _summary_value(entry: dict, locale: str) -> str:
    value = str(entry.get('value', ''))
    if entry.get('key') == 'agenda_items':
        return '; '.join(translate_text(part.strip(), locale) for part in value.split(';'))
    # Choice serialization is authored UI copy. The optional free-text details
    # and original evidence section retain exactly what the patient entered.
    if value.startswith('Selected options:\n'):
        choices, separator, details = value.partition('\n\nAdditional details:\n')
        translated = '\n'.join('- ' + translate_text(line[2:], locale) if line.startswith('- ')
                               else summary_text(line, locale) for line in choices.split('\n'))
        return translated + ('\n\n' + summary_text('Additional details:', locale) + '\n' + details if separator else '')
    return value


def _reference_numbers(ids: list, source_numbers: dict, locale='en') -> str:
    numbers = list(dict.fromkeys(source_numbers[s] for s in ids if s in source_numbers))
    return ' [' + report_text(locale, 'sources', numbers=', '.join(str(n) for n in numbers)) + ']' if numbers else ''


def _cited(story: list, entries: list, source_numbers: dict, locale='en'):
    for entry in entries or []:
        if isinstance(entry, dict):
            story.extend(_paragraphs(str(entry.get('text', '')) + _reference_numbers(entry.get('source_ids', []), source_numbers, locale)))


def _assessment(story: list, report: dict | None, source_numbers: dict, locale='en'):
    t = lambda key, **values: report_text(locale, key, **values)
    story.append(_p(t('ai_heading'), 'heading'))
    if not report:
        story.append(_p(t('not_generated')))
        return
    notice = Table([[_p(t('preliminary'), 'subheading')],
                    [_p(t('pdf_disclaimer'), 'small')]], colWidths=[_WIDTH - 22])
    notice.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), _PALE), ('BOX', (0, 0), (-1, -1), .5, _LINE),
                               ('LEFTPADDING', (0, 0), (-1, -1), 11), ('RIGHTPADDING', (0, 0), (-1, -1), 11),
                               ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story.extend([notice, Spacer(1, 9), _p(t('metadata', model=report.get('model', t('unavailable')),
        generated=report.get('generated_at', t('unavailable')), version=report.get('summary_version', t('unavailable'))), 'small')])
    _cited(story, [report.get('overview', {})], source_numbers, locale)
    story.append(_p(t('diagnoses'), 'subheading'))
    diagnoses = report.get('possible_diagnoses', [])
    if not diagnoses:
        story.append(_p(t('no_diagnoses')))
    for item in diagnoses:
        story.append(_p(item.get('name', t('possible_cause')), 'subheading'))
        story.extend(_paragraphs(str(item.get('explanation', '')) + _reference_numbers(item.get('source_ids', []), source_numbers, locale)))
        for value in item.get('supporting_evidence', []):
            story.extend(_paragraphs(t('supporting') + value))
        for value in item.get('uncertainties', []):
            story.extend(_paragraphs(t('uncertainty') + value))
    guidance = report.get('care_guidance', {})
    story.append(_p(t('care'), 'subheading'))
    urgency = guidance.get('urgency', 'uncertain')
    story.append(_p(f"{t(urgency if urgency in {'emergency', 'urgent', 'routine', 'uncertain'} else 'uncertain')} - {guidance.get('timeframe', '')}"))
    story.extend(_paragraphs(str(guidance.get('reason', '')) + _reference_numbers(guidance.get('source_ids', []), source_numbers, locale)))
    for key in ['next_steps', 'red_flags', 'missing_information']:
        story.append(_p(t(key), 'subheading'))
        _cited(story, report.get(key, []), source_numbers, locale)
    if report.get('attachment_reviews'):
        story.append(_p(t('attachment_reviews'), 'subheading'))
        for item in report['attachment_reviews']:
            status = 'reviewed' if item.get('status') == 'reviewed' else 'limited'
            story.append(_p(f"{item.get('filename', t('attachment'))} - {t(status)}", 'subheading'))
            story.extend(_paragraphs(str(item.get('findings', '')) + _reference_numbers(item.get('source_ids', []), source_numbers, locale)))
            story.extend(_paragraphs(t('limitations_prefix') + str(item.get('limitations', ''))))
    if report.get('limitations'):
        story.append(_p(t('limitations'), 'subheading'))
        for value in report['limitations']:
            story.extend(_paragraphs(value))


def _main_document(intake: dict, report: dict | None, attachments: list[dict]) -> bytes:
    locale = report_locale(intake.get('locale'))
    t = lambda key, **values: report_text(locale, key, **values)
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
    sharing_label = t('approved' if currently_shared else 'withdrawn' if intake.get('status') == 'withdrawn' else 'draft')
    # Exact catalog translation only: a custom patient title stays their own text.
    title = translate_text(intake.get('title') or t('report_title'), locale)
    story = [_p(t('brand_heading'), 'small'), _p(title, 'title'),
             _p(f"{t('patient')}: {intake.get('patient_name') or intake.get('patient_email') or t('patient')}", 'body'),
             _p(t('prepared', date=summary.get('generated_at', t('not_recorded')), version=summary.get('version', 1)), 'small'),
             _p(sharing_label, 'small')]
    if currently_shared:
        story.append(_p(t('shared_with') + str(intake.get('doctor_email') or t('clinician')), 'small'))
    _assessment(story, report, source_numbers, locale)
    story.append(_p(t('summary'), 'heading'))
    story.append(_p(t('summary_note'), 'small'))
    if synthesis.get('status') == 'live':
        for key in ['patient_overview', 'clinician_brief']:
            if synthesis.get(key):
                story.append(_p(t(key), 'subheading'))
                _cited(story, synthesis[key], source_numbers, locale)
        for concern in synthesis.get('concern_summaries', []):
            story.append(_p(translate_text(concern.get('title', t('concern')), locale), 'subheading'))
            story.extend(_paragraphs(str(concern.get('summary', '')) + _reference_numbers(concern.get('source_ids', []), source_numbers, locale)))
        for key in ['appointment_agenda', 'uncertainties']:
            if synthesis.get(key):
                story.append(_p(t(key), 'subheading'))
                _cited(story, synthesis[key], source_numbers, locale)
    elif summary.get('sections'):
        for section in summary['sections']:
            story.append(_p(translate_text(section.get('title', t('patient_information')), locale), 'subheading'))
            for entry in section.get('entries', []):
                label = field_label(entry.get('key', ''), entry.get('label', ''), locale)
                story.extend(_paragraphs(f"{label}: {_summary_value(entry, locale)}"))
        for gap in summary.get('gaps', []):
            label = field_label(gap.get('key', ''), gap.get('label', ''), locale)
            description = translate_text(gap.get('description', t('not_supplied')), locale)
            story.extend(_paragraphs(f"{label}: {description}"))
    else:
        story.extend(_paragraphs(summary.get('text', t('no_summary'))))
    symptom_history = [row for row in summary.get('symptom_history', []) if row.get('applicable')]
    if symptom_history:
        story.append(_p(translate_text('Your symptom story', locale), 'heading'))
        story.append(_p(translate_text('Patient-reported details and remaining gaps. This is not a medical completeness or safety score.', locale), 'small'))
        status_labels = {'FILLED': 'Recorded', 'PARTIAL': 'Partly recorded', 'MISSING': 'Not yet recorded',
                         'UNCERTAIN': 'Not sure', 'SKIPPED': 'Chose not to answer', 'NOT_APPLICABLE': 'Not applicable'}
        concern_lookup = {concern['id']: concern for concern in intake.get('concerns', [])}
        for row in symptom_history:
            concern = concern_lookup.get(row.get('concern_id'), {})
            story.append(_p(workflow_title(concern.get('workflow_id'), concern.get('title', t('concern')), locale), 'subheading'))
            detail_rows = list(row.get('dimensions', []))
            if row.get('radiation', {}).get('applicable'):
                detail_rows.append(row['radiation'])
            for dimension in detail_rows:
                if dimension.get('status') == 'NOT_APPLICABLE':
                    continue
                label = translate_text(dimension.get('label', dimension['id']), locale)
                status = translate_text(status_labels.get(dimension.get('status'), 'Not yet recorded'), locale)
                story.append(_p(f'{label} — {status}', 'small'))
                for entry in dimension.get('values', []):
                    if entry.get('status') in {'FILLED', 'UNCERTAIN'} and entry.get('value'):
                        # Original patient wording remains attributable and editable;
                        # headings and state labels are authored translations.
                        entry_label = field_label(entry.get('key', ''), entry.get('key', '').replace('_', ' ').capitalize(), locale)
                        uncertainty = translate_text('Not sure', locale) + ': ' if entry['status'] == 'UNCERTAIN' else ''
                        story.extend(_paragraphs(f"{entry_label}: {uncertainty}{entry['value']}"))
    story.append(_p(t('source_heading'), 'heading'))
    story.append(_p(t('source_note'), 'small'))
    concern_names = {concern['id']: workflow_title(concern.get('workflow_id'), concern.get('title', t('concern')), locale)
                     for concern in intake.get('concerns', [])}
    status_names = {'FILLED': 'reported', 'UNCERTAIN': 'unknown', 'MISSING': 'uncollected', 'SKIPPED': 'skipped'}
    for index, source in enumerate(sources, 1):
        scope = concern_names.get(source.get('concern_id'))
        label = field_label(source.get('key', ''), source.get('label', source.get('key', t('source'))), locale)
        status = t(status_names.get(source.get('status'), 'reported'))
        story.append(_p(f"[{index}] {scope + ' / ' if scope else ''}{label} - {status}", 'subheading'))
        # Patient evidence is deliberately untouched. Only the server-authored
        # attachment registry description is localised, not the original file.
        value = (t('uploaded_source', filename=source['label']) if source.get('concern_id') == 'attachments'
                 else source.get('value') if source.get('value') is not None else t('no_value'))
        story.extend(_paragraphs(value))
    story.append(_p(t('appendix'), 'heading'))
    if not attachments:
        story.append(_p(t('no_attachments')))
    else:
        story.append(_p(t('appendix_note'), 'small'))
        for index, attachment in enumerate(attachments, 1):
            count = attachment['page_count']
            description = (t('pdf_pages', count=count) if attachment['media_type'] == 'application/pdf'
                           else t('frames', count=count) if count > 1 else t('complete_image'))
            story.append(_p(f"A{index}. {attachment['filename']} - {description}"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=_MARGIN, leftMargin=_MARGIN,
                            topMargin=45, bottomMargin=54, title=t('pdf_title'),
                            author='PreConsult', pageCompression=1)
    footer = lambda pdf, document: _footer(pdf, document, locale)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _attachment_page(attachment: dict, number: int, image_data: bytes | None = None, frame_index: int = 0, locale='en') -> bytes:
    t = lambda key, **values: report_text(locale, key, **values)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    frame_label = "  /  " + t('frame', frame=frame_index + 1, count=attachment['page_count']) if image_data is not None and attachment['page_count'] > 1 else ''
    title = _p(t('attachment_number', number=number) + frame_label, 'small')
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
        content = _p(t('pdf_cover', count=attachment['page_count']))
        _, height = content.wrap(_WIDTH, 300)
        content.drawOn(pdf, _MARGIN, top - 30 - height)
    footer = _p('PreConsult  |  ' + t('uploaded_attachment') + '  |  ' + t('private'), 'small')
    footer.wrap(_WIDTH, 30)
    footer.drawOn(pdf, _MARGIN, 22)
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

    locale = report_locale(intake.get('locale'))
    report = public_report(intake)
    synthesis = (intake.get('summary') or {}).get('synthesis') or {}
    if ((synthesis.get('status') == 'live' and report_locale(synthesis.get('locale')) != locale)
            or (report and (report_locale(report.get('locale')) != locale
                           or (locale != 'en' and report.get('localization_outdated'))))):
        raise HTTPException(409, 'Regenerate the summary and AI assessment in the selected patient language before downloading the report.')
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
    writer.append(PdfReader(BytesIO(_main_document(intake, report, attachments))), import_outline=False)
    for number, attachment in enumerate(attachments, 1):
        is_pdf = attachment['media_type'] == 'application/pdf'
        if is_pdf:
            writer.append(PdfReader(BytesIO(_attachment_page(attachment, number, locale=locale))), import_outline=False)
            source = PdfReader(BytesIO(attachment['data']))
            for page in source.pages:
                copied = writer.add_page(page, excluded_keys=['/AA', '/A', '/OpenAction', '/Thumb'])
                _remove_active_content(copied, set())
        else:
            for frame_index in range(attachment['page_count']):
                writer.append(PdfReader(BytesIO(_attachment_page(attachment, number, attachment['data'], frame_index, locale))), import_outline=False)
    writer.add_metadata({'/Title': report_text(locale, 'pdf_title'), '/Author': 'PreConsult',
                         '/Subject': report_text(locale, 'pdf_subject'), '/Language': locale})
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
