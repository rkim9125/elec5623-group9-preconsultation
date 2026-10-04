from fastapi.testclient import TestClient
from app.core.main import create_app


def test_product_app_disables_unowned_api_and_restricts_origins(tmp_path, monkeypatch):
    monkeypatch.setenv('PRODUCT_DB_PATH', str(tmp_path / 'app.sqlite3'))
    monkeypatch.setenv('APP_ENV', 'local')
    monkeypatch.setenv('APP_BASE_URL', 'http://127.0.0.1:8000')
    with TestClient(create_app(enable_legacy=False)) as client:
        assert client.post('/api/sessions', json={}).status_code == 404
        assert client.get('/api/v1/intakes').status_code == 401
        assert client.get('/api/v1/config').headers['cache-control'] == 'no-store'
        allowed = client.options('/api/v1/config', headers={'Origin':'http://127.0.0.1:8000','Access-Control-Request-Method':'GET'})
        assert allowed.headers.get('access-control-allow-origin') == 'http://127.0.0.1:8000'
        denied = client.options('/api/v1/config', headers={'Origin':'http://localhost:9999','Access-Control-Request-Method':'GET'})
        assert denied.status_code == 400
        assert 'access-control-allow-origin' not in denied.headers


def test_production_requires_exact_https_origin(tmp_path, monkeypatch):
    monkeypatch.setenv('PRODUCT_DB_PATH', str(tmp_path / 'prod.sqlite3'))
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('APP_BASE_URL', 'https://clinic.example.test')
    monkeypatch.setenv('ALLOWED_ORIGINS', '')
    with TestClient(create_app(enable_legacy=False)) as client:
        bad = client.options('/api/v1/config', headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET'})
        assert bad.status_code == 400
        good = client.options('/api/v1/config', headers={'Origin':'https://clinic.example.test','Access-Control-Request-Method':'GET'})
        assert good.status_code == 200
