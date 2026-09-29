"""Patient approval of the summary (C3 responsibility, C6 persistence seam).

The point of these tests is that approval is a statement about a *specific
summary version*, not a flag on the session — so consent can't silently carry
forward onto text the patient never read.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.main import app
from app.core.store import get_store

client = TestClient(app)

REQUIRED = [
    ("chief_complaint", "sore throat"),
    ("symptom_duration_days", 3),
    ("symptom_severity", "mild"),
    ("associated_symptoms", []),
    ("current_medications", []),
    ("allergies", []),
    ("patient_worry", "that it keeps coming back"),
    ("appointment_goal", "a plan"),
    ("clinician_questions", ["Do I need antibiotics?"]),
]


@pytest.fixture(autouse=True)
def _clean_store(database_factory):
    from app.db.session import store_transaction

    def dependency():
        with store_transaction(database_factory) as store:
            yield store

    app.dependency_overrides[get_store] = dependency
    yield
    app.dependency_overrides.pop(get_store, None)


def _completed_session() -> str:
    sid = client.post("/api/sessions", json={}).json()["session_id"]
    for slot_id, value in REQUIRED:
        client.post(
            f"/api/sessions/{sid}/slots/{slot_id}",
            json={"action": "edit", "value": value},
        )
    assert client.post(f"/api/sessions/{sid}/complete").status_code == 200
    return sid


def test_summary_starts_unapproved():
    sid = _completed_session()
    body = client.get(f"/api/sessions/{sid}/summary").json()
    assert body["version"] == 1
    assert body["approved"] is False
    assert body["approved_at"] is None


def test_approving_the_reviewed_version_records_approval():
    sid = _completed_session()
    resp = client.post(
        f"/api/sessions/{sid}/summary/approve",
        json={"version": 1, "approved_by": "patient"},
    )
    assert resp.status_code == 200
    assert resp.json()["approved"] is True
    assert resp.json()["approved_at"] is not None

    # and it is durable, not just in the response
    assert client.get(f"/api/sessions/{sid}/summary").json()["approved"] is True


def test_approving_a_stale_version_is_a_conflict():
    sid = _completed_session()
    resp = client.post(
        f"/api/sessions/{sid}/summary/approve",
        json={"version": 99, "approved_by": "patient"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SUMMARY_VERSION_CONFLICT"
    assert client.get(f"/api/sessions/{sid}/summary").json()["approved"] is False


def test_approving_twice_is_idempotent():
    sid = _completed_session()
    payload = {"version": 1, "approved_by": "patient"}
    first = client.post(f"/api/sessions/{sid}/summary/approve", json=payload).json()
    second = client.post(f"/api/sessions/{sid}/summary/approve", json=payload).json()
    assert first["approved_at"] == second["approved_at"]


def test_cannot_approve_before_completion():
    sid = client.post("/api/sessions", json={}).json()["session_id"]
    resp = client.post(
        f"/api/sessions/{sid}/summary/approve",
        json={"version": 1, "approved_by": "patient"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SUMMARY_NOT_READY"


def test_approval_requires_an_actor():
    sid = _completed_session()
    resp = client.post(
        f"/api/sessions/{sid}/summary/approve",
        json={"version": 1, "approved_by": ""},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"
