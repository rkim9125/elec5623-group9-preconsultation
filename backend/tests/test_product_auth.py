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

def test_any_verified_email_can_register_as_doctor(auth_client):
    client, codes = auth_client
    assert sign_in(client, codes, "outsider@gmail.com", "doctor")["role"] == "doctor"
    assert client.get("/api/v1/auth/me").json()["user"]["role"] == "doctor"

def test_registered_role_is_permanent_and_independent_of_legacy_allowlist(auth_client, monkeypatch):
    client, codes = auth_client
    sign_in(client, codes, "doctor@example.test", "doctor")
    monkeypatch.setenv("DOCTOR_EMAILS", "second@example.test")
    assert client.get("/api/v1/auth/me").status_code == 200
    result = client.post("/api/v1/auth/request-code", json={"email":"  DOCTOR@example.test ", "role":"patient"})
    assert result.status_code == 409
    assert "different account role" in result.json()["detail"]
    assert client.post("/api/v1/auth/verify", json={"email":"doctor@example.test", "role":"patient", "code":codes["doctor@example.test"]}).status_code == 409

def test_patient_email_cannot_register_doctor_role(auth_client):
    client, codes = auth_client
    sign_in(client, codes, "person@yahoo.com")
    assert client.post("/api/v1/auth/request-code", json={"email":"PERSON@yahoo.com", "role":"doctor"}).status_code == 409

def test_first_verified_role_wins_competing_challenges(auth_client):
    client, codes = auth_client
    email = "new@example.test"
    assert client.post("/api/v1/auth/request-code", json={"email": email, "role": "patient"}).status_code == 200
    patient_code = codes[email]
    with get_connection() as conn:
        conn.execute("DELETE FROM rate_limits")
    assert client.post("/api/v1/auth/request-code", json={"email": email, "role": "doctor"}).status_code == 200
    assert client.post("/api/v1/auth/verify", json={"email": email, "role": "patient", "code": patient_code}).status_code == 200
    assert client.post("/api/v1/auth/verify", json={"email": email, "role": "doctor", "code": codes[email]}).status_code == 409
    with get_connection() as conn:
        assert conn.execute("SELECT role FROM account_roles").fetchone()[0] == "patient"
        assert conn.execute("SELECT COUNT(*) FROM otp_challenges").fetchone()[0] == 0

def test_legacy_roles_migrate_once_preserving_patient_records(product_env, monkeypatch):
    with get_connection() as conn:
        conn.execute("DROP TABLE account_roles")
        conn.executemany("INSERT INTO users VALUES (?, ?, '', '2025-01-01')", [
            ("mixed", "mixed@example.test"), ("doctor", "doctor@example.test"), ("first", "first@example.test")])
        conn.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?, ?)", [
            ("mixed-doctor", "mixed", "doctor", time.time() + 1000, "2025-01-01"),
            ("mixed-patient", "mixed", "patient", time.time() + 1000, "2025-02-01"),
            ("first-doctor", "first", "doctor", time.time() + 1000, "2025-01-01"),
            ("first-patient", "first", "patient", time.time() + 1000, "2025-02-01")])
        conn.execute("INSERT INTO intakes VALUES ('kept', 'mixed', 1, '{}', '2025-02-01')")
    init_db()
    monkeypatch.setenv("DOCTOR_EMAILS", "")
    init_db()
    with get_connection() as conn:
        roles = {row["user_id"]: row["role"] for row in conn.execute("SELECT * FROM account_roles")}
        assert roles == {"mixed": "patient", "doctor": "doctor", "first": "doctor"}
        assert conn.execute("SELECT COUNT(*) FROM intakes").fetchone()[0] == 1
        assert {row[0] for row in conn.execute("SELECT token_hash FROM sessions")} == {"mixed-patient", "first-doctor"}

def test_registered_doctors_excludes_unregistered_allowlist_entries(auth_client):
    from app.product.database import registered_doctors
    client, codes = auth_client
    assert registered_doctors() == []
    sign_in(client, codes, "newdoctor@gmail.com", "doctor")
    client.patch("/api/v1/auth/me", json={"name": "Dr Green"})
    assert registered_doctors() == [{"email": "newdoctor@gmail.com", "name": "Dr Green"}]

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


def test_patient_background_is_durable_isolated_and_editable(auth_client):
    from app.product.profiles import load_profile, snapshot_for_intake, prefill_answers
    client, codes = auth_client
    user = sign_in(client, codes)
    initial = client.get("/api/v1/auth/profile")
    assert initial.status_code == 200
    assert initial.json()["profile"]["updated_at"] is None
    values = {"date_of_birth": "1990-04-25", "sex_at_birth": "female", "blood_group": "O+", "medical_history": "Childhood asthma", "surgical_history": "Appendectomy in 2005", "family_history": "Father has diabetes", "accessibility_needs": "Large text"}
    response = client.put("/api/v1/auth/profile", json=values)
    assert response.status_code == 200, response.text
    saved = response.json()["profile"]
    assert saved["date_of_birth"] == values["date_of_birth"]
    assert saved["updated_at"] and set(saved["field_updated_at"]) == set(values)
    snapshot = snapshot_for_intake(user["id"])
    assert load_profile(user["id"]) == saved
    assert prefill_answers(user["id"]) == [{"concern_id": "session", "key": "relevant_history", "value": "Medical history: Childhood asthma\nSurgical history: Appendectomy in 2005\nFamily history: Father has diabetes", "status": "FILLED"}]
    assert client.put("/api/v1/auth/profile", json=values).json()["profile"] == saved
    edited = client.put("/api/v1/auth/profile", json={**values, "medical_history": ""}).json()["profile"]
    assert edited["medical_history"] == ""
    assert edited["field_updated_at"]["date_of_birth"] == saved["field_updated_at"]["date_of_birth"]
    assert snapshot["medical_history"] == "Childhood asthma"
    client.post("/api/v1/auth/logout")
    sign_in(client, codes, "another@example.test")
    assert client.get("/api/v1/auth/profile").json()["profile"]["medical_history"] == ""
    assert load_profile(user["id"])["date_of_birth"] == "1990-04-25"


@pytest.mark.parametrize("field", ["current_medications", "allergies", "weight", "blood_pressure", "pregnancy_status", "symptoms"])
def test_profile_rejects_expiry_prone_fields(auth_client, field):
    client, codes = auth_client
    sign_in(client, codes)
    assert client.put("/api/v1/auth/profile", json={field: "Must not carry forward"}).status_code == 422
    assert client.get("/api/v1/auth/profile").json()["profile"]["updated_at"] is None


def test_profile_validates_dates_requires_patient_and_csrf(auth_client):
    client, codes = auth_client
    sign_in(client, codes)
    for value in ("2024-02-30", "9999-01-01", "not a date"):
        assert client.put("/api/v1/auth/profile", json={"date_of_birth": value}).status_code == 422
    assert client.put("/api/v1/auth/profile", json={"sex_at_birth": "invalid"}).status_code == 422
    assert client.put("/api/v1/auth/profile", json={"medical_history": "a" * 3000, "surgical_history": "b" * 3000}).status_code == 422
    assert client.put("/api/v1/auth/profile", json={"medical_history": "Changed"}, headers={"Origin": "https://evil.test"}).status_code == 403
    client.post("/api/v1/auth/logout")
    sign_in(client, codes, "doctor@outlook.com", "doctor")
    assert client.get("/api/v1/auth/profile").status_code == 403
    assert client.put("/api/v1/auth/profile", json={}).status_code == 403
