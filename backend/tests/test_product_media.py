"""Temporary media integration tests; no real patient data or provider calls."""
from io import BytesIO
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from app.product import media, database
from app.product.auth import require_user


@pytest.fixture
def media_app(tmp_path, monkeypatch):
    monkeypatch.setenv('PRODUCT_DB_PATH', str(tmp_path / 'media.sqlite3'))
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path / 'uploads'))
    monkeypatch.setenv('APP_ENV', 'local')
    monkeypatch.setenv('APP_BASE_URL', 'http://testserver')
    database.init_db()
    with database.get_connection() as conn:
        conn.execute("INSERT INTO users VALUES ('p1','patient@example.com','Patient','now')")
    database.save_intake({'id':'intake1','patient_id':'p1','consent':True,'status':'active','model':'gpt-6-sol','attachments':[], 'summary':None})
    identity = {'id':'p1','email':'patient@example.com','role':'patient'}
    app = FastAPI()
    app.include_router(media.router, prefix='/api/v1')
    app.dependency_overrides[require_user] = lambda: identity
    return TestClient(app, headers={'Origin':'http://testserver'}), identity


def png():
    stream = BytesIO()
    Image.new('RGB', (5, 5), 'blue').save(stream, format='PNG')
    return stream.getvalue()


def test_upload_download_remove_are_private(media_app):
    client, identity = media_app
    uploaded = client.post('/api/v1/intakes/intake1/attachments', files={'file':('../scan.png', png(), 'image/png')})
    assert uploaded.status_code == 201, uploaded.text
    a = uploaded.json()
    assert a['filename'] == 'scan.png'
    assert 'storage_path' not in a
    assert client.get(a['url']).content == png()
    identity['id'] = 'stranger'
    assert client.get(a['url']).status_code == 404
    identity['id'] = 'p1'
    assert client.delete(a['url']).status_code == 204
    assert client.get(a['url']).status_code == 404


def test_mime_spoofing_and_unsupported_files_rejected(media_app):
    client, _ = media_app
    assert client.post('/api/v1/intakes/intake1/attachments', files={'file':('x.png', b'<script>alert(1)</script>', 'image/png')}).status_code == 422
    assert client.post('/api/v1/intakes/intake1/attachments', files={'file':('x.html', b'html', 'text/html')}).status_code == 415
    assert client.post('/api/v1/intakes/intake1/attachments', files={'file':('x.pdf', b'%PDF-invalid', 'application/pdf')}).status_code == 422


def test_approved_upload_locked_and_doctor_revocation(media_app):
    client, identity = media_app
    a = client.post('/api/v1/intakes/intake1/attachments', files={'file':('scan.png', png(), 'image/png')}).json()
    record = database.load_intake('intake1')
    record.update(status='approved', doctor_email='doctor@example.com', summary={'approved_at':'now'})
    database.save_intake(record)
    assert client.post('/api/v1/intakes/intake1/attachments', files={'file':('scan.png', png(), 'image/png')}).status_code == 409
    identity.update(id='d1', email='doctor@example.com', role='doctor')
    assert client.get(a['url']).status_code == 200
    assert client.delete(a['url']).status_code == 404
    record = database.load_intake('intake1')
    record['status'] = 'withdrawn'
    database.save_intake(record)
    assert client.get(a['url']).status_code == 404


def test_media_requires_same_origin_and_consent(media_app):
    client, _ = media_app
    assert client.post('/api/v1/intakes/intake1/attachments', headers={'Origin':'https://attacker.example'}, files={'file':('scan.png', png(), 'image/png')}).status_code == 403
    record = database.load_intake('intake1')
    record['consent'] = False
    database.save_intake(record)
    assert client.post('/api/v1/intakes/intake1/attachments', files={'file':('scan.png', png(), 'image/png')}).status_code == 409


def test_attachment_change_invalidates_existing_review(media_app):
    client, _ = media_app
    record = database.load_intake('intake1')
    record.update(status='review', summary={'version':7,'text':'Previously reviewed file list'})
    database.save_intake(record)
    response = client.post('/api/v1/intakes/intake1/attachments', files={'file':('new.png', png(), 'image/png')})
    assert response.status_code == 201
    changed = database.load_intake('intake1')
    assert changed['status'] == 'active'
    assert changed['summary'] is None
    assert changed['_summary_version'] == 7
