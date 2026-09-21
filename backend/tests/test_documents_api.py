"""Exercise tools through HTTP, including authorization and approval boundaries."""
import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader
from docx import Document

from app.api.document_limits import DocumentUploadLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.main import create_app
from app.core.store import InMemorySessionStore, get_store
from app.utils.document_errors import DocumentError
from app.utils.document_service import DocumentService, InMemoryDocumentMetadataStore, get_document_service
from app.utils.storage import LocalStorage


@pytest.fixture
def env(tmp_path):
    settings = Settings(_env_file=None, storage_local_root=tmp_path / 'objects')
    store = InMemorySessionStore()
    metadata = InMemoryDocumentMetadataStore()
    service = DocumentService(settings, LocalStorage(settings.storage_local_root), metadata)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_document_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, store, settings


def new_session(client):
    r = client.post('/api/sessions', json={})
    assert r.status_code == 201
    return r.json()['session_id']


def upload(client, sid, name='notes.txt', data=b'Synthetic concern\nDuration unknown', mime='text/plain'):
    return client.post(f'/api/sessions/{sid}/documents', files={'file': (name, data, mime)})


def complete(client, sid):
    assert client.post(f'/api/sessions/{sid}/slots/chief_complaint',
                       json={'action': 'edit', 'value': 'Synthetic <example> & uncertainty'}).status_code == 200
    assert client.post(f'/api/sessions/{sid}/complete').status_code == 200
    return client.get(f'/api/sessions/{sid}/summary').json()


def test_upload_extract_download_delete_and_session_isolation(env):
    client, service, store, _ = env
    sid = new_session(client)
    other = new_session(client)
    state_before = store.get(sid).model_dump(mode='json')
    response = upload(client, sid)
    assert response.status_code == 201
    record = response.json()
    did = record['document_id']
    url = f'/api/sessions/{sid}/documents/{did}'
    assert record['status'] == 'uploaded'
    assert sid not in record['storage_key']
    assert record['storage_key'].startswith('c5/')
    assert client.get(f'/api/sessions/{sid}/documents').json()[0]['document_id'] == did
    result = client.post(url + '/extract').json()
    assert result['status'] == 'processed'
    assert result['extraction']['chunks'][0]['location'] == {'line': 1}
    assert store.get(sid).model_dump(mode='json') == state_before
    for method, suffix in [('get', ''), ('get', '/download'), ('post', '/extract'), ('delete', '')]:
        r = getattr(client, method)(f'/api/sessions/{other}/documents/{did}' + suffix)
        assert r.status_code == 404
        assert r.json()['error']['code'] == 'DOCUMENT_NOT_FOUND'
    response = client.get(url + '/download')
    assert response.content == b'Synthetic concern\nDuration unknown'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(f'/api/sessions/{sid}/documents').json() == []
    with pytest.raises(DocumentError):
        service.storage.get(record['storage_key'])


@pytest.mark.parametrize('name,data,mime,code', [
    ('../escape.txt', b'x', 'text/plain', 'INVALID_FILENAME'),
    ('legacy.doc', b'x', 'application/msword', 'UNSUPPORTED_FILE_TYPE'),
    ('empty.txt', b'', 'text/plain', 'EMPTY_FILE'),
    ('binary.txt', b'\xff\x00', 'text/plain', 'DOCUMENT_PARSE_FAILED'),
    ('pretend.pdf', b'not pdf', 'application/pdf', 'UNSUPPORTED_FILE_TYPE'),
    ('notes.txt', b'hello', 'image/png', 'UNSUPPORTED_FILE_TYPE'),
])
def test_upload_rejection_has_error_envelope_without_objects(env, name, data, mime, code):
    client, service, _, _ = env
    sid = new_session(client)
    r = upload(client, sid, name, data, mime)
    assert r.status_code == 422
    assert r.json()['error']['code'] == code
    assert service.list(sid) == []


def test_file_size_limit_and_nonexistent_session(env):
    client, service, _, settings = env
    settings.document_max_bytes = 4
    sid = new_session(client)
    assert upload(client, sid, data=b'12345').status_code == 413
    assert upload(client, 'not-a-session', data=b'123').status_code == 404
    assert service.list(sid) == []


def test_parse_failure_is_persisted_and_can_be_deleted(env):
    client, _, _, _ = env
    sid = new_session(client)
    r = upload(client, sid, 'broken.pdf', b'%PDF-1.7\nnot a real PDF', 'application/pdf')
    assert r.status_code == 201
    url = f"/api/sessions/{sid}/documents/{r.json()['document_id']}"
    failure = client.post(url + '/extract')
    assert failure.status_code == 422
    record = client.get(url).json()
    assert record['status'] == 'failed'
    assert record['error_code'] == 'DOCUMENT_PARSE_FAILED'
    assert client.delete(url).status_code == 204


def test_approval_is_explicit_version_bound_and_idempotent(env):
    client, _, store, _ = env
    sid = new_session(client)
    summary = complete(client, sid)
    assert summary['approved'] is False
    exports = f'/api/sessions/{sid}/exports'
    assert client.post(exports, json={'format': 'pdf'}).json()['error']['code'] == 'SUMMARY_NOT_APPROVED'
    approval = f'/api/sessions/{sid}/summary/approve'
    assert client.post(approval, json={'content_sha256': '0' * 64}).status_code == 409
    r = client.post(approval, json={'content_sha256': summary['content_sha256']})
    assert r.status_code == 200 and r.json()['approved'] is True
    timestamp = r.json()['approved_at']
    assert client.post(approval, json={'content_sha256': summary['content_sha256']}).json()['approved_at'] == timestamp
    for fmt in ('pdf', 'docx'):
        r = client.post(exports, json={'format': fmt})
        assert r.status_code == 201, r.text
        record = r.json()
        assert record['summary_sha256'] == summary['content_sha256']
        data = client.get(f"/api/sessions/{sid}/documents/{record['document_id']}/download").content
        if fmt == 'pdf':
            text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
        else:
            text = '\n'.join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        assert 'Synthetic <example> & uncertainty' in text
    store.get_summary(sid).sections['New fact'] = 'Updated by a future C3 summary version'
    assert client.get(f'/api/sessions/{sid}/summary').json()['approved'] is False
    assert client.post(exports, json={'format': 'pdf'}).status_code == 409
    assert client.post(approval, json={'content_sha256': summary['content_sha256']}).status_code == 409


def test_approval_before_completion_and_invalid_format(env):
    client, _, _, _ = env
    sid = new_session(client)
    assert client.post(f'/api/sessions/{sid}/summary/approve', json={'content_sha256': '0' * 64}).status_code == 409
    assert client.post(f'/api/sessions/{sid}/exports', json={'format': 'pdf'}).status_code == 409
    assert client.post(f'/api/sessions/{sid}/exports', json={'format': 'html'}).status_code == 422


def test_optional_token_protects_every_new_tool_route(env):
    client, _, _, settings = env
    from pydantic import SecretStr
    sid = new_session(client)
    settings.document_api_token = SecretStr('test-integration-token')
    routes = [
        ('get', '/api/documents/health', {}),
        ('get', f'/api/sessions/{sid}/documents', {}),
        ('post', f'/api/sessions/{sid}/documents', {'files': {'file': ('test.txt', b'x', 'text/plain')}}),
        ('get', f'/api/sessions/{sid}/documents/doc_x', {}),
        ('post', f'/api/sessions/{sid}/documents/doc_x/extract', {}),
        ('get', f'/api/sessions/{sid}/documents/doc_x/download', {}),
        ('delete', f'/api/sessions/{sid}/documents/doc_x', {}),
        ('post', f'/api/sessions/{sid}/exports', {'json': {'format': 'pdf'}}),
        ('post', f'/api/sessions/{sid}/summary/approve', {'json': {'content_sha256': '0' * 64}}),
    ]
    for method, path, kwargs in routes:
        for headers in ({}, {'Authorization': 'Bearer wrong'}):
            r = getattr(client, method)(path, headers=headers, **kwargs)
            assert r.status_code == 401, (path, r.text)
            assert r.json()['error']['code'] == 'DOCUMENT_ACCESS_DENIED'
    r = client.get('/api/documents/health', headers={'Authorization': 'Bearer test-integration-token'})
    assert r.status_code == 200


def test_download_detects_tampering(env):
    client, service, _, _ = env
    sid = new_session(client)
    record = upload(client, sid).json()
    service.storage.put(record['storage_key'], b'tampered', 'text/plain')
    r = client.get(f"/api/sessions/{sid}/documents/{record['document_id']}/download")
    assert r.status_code == 503
    assert r.json()['error']['code'] == 'DOCUMENT_INTEGRITY_FAILED'


def test_storage_delete_failure_preserves_metadata_for_retry(env, monkeypatch):
    client, service, _, _ = env
    sid = new_session(client)
    record = upload(client, sid).json()
    def fail(key):
        raise DocumentError('STORAGE_UNAVAILABLE', 'Unavailable', 503)
    monkeypatch.setattr(service.storage, 'delete', fail)
    r = client.delete(f"/api/sessions/{sid}/documents/{record['document_id']}")
    assert r.status_code == 503
    assert service.get(sid, record['document_id'])


def test_failed_metadata_write_rolls_back_object(env, monkeypatch):
    _, service, _, _ = env
    def fail(record):
        raise RuntimeError('metadata offline')
    monkeypatch.setattr(service.metadata, 'save', fail)
    with pytest.raises(RuntimeError, match='metadata offline'):
        service.upload('session', 'a.txt', b'example')
    assert not list(service.settings.storage_local_root.rglob('*.txt'))


@pytest.mark.parametrize('kwargs', [
    {'storage_backend': 's3', 'storage_bucket': 'example', 'storage_region': 'ap-southeast-2'},
    {'storage_backend': 'oss', 'document_api_token': 'test'},
    {'storage_access_key_id': 'incomplete'},
    {'storage_prefix': '../escape'},
    {'document_max_bytes': 0},
])
def test_invalid_storage_configuration_fails_early(kwargs):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **kwargs)


def test_configuration_errors_do_not_print_secrets():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, storage_access_key_secret="sensitive-test-credential")
    assert "sensitive-test-credential" not in str(caught.value)


def test_example_environment_is_bootable():
    from pathlib import Path
    settings = Settings(_env_file=Path(__file__).parents[1] / '.env.example')
    assert settings.api_port == 8000 and settings.storage_backend == 'local'


@pytest.mark.parametrize('with_length', [False, True])
def test_upload_request_bound_before_parser_even_without_content_length(with_length):
    called = False
    sent = []
    async def app(scope, receive, send):
        nonlocal called
        called = True
    body = b'x' * (64 * 1024 + 2)
    chunks = iter([{'type': 'http.request', 'body': body[:100], 'more_body': True},
                   {'type': 'http.request', 'body': body[100:], 'more_body': False}])
    async def receive():
        return next(chunks)
    async def send(event):
        sent.append(event)
    scope = {'type': 'http', 'method': 'POST', 'path': '/api/sessions/test/documents',
             'headers': [(b'content-length', str(len(body)).encode())] if with_length else []}
    asyncio.run(DocumentUploadLimitMiddleware(app, max_bytes=1)(scope, receive, send))
    assert not called
    assert sent[0]['status'] == 413


def test_malformed_multipart_and_unknown_routes_keep_error_envelope(env):
    client, _, _, _ = env
    sid = new_session(client)
    response = client.post(f'/api/sessions/{sid}/documents',
                           content=b'garbage', headers={'Content-Type': 'multipart/form-data'})
    assert response.status_code == 400
    assert response.json()['error']['code'] == 'BAD_REQUEST'
    response = client.get('/api/not-a-route')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'


def test_non_ascii_bearer_returns_unauthorized(env):
    from pydantic import SecretStr
    client, _, _, settings = env
    settings.document_api_token = SecretStr('configured-token')
    response = client.get('/api/documents/health', headers={b'Authorization': b'Bearer caf\xe9'})
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'DOCUMENT_ACCESS_DENIED'


def test_oversize_upload_error_has_cors_headers(env):
    client, _, _, _ = env
    response = client.post('/api/sessions/irrelevant/documents', content=b'x',
                           headers={'Content-Length': str(21 * 1024 * 1024),
                                    'Origin': 'http://localhost:5173'})
    assert response.status_code == 413
    assert response.headers['access-control-allow-origin'] == 'http://localhost:5173'
    assert response.json()['error']['code'] == 'FILE_TOO_LARGE'
