"""Synthetic complete-report coverage. No patient data, mail or provider calls."""
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
import pytest
from reportlab.pdfgen import canvas

from app.product import database, report_pdf
from app.product.auth import require_user
from app.product.intelligence import current_sources


def patient_record():
    return {'id': 'pdf-test', 'patient_id': 'p1', 'patient_name': 'Synthetic test patient',
            'patient_email': 'synthetic@example.test', 'title': 'Consultation with supporting records',
            'consent': True, 'status': 'review', 'model': 'gpt-6-sol', 'attachments': [],
            'shared_slots': {'goals': {'label': 'Appointment goals', 'value': '讨论腿痛 & questions <not markup>', 'status': 'FILLED'}},
            'concerns': [{'id': 'c1', 'title': 'Leg pain', 'workflow_id': 'leg_pain',
                          'slots': {'location': {'label': 'Location', 'value': 'Both shins', 'status': 'FILLED'},
                                    'medication': {'label': 'Current medication', 'value': None, 'status': 'UNCERTAIN'}}}],
            'summary': {'version': 3, 'generated_at': '2026-10-07T10:00:00Z',
                        'sections': [{'title': 'Reported concerns', 'entries': [{'label': 'Location', 'value': 'Both shins'}]}]}}


@pytest.fixture
def pdf_app(tmp_path, monkeypatch):
    from app.product import assessment
    monkeypatch.setenv('PRODUCT_DB_PATH', str(tmp_path / 'report.sqlite3'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('APP_ENV', 'local')
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO users VALUES ('p1','synthetic@example.test','Synthetic test patient','now')")
    database.save_intake(patient_record())
    identity = {'id': 'p1', 'email': 'synthetic@example.test', 'role': 'patient'}
    monkeypatch.setattr(assessment, 'public_report', lambda session: session.get('ai_report'))
    app = FastAPI()
    app.include_router(report_pdf.router, prefix='/api/v1')
    app.dependency_overrides[require_user] = lambda: identity
    return TestClient(app), identity, tmp_path


def save_attachment(tmp_path, name, data, media_type):
    root = tmp_path / 'uploads'
    root.mkdir(exist_ok=True)
    path = root / name
    path.write_bytes(data)
    record = database.load_intake('pdf-test')
    record['attachments'].append({'id': name, 'filename': name, 'media_type': media_type,
                                  'storage_path': str(path), 'size_bytes': len(data)})
    database.save_intake(record)
    return path


def source_pdf(pages=2):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for number in range(1, pages + 1):
        pdf.drawString(60, 720, f'ORIGINAL ATTACHMENT PAGE {number}')
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def image_bytes():
    buffer = BytesIO()
    photo = Image.new('RGB', (480, 240), 'white')
    for x in range(0, 80):
        for y in range(0, 240):
            photo.putpixel((x, y), (17, 110, 98))
    exif = Image.Exif()
    exif[274] = 6
    photo.save(buffer, format='JPEG', exif=exif)
    return buffer.getvalue()


def report_text(response):
    assert response.status_code == 200, response.text if response.status_code != 200 else ''
    pdf = PdfReader(BytesIO(response.content))
    return pdf, '\n'.join(page.extract_text() for page in pdf.pages)


def test_complete_pdf_contains_all_original_pages_full_oriented_image_and_unicode(pdf_app):
    client, _, tmp_path = pdf_app
    save_attachment(tmp_path, '原始记录.pdf', source_pdf(3), 'application/pdf')
    save_attachment(tmp_path, 'Photo.jpg', image_bytes(), 'image/jpeg')
    response = client.get('/api/v1/intakes/pdf-test/report.pdf')
    pdf, text = report_text(response)
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-disposition'].startswith('attachment;')
    for number in range(1, 4):
        assert text.count(f'ORIGINAL ATTACHMENT PAGE {number}') == 1
    assert '原始记录.pdf' in text
    assert '讨论腿痛' in text
    assert '<not markup>' in text
    assert 'Photo.jpg' in text
    images = list(pdf.pages[-1].images)
    assert len(images) == 1
    assert images[0].image.size == (240, 480), 'EXIF orientation is applied without cropping'
    assert len(pdf.pages) >= 6


@pytest.mark.parametrize('file_format,media_type,extension', [('WEBP', 'image/webp', 'webp'), ('PNG', 'image/png', 'png')])
def test_every_animated_image_frame_is_included(pdf_app, file_format, media_type, extension):
    client, _, tmp_path = pdf_app
    output = BytesIO()
    frames = [Image.new('RGB', (40, 30), 'red'), Image.new('RGB', (40, 30), 'blue')]
    frames[0].save(output, format=file_format, save_all=True, append_images=frames[1:], duration=100, lossless=True)
    save_attachment(tmp_path, f'animated.{extension}', output.getvalue(), media_type)
    pdf, text = report_text(client.get('/api/v1/intakes/pdf-test/report.pdf'))
    assert 'All 2 image frames' in text
    assert 'FRAME 1 OF 2' in text
    assert 'FRAME 2 OF 2' in text
    assert list(pdf.pages[-2].images)[0].image.getpixel((10, 10)) == (255, 0, 0)
    assert list(pdf.pages[-1].images)[0].image.getpixel((10, 10)) == (0, 0, 255)


def test_animation_above_frame_limit_fails_with_specific_explanation(pdf_app):
    client, _, tmp_path = pdf_app
    output = BytesIO()
    frames = [Image.new('RGB', (10, 10), (number * 7, 0, 0)) for number in range(31)]
    frames[0].save(output, format='WEBP', save_all=True, append_images=frames[1:], duration=100, lossless=True)
    save_attachment(tmp_path, 'long-animation.webp', output.getvalue(), 'image/webp')
    response = client.get('/api/v1/intakes/pdf-test/report.pdf')
    assert response.status_code == 422
    assert 'more than 30 frames' in response.json()['detail']


def test_pdf_contains_assessment_citations_and_preserves_fact_version(pdf_app):
    client, _, _ = pdf_app
    record = database.load_intake('pdf-test')
    source = current_sources(record)[0]['id']
    record['summary']['synthesis'] = {'status': 'live', 'patient_overview': [{'text': 'Patient wants to discuss leg discomfort.', 'source_ids': [source]}],
                                    'clinician_brief': [], 'concern_summaries': [], 'appointment_agenda': [], 'uncertainties': []}
    record['ai_report'] = {
        'status': 'ready', 'model': 'synthetic-model', 'generated_at': '2026-10-07T10:01:00Z', 'summary_version': 3,
        'overview': {'text': 'Preliminary synthetic assessment.', 'source_ids': [source]},
        'possible_diagnoses': [{'name': 'Example diagnostic hypothesis', 'explanation': 'Requires clinical examination.',
                               'supporting_evidence': ['Reported symptoms'], 'uncertainties': ['No examination'], 'source_ids': [source]}],
        'care_guidance': {'urgency': 'uncertain', 'timeframe': 'Discuss with a clinician', 'reason': 'Insufficient information.', 'source_ids': [source]},
        'next_steps': [{'text': 'Bring your symptom timeline.', 'source_ids': [source]}],
        'red_flags': [{'text': 'Seek emergency help for severe new symptoms.', 'source_ids': []}],
        'missing_information': [{'text': 'A clinical examination is missing.', 'source_ids': []}],
        'attachment_reviews': [], 'limitations': ['Synthetic fixture.'], 'sources': current_sources(record)}
    database.save_intake(record)
    original = database.load_intake('pdf-test')
    _, text = report_text(client.get('/api/v1/intakes/pdf-test/report.pdf'))
    for expected in ['AI diagnosis & consultation guidance', 'Example diagnostic hypothesis', 'synthetic-model',
                     'CLINICIAN REVIEW REQUIRED', 'Patient overview', '[Sources 1]', 'Information still needed']:
        assert expected in text
    assert database.load_intake('pdf-test') == original


def test_owner_and_only_current_assigned_doctor_can_export(pdf_app):
    client, identity, _ = pdf_app
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 200
    identity['id'] = 'stranger'
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 404
    identity.update(id='doctor1', email='doctor@example.test', role='doctor')
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 404
    record = database.load_intake('pdf-test')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    database.save_intake(record)
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 200
    identity['email'] = 'another@example.test'
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 404
    identity['email'] = 'doctor@example.test'
    record = database.load_intake('pdf-test')
    record['status'] = 'withdrawn'
    database.save_intake(record)
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 404


@pytest.mark.parametrize('problem', ['missing', 'damaged', 'outside'])
def test_bad_attachment_fails_whole_export_without_disclosing_path(pdf_app, problem):
    client, _, tmp_path = pdf_app
    path = save_attachment(tmp_path, 'Document.pdf', source_pdf(), 'application/pdf')
    if problem == 'missing':
        path.unlink()
    elif problem == 'damaged':
        path.write_bytes(b'%PDF-invalid')
    else:
        record = database.load_intake('pdf-test')
        record['attachments'][0]['storage_path'] = str(tmp_path / 'outside-secret.pdf')
        database.save_intake(record)
    response = client.get('/api/v1/intakes/pdf-test/report.pdf')
    assert response.status_code == 409
    assert 'complete report' in response.json()['detail']
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize('change', ['withdraw', 'edit'])
def test_access_and_version_rechecked_after_render(pdf_app, monkeypatch, change):
    client, identity, _ = pdf_app
    record = database.load_intake('pdf-test')
    record.update(status='approved', doctor_email='doctor@example.test')
    record['summary']['approved_at'] = 'now'
    database.save_intake(record)
    identity.update(id='doctor1', email='doctor@example.test', role='doctor')
    def render_then_change(snapshot):
        changed = database.load_intake('pdf-test')
        changed['status' if change == 'withdraw' else 'title'] = 'withdrawn' if change == 'withdraw' else 'Changed title'
        database.save_intake(changed)
        return b'%PDF-do-not-return'
    monkeypatch.setattr(report_pdf, 'create_pdf', render_then_change)
    response = client.get('/api/v1/intakes/pdf-test/report.pdf')
    assert response.status_code == (404 if change == 'withdraw' else 409)
    assert b'%PDF-do-not-return' not in response.content


def test_source_pdf_scripts_and_links_removed_static_highlight_preserved(pdf_app):
    client, _, tmp_path = pdf_app
    source = PdfReader(BytesIO(source_pdf(1)))
    writer = PdfWriter()
    page = writer.add_page(source.pages[0])
    script = DictionaryObject({NameObject('/S'): NameObject('/JavaScript'), NameObject('/JS'): TextStringObject('app.alert("unsafe")')})
    page[NameObject('/AA')] = DictionaryObject({NameObject('/O'): script})
    highlight = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Highlight'),
                                  NameObject('/Contents'): TextStringObject('Preserved source annotation'), NameObject('/A'): script})
    link = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Link'), NameObject('/A'): script})
    page[NameObject('/Annots')] = ArrayObject([writer._add_object(highlight), writer._add_object(link)])
    writer.add_js('app.alert("unsafe root")')
    output = BytesIO()
    writer.write(output)
    save_attachment(tmp_path, 'annotated.pdf', output.getvalue(), 'application/pdf')
    pdf, _ = report_text(client.get('/api/v1/intakes/pdf-test/report.pdf'))
    last = pdf.pages[-1]
    assert '/AA' not in last
    annotations = last['/Annots']
    assert len(annotations) == 1
    assert annotations[0].get_object()['/Contents'] == 'Preserved source annotation'
    assert '/A' not in annotations[0].get_object()
    assert b'/JavaScript' not in client.get('/api/v1/intakes/pdf-test/report.pdf').content


def test_long_multilingual_values_wrap_across_pages_without_truncation(pdf_app):
    client, _, _ = pdf_app
    record = database.load_intake('pdf-test')
    record['shared_slots']['goals']['value'] = ('Patient words 腿疼 & questions. ' * 180) + 'END-OF-ORIGINAL'
    database.save_intake(record)
    pdf, text = report_text(client.get('/api/v1/intakes/pdf-test/report.pdf'))
    assert '腿疼' in text
    assert 'END-OF-ORIGINAL' in text
    assert len(pdf.pages) > 1


def test_summary_must_exist_and_pending_corrections_block_export(pdf_app):
    client, _, _ = pdf_app
    record = database.load_intake('pdf-test')
    record['summary']['needs_reconciliation'] = True
    database.save_intake(record)
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 409
    record = database.load_intake('pdf-test')
    record.update(status='active', summary=None)
    database.save_intake(record)
    assert client.get('/api/v1/intakes/pdf-test/report.pdf').status_code == 409
