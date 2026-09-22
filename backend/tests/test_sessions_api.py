import pytest
from fastapi.testclient import TestClient

from app.core.main import app
from app.core.store import get_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_store(database_factory):
    from app.db.session import store_transaction

    def dependency():
        with store_transaction(database_factory) as store:
            yield store

    app.dependency_overrides[get_store] = dependency
    yield
    app.dependency_overrides.pop(get_store, None)


def _new_session() -> str:
    r = client.post("/api/sessions", json={})
    assert r.status_code == 201
    return r.json()["session_id"]


def test_create_and_fetch_session():
    sid = _new_session()
    r = client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_progress"
    assert body["schema_version"] == "0.2"
    assert "chief_complaint" in body["slots"]


def test_unknown_session_returns_envelope():
    r = client.get("/api/sessions/nope")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "SESSION_NOT_FOUND"
    assert err["request_id"].startswith("req_")


def test_malformed_json_body_still_uses_the_error_envelope():
    sid = _new_session()
    r = client.post(
        f"/api/sessions/{sid}/messages",
        content=b'{"text": }',
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "REQUEST_VALIDATION_FAILED"
    assert err["request_id"].startswith("req_")


def test_wrong_field_type_still_uses_the_error_envelope():
    sid = _new_session()
    r = client.post(f"/api/sessions/{sid}/messages", json={"text": 123})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_message_extracts_and_returns_next_prompt():
    sid = _new_session()
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"text": "I've had a fever and sore throat for 3 days"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "associated_symptoms" in body["updated_slots"]
    assert body["next_prompt"] is not None
    assert body["safety"]["triggered"] is False
    assert body["completeness"]["resolution"] == 0.0


def test_safety_interruption_short_circuits_the_turn():
    sid = _new_session()
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"text": "I have really bad chest pain right now"},
    )
    body = r.json()
    assert body["safety"]["triggered"] is True
    assert body["safety"]["category"] == "cardiac"
    assert body["stopped"] is True
    assert body["updated_slots"] == []
    assert body["next_prompt"] is None


def test_confirm_edit_skip_slot_flow():
    sid = _new_session()
    client.post(f"/api/sessions/{sid}/messages", json={"text": "sore throat"})

    # confirm the extracted chief_complaint candidate
    r = client.post(
        f"/api/sessions/{sid}/slots/chief_complaint", json={"action": "confirm"}
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "accepted"

    # edit requires a value
    r = client.post(f"/api/sessions/{sid}/slots/symptom_severity", json={"action": "edit"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SLOT_VALIDATION_FAILED"

    r = client.post(
        f"/api/sessions/{sid}/slots/symptom_severity",
        json={"action": "edit", "value": "moderate"},
    )
    assert r.status_code == 200

    # invalid enum value is rejected
    r = client.post(
        f"/api/sessions/{sid}/slots/symptom_severity",
        json={"action": "edit", "value": "extreme"},
    )
    assert r.status_code == 422

    # skip an optional slot
    r = client.post(
        f"/api/sessions/{sid}/slots/past_conditions", json={"action": "skip"}
    )
    assert r.json()["outcome"] == "accepted"

    # "I don't know" is a distinct action/status from skip
    r = client.post(
        f"/api/sessions/{sid}/slots/current_medications", json={"action": "unknown"}
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "accepted"
    state = client.get(f"/api/sessions/{sid}").json()
    assert state["slots"]["current_medications"]["status"] == "unknown"
    assert state["slots"]["past_conditions"]["status"] == "skipped"

    # the audit trail is exposed on the session and skips rejected attempts
    events = {(e["slot_id"], e["event"]) for e in state["history"]}
    assert ("chief_complaint", "confirmed") in events
    assert ("symptom_severity", "confirmed") in events
    assert ("past_conditions", "skipped") in events
    assert ("current_medications", "marked_unknown") in events
    assert len(state["history"]) == 4  # the rejected "extreme" edit left no trace

    # nonexistent slot
    r = client.post(f"/api/sessions/{sid}/slots/not_real", json={"action": "skip"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "SLOT_NOT_FOUND"


def test_full_flow_to_summary():
    sid = _new_session()
    for slot_id, value in [
        ("chief_complaint", "sore throat"),
        ("symptom_duration_days", 3),
        ("symptom_severity", "mild"),
        ("current_medications", []),
        ("allergies", []),
    ]:
        r = client.post(
            f"/api/sessions/{sid}/slots/{slot_id}",
            json={"action": "edit", "value": value},
        )
        assert r.status_code == 200

    # summary not available before completion
    assert client.get(f"/api/sessions/{sid}/summary").status_code == 409

    r = client.post(f"/api/sessions/{sid}/complete")
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["summary_ref"] == f"sum_{sid}"

    r = client.get(f"/api/sessions/{sid}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["sections"]["Main reason for the visit"] == "sore throat"
    assert len(body["patient_questions"]) >= 1

    # second complete is a conflict
    assert client.post(f"/api/sessions/{sid}/complete").status_code == 409
    # messages after completion are rejected
    assert (
        client.post(f"/api/sessions/{sid}/messages", json={"text": "hi"}).status_code
        == 409
    )


def test_stops_when_all_required_addressed_via_messages():
    sid = _new_session()
    r = client.post(
        f"/api/sessions/{sid}/messages",
        json={"text": "no medications and no known allergies, mild pain for 2 days"},
    )
    body = r.json()
    # duration + severity + medications + allergies extracted as candidates,
    # still need confirmation, so not stopped yet
    assert body["stopped"] is False
