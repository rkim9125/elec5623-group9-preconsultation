"""Security regressions. Mocks send no email and never call a live model."""
import time
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from app.product import auth
from app.product.database import get_connection, init_db

REAL_SEND_VERIFICATION_EMAIL = auth.send_verification_email

@pytest.fixture
def product_env(monkeypatch, tmp_path):
    for key, value in {"APP_ENV":"test", "APP_BASE_URL":"http://testserver", "PRODUCT_DB_PATH":str(tmp_path / "product.sqlite3"), "UPLOAD_DIR":str(tmp_path / "uploads"), "RESEND_API_KEY":"fake", "RESEND_FROM_EMAIL":"signin@example.test", "DOCTOR_EMAILS":"doctor@example.test,second@example.test", "OPENAI_API_KEY":"", "OPENAI_MODEL":"gpt-6-sol"}.items():
        monkeypatch.setenv(key, value)
    init_db()
    codes = {}
    monkeypatch.setattr(auth, "send_verification_email", lambda email, code: codes.__setitem__(email, code))
    return codes

@pytest.fixture
def auth_client(product_env):
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    with TestClient(app, headers={"Origin":"http://testserver"}) as client:
        yield client, product_env

def sign_in(client, codes, email="patient@example.test", role="patient"):
    requested = client.post("/api/v1/auth/request-code", json={"email":email, "role":role})
    assert requested.status_code == 200, requested.text
    result = client.post("/api/v1/auth/verify", json={"email":email, "role":role, "code":codes[email]})
    assert result.status_code == 200, result.text
    return result.json()["user"]

def test_otp_is_hashed_single_use_and_session_is_opaque(auth_client):
    client, codes = auth_client
    user = sign_in(client, codes)
    assert user["role"] == "patient"
    assert set(user) == {"id", "email", "name", "role"}
    token = client.cookies.get("preconsult_session")
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM otp_challenges").fetchone()[0] == 0
        assert conn.execute("SELECT token_hash FROM sessions").fetchone()[0] != token
    assert client.get("/api/v1/auth/me").json()["user"] == user
    assert client.post("/api/v1/auth/verify", json={"email":user["email"], "code":codes[user["email"]]}).status_code == 400
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

def test_code_never_returned_or_stored_in_plaintext(auth_client):
    client, codes = auth_client
    email = "patient@example.test"
    requested = client.post("/api/v1/auth/request-code", json={"email":email})
    assert codes[email] not in requested.text
    with get_connection() as conn:
        challenge = dict(conn.execute("SELECT * FROM otp_challenges").fetchone())
    assert challenge["code_hash"] != codes[email]
    assert "code" not in challenge
    verified = client.post("/api/v1/auth/verify", json={"email":email, "code":codes[email]})
    assert "HttpOnly" in verified.headers["set-cookie"]
    assert "SameSite=lax" in verified.headers["set-cookie"]

def test_five_wrong_codes_lock_challenge(auth_client):
    client, codes = auth_client
    email = "patient@example.test"
    client.post("/api/v1/auth/request-code", json={"email":email})
    wrong = "000000" if codes[email] != "000000" else "111111"
    for _ in range(5):
        assert client.post("/api/v1/auth/verify", json={"email":email, "code":wrong}).status_code == 400
    with get_connection() as conn:
        assert conn.execute("SELECT attempts FROM otp_challenges").fetchone()[0] == 5
    assert client.post("/api/v1/auth/verify", json={"email":email, "code":codes[email]}).status_code == 400

def test_expired_code_rejected(auth_client):
    client, codes = auth_client
    email = "patient@example.test"
    client.post("/api/v1/auth/request-code", json={"email":email})
    with get_connection() as conn:
        conn.execute("UPDATE otp_challenges SET expires_at = ?", (time.time()-1,))
    assert client.post("/api/v1/auth/verify", json={"email":email, "code":codes[email]}).status_code == 400

def test_origin_required_for_auth_and_session_mutations(auth_client):
    client, codes = auth_client
    assert client.post("/api/v1/auth/request-code", json={"email":"patient@example.test"}, headers={"Origin":"https://evil.example"}).status_code == 403
    sign_in(client, codes)
    assert client.patch("/api/v1/auth/me", json={"name":"Injected"}, headers={"Origin":"https://evil.example"}).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"Origin":"null"}).status_code == 403
    client.headers.pop("Origin")
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200

def test_doctor_role_cannot_be_self_assigned(auth_client):
    client, codes = auth_client
    assert client.post("/api/v1/auth/request-code", json={"email":"outsider@example.test", "role":"doctor"}).status_code == 403
    assert sign_in(client, codes, "outsider@example.test")["role"] == "patient"
    assert client.post("/api/v1/auth/verify", json={"email":"outsider@example.test", "role":"doctor", "code":codes["outsider@example.test"]}).status_code == 403

def test_clinician_allowlist_revocation_ends_access(auth_client, monkeypatch):
    client, codes = auth_client
    sign_in(client, codes, "doctor@example.test", "doctor")
    monkeypatch.setenv("DOCTOR_EMAILS", "second@example.test")
    assert client.get("/api/v1/auth/me").status_code == 403

def test_role_specific_otp_cannot_switch_role(auth_client):
    client, codes = auth_client
    email = "doctor@example.test"
    assert client.post("/api/v1/auth/request-code", json={"email":email, "role":"patient"}).status_code == 200
    assert client.post("/api/v1/auth/verify", json={"email":email, "role":"doctor", "code":codes[email]}).status_code == 400

def test_resend_rate_limit(auth_client):
    client, _ = auth_client
    body = {"email":"patient@example.test"}
    assert client.post("/api/v1/auth/request-code", json=body).status_code == 200
    assert client.post("/api/v1/auth/request-code", json=body).status_code == 429

def test_missing_sender_fails_without_challenge(auth_client, monkeypatch):
    client, codes = auth_client
    monkeypatch.setenv("RESEND_FROM_EMAIL", "")
    assert client.post("/api/v1/auth/request-code", json={"email":"patient@example.test"}).status_code == 503
    assert not codes
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM otp_challenges").fetchone()[0] == 0

def test_delivery_failure_invalidates_code(auth_client, monkeypatch):
    client, _ = auth_client
    def failed_send(*args):
        raise HTTPException(502, "Email delivery failed")
    monkeypatch.setattr(auth, "send_verification_email", failed_send)
    assert client.post("/api/v1/auth/request-code", json={"email":"patient@example.test"}).status_code == 502
    with get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM otp_challenges").fetchone()[0] == 0

def test_logout_revokes_server_side_token(auth_client):
    client, codes = auth_client
    sign_in(client, codes)
    token = client.cookies.get("preconsult_session")
    client.post("/api/v1/auth/logout")
    client.cookies.set("preconsult_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_production_cookie_is_host_only_and_secure(auth_client, monkeypatch):
    client, codes = auth_client
    monkeypatch.setenv("APP_ENV", "production")
    email = "patient@example.test"
    client.post("/api/v1/auth/request-code", json={"email":email})
    response = client.post("/api/v1/auth/verify", json={"email":email, "code":codes[email]})
    cookie = response.headers["set-cookie"]
    assert "__Host-preconsult_session=" in cookie
    assert "Secure" in cookie and "HttpOnly" in cookie
    assert "Domain=" not in cookie


def test_resend_adapter_masks_provider_response_and_rejects_failure(product_env, monkeypatch):
    import httpx
    def rejected(*args, **kwargs):
        return httpx.Response(403, json={"message":"private-provider-detail"}, request=httpx.Request("POST", "https://api.resend.com/emails"))
    monkeypatch.setattr(auth.httpx, "post", rejected)
    with pytest.raises(HTTPException) as error:
        REAL_SEND_VERIFICATION_EMAIL("patient@example.test", "123456")
    assert error.value.status_code == 502
    assert "private-provider-detail" not in error.value.detail
    assert "123456" not in error.value.detail


def test_resend_adapter_requires_delivery_receipt(product_env, monkeypatch):
    import httpx
    def no_receipt(*args, **kwargs):
        return httpx.Response(200, json={}, request=httpx.Request("POST", "https://api.resend.com/emails"))
    monkeypatch.setattr(auth.httpx, "post", no_receipt)
    with pytest.raises(HTTPException) as error:
        REAL_SEND_VERIFICATION_EMAIL("patient@example.test", "123456")
    assert error.value.status_code == 502
