"""Ownership, sharing and concurrency boundaries independent of LLM behavior."""
from copy import deepcopy
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.product import auth
from app.product.database import ConcurrentUpdate, load_intake, save_intake
from .test_product_auth import product_env, sign_in

@pytest.fixture
def api(product_env, monkeypatch):
    from app.product import routes
    def fake_review(session, correction=None):
        session["summary"] = {"version":(session.get("summary") or {}).get("version", 0)+1, "text":correction or "Patient-reported intake draft.", "gaps":[]}
        session["status"] = "review"
        return session
    def fake_message(session, text, action="answer"):
        session["messages"].append({"role":"patient", "text":text})
        session["status"] = "active"
        return session
    # Keep real intake/form initialization; isolate only the remote AI operations.
    monkeypatch.setattr(routes.pipeline, "build_review", fake_review)
    monkeypatch.setattr(routes.pipeline, "process_message", fake_message)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(routes.router, prefix="/api/v1")
    clients = {}
    def login(email, role="patient"):
        client = TestClient(app, headers={"Origin":"http://testserver"})
        sign_in(client, product_env, email, role)
        clients[email] = client
        return client
    yield app, login
    for client in clients.values():
        client.close()


def new_intake(client):
    result = client.post("/api/v1/intakes", json={"consent":True})
    assert result.status_code == 201, result.text
    return result.json()


def share(client, intake_id, doctor="doctor@example.test"):
    draft = client.post(f"/api/v1/intakes/{intake_id}/review").json()
    result = client.post(f"/api/v1/intakes/{intake_id}/approve", json={"version":draft["summary"]["version"], "doctor_email":doctor})
    assert result.status_code == 200, result.text
    return result.json()


def test_unauthenticated_access_and_no_legacy_routes(api):
    app, _ = api
    with TestClient(app) as client:
        for path in ("/intakes", "/workflows", "/clinician/intakes"):
            assert client.get("/api/v1"+path).status_code == 401
        assert client.get("/api/sessions").status_code == 404


def test_patient_isolation_for_reads_edits_and_deletes(api):
    _, login = api
    alice = login("alice@example.test")
    bob = login("bob@example.test")
    intake = new_intake(alice)
    url = f"/api/v1/intakes/{intake['id']}"
    assert len(alice.get("/api/v1/intakes").json()) == 1
    assert bob.get("/api/v1/intakes").json() == []
    assert bob.get(url).status_code == 404
    assert bob.post(url+"/messages", json={"text":"Harmful overwrite"}).status_code == 404
    assert bob.post(url+"/review").status_code == 404
    assert bob.delete(url).status_code == 404
    assert alice.get(url).json()["messages"] == intake["messages"]


def test_clinician_sees_only_explicitly_approved_assigned_version(api):
    _, login = api
    patient = login("patient@example.test")
    doctor = login("doctor@example.test", "doctor")
    other = login("second@example.test", "doctor")
    intake = new_intake(patient)
    url = f"/api/v1/clinician/intakes/{intake['id']}"
    assert doctor.get(url).status_code == 404
    assert doctor.get("/api/v1/clinician/intakes").json() == []
    approved = share(patient, intake["id"])
    assert approved["summary"]["approved_version"] == 1
    assert doctor.get(url).status_code == 200
    assert "messages" not in doctor.get(url).json()
    assert "plan" not in doctor.get(url).json()
    assert len(doctor.get("/api/v1/clinician/intakes").json()) == 1
    assert other.get(url).status_code == 404
    assert other.get("/api/v1/clinician/intakes").json() == []
    assert patient.get(url).status_code == 403
    assert doctor.get("/api/v1/intakes").status_code == 403
    assert doctor.post(url+"/reviewed").json()["reviewed_at"]


def test_sharing_requires_current_summary_and_allowlisted_recipient(api):
    _, login = api
    client = login("patient@example.test")
    intake = new_intake(client)
    url = f"/api/v1/intakes/{intake['id']}"
    assert client.post(url+"/approve", json={"version":1, "doctor_email":"doctor@example.test"}).status_code == 409
    client.post(url+"/review")
    revised = client.patch(url+"/review", json={"text":"My correction."}).json()
    assert revised["summary"]["version"] == 2
    assert client.post(url+"/approve", json={"version":1, "doctor_email":"doctor@example.test"}).status_code == 409
    assert client.post(url+"/approve", json={"version":2, "doctor_email":"outsider@example.test"}).status_code == 422
    assert client.post(url+"/approve", json={"version":2}).status_code == 422


def test_withdrawal_revokes_doctor_visibility_and_allows_patient_revision(api):
    _, login = api
    patient = login("patient@example.test")
    doctor = login("doctor@example.test", "doctor")
    intake = new_intake(patient)
    url = f"/api/v1/intakes/{intake['id']}"
    share(patient, intake["id"])
    assert patient.post(url+"/messages", json={"text":"An edit"}).status_code == 409
    withdrawn = patient.post(url+"/withdraw").json()
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["doctor_email"] is None
    assert "approved_at" not in withdrawn["summary"]
    assert doctor.get(f"/api/v1/clinician/intakes/{intake['id']}").status_code == 404
    assert doctor.get("/api/v1/clinician/intakes").json() == []
    assert patient.post(url+"/messages", json={"text":"Updated detail"}).status_code == 200
    assert share(patient, intake["id"])["summary"]["version"] == 2


def test_explicit_consent_required_and_revocation_prevents_edits(api):
    _, login = api
    client = login("patient@example.test")
    assert client.post("/api/v1/intakes", json={"consent":False}).status_code == 422
    assert client.post("/api/v1/intakes", json={}).status_code == 422
    intake = new_intake(client)
    intake["consent"] = False
    intake["status"] = "withdrawn"
    save_intake(intake)
    assert client.post(f"/api/v1/intakes/{intake['id']}/messages", json={"text":"Update"}).status_code == 409
    assert client.post(f"/api/v1/intakes/{intake['id']}/review").status_code == 409


def test_storage_paths_are_private_and_delete_removes_owned_uploads(api, tmp_path):
    _, login = api
    patient = login("patient@example.test")
    doctor = login("doctor@example.test", "doctor")
    intake = new_intake(patient)
    directory = tmp_path / "uploads" / intake["id"]
    directory.mkdir(parents=True)
    file = directory / "sample.pdf"
    file.write_bytes(b"example")
    intake["attachments"] = [{"id":"sample", "name":"sample.pdf", "storage_path":str(file)}]
    save_intake(intake)
    returned = patient.get(f"/api/v1/intakes/{intake['id']}").json()
    assert "storage_path" not in returned["attachments"][0]
    share(patient, intake["id"])
    returned = doctor.get(f"/api/v1/clinician/intakes/{intake['id']}").json()
    assert "storage_path" not in returned["attachments"][0]
    assert patient.delete(f"/api/v1/intakes/{intake['id']}").status_code == 204
    assert not directory.exists()
    assert doctor.get(f"/api/v1/clinician/intakes/{intake['id']}").status_code == 404


def test_optimistic_lock_prevents_overwriting_newer_data(api):
    _, login = api
    patient = login("patient@example.test")
    original = new_intake(patient)
    first, stale = deepcopy(original), deepcopy(original)
    first["title"] = "New title"
    save_intake(first)
    stale["title"] = "Stale overwrite"
    with pytest.raises(ConcurrentUpdate):
        save_intake(stale)
    assert load_intake(original["id"])["title"] == "New title"


def test_concurrent_engine_update_returns_409(api, monkeypatch):
    from app.product import routes
    _, login = api
    patient = login("patient@example.test")
    intake = new_intake(patient)
    def racing_message(session, text, action):
        other = deepcopy(session)
        other["title"] = "Concurrent saved title"
        save_intake(other)
        session["title"] = "Stale title"
        return session
    monkeypatch.setattr(routes.pipeline, "process_message", racing_message)
    result = patient.post(f"/api/v1/intakes/{intake['id']}/messages", json={"text":"Hello"})
    assert result.status_code == 409
    assert load_intake(intake["id"])["title"] == "Concurrent saved title"


def test_config_never_contains_keys_or_server_paths(api):
    app, _ = api
    with TestClient(app) as client:
        result = client.get("/api/v1/config")
    assert result.status_code == 200
    assert "api_key" not in result.text
    assert "sqlite" not in result.text
    assert "storage_path" not in result.text
    assert result.json()["default_model"] == "gpt-6-sol"
    assert result.json()["care_team"] == []
    assert "doctor@example.test" not in result.text


def test_interrupted_intake_cannot_be_reviewed(api):
    _, login = api
    client = login("patient@example.test")
    intake = new_intake(client)
    intake["status"] = "interrupted"
    save_intake(intake)
    assert client.post(f"/api/v1/intakes/{intake['id']}/review").status_code == 409


def test_clinician_does_not_receive_nested_history_or_declined_words(api):
    _, login = api
    patient = login("patient@example.test")
    doctor = login("doctor@example.test", "doctor")
    intake = new_intake(patient)
    share(patient, intake["id"])
    stored = load_intake(intake["id"])
    secret = "Private superseded phrase"
    stored["concerns"] = [{"id":"concern", "workflow_id":"WF-01", "title":"Leg pain", "entry_evidence":{"span":secret}, "slots":{"onset":{"label":"Onset", "value":"Last week", "status":"FILLED", "evidence":{"span":secret}, "history":[{"value":secret}]}, "detail":{"label":"Optional detail", "value":secret, "status":"SKIPPED"}}}]
    stored["summary"]["sections"] = [{"entries":[{"label":"Onset", "value":"Last week", "evidence":{"span":secret}}]}]
    stored["audit"] = [{"private":secret}]
    save_intake(stored)
    result = doctor.get(f"/api/v1/clinician/intakes/{intake['id']}")
    assert result.status_code == 200
    assert secret not in result.text
    assert '"history":' not in result.text
    assert '"evidence":' not in result.text
    assert "Last week" in result.text
    assert secret in patient.get(f"/api/v1/intakes/{intake['id']}").text


def test_unreconciled_correction_blocks_approval(api):
    _, login = api
    patient = login("patient@example.test")
    intake = new_intake(patient)
    patient.post(f"/api/v1/intakes/{intake['id']}/review")
    stored = load_intake(intake["id"])
    stored["summary"]["needs_reconciliation"] = True
    save_intake(stored)
    result = patient.post(f"/api/v1/intakes/{intake['id']}/approve", json={"version":1, "doctor_email":"doctor@example.test"})
    assert result.status_code == 409
    assert "reconciled" in result.json()["detail"]
    assert load_intake(intake["id"])["status"] == "review"


def test_handoff_excludes_superseded_aggregate_values():
    from app.product.routes import clinician_public_session
    slot = {'label': 'Original narrative', 'status': 'FILLED', 'value': 'superseded-sensitive-phrase', 'exclude_from_handoff': True}
    result = clinician_public_session({'shared_slots': {'main_concern': slot}, 'concerns': [], 'summary': {'version': 2, 'text': 'Corrected summary'}, 'attachments': []})
    assert 'superseded-sensitive-phrase' not in str(result)
