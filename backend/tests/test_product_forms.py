"""Form-first preparation, explicit evidence, and API trust boundaries."""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.product import auth, engine, forms
from app.product.database import load_intake, save_intake
from app.product.workflows import WORKFLOWS, SHARED_QUESTIONS
from .test_product_auth import product_env, sign_in


def new(workflows=None, custom=None):
    return forms.initialize(engine.new_intake({"id": "patient", "email": "patient@example.test"},
                                             "gpt-6-sol", workflows or []), custom)


def answer(owner, key, value=None, status="FILLED"):
    return {"concern_id": owner, "key": key, "value": value, "status": status}


def fields(session):
    return [field for group in forms.get_form(session)["groups"] for field in group["fields"]]


def test_no_topic_creates_general_form_and_no_initial_chat():
    session = new()
    assert session["experience_version"] == 2 and session["stage"] == "baseline"
    assert session["concerns"][0]["workflow_id"] == "GENERAL"
    assert session["messages"] == [] and session["current_question"] is None
    assert not session["baseline"]["completed"]
    assert [f["key"] for f in forms.get_form(session)["groups"][1]["fields"]] == ["concern_description"]


def test_custom_and_predefined_concerns_coexist_without_repeated_shared_history():
    session = new(["WF-01", "WF-08"], ["Workplace paperwork", "Family history question"])
    assert [c["workflow_id"] for c in session["concerns"]] == ["WF-01", "WF-08", "GENERAL", "GENERAL"]
    assert session["concerns"][-1]["title"] == "Family history question"
    for key in ("current_medications", "allergies", "appointment_goal", "relevant_history"):
        matches = [f for f in fields(session) if f["key"] == key]
        assert len(matches) == 1 and matches[0]["concern_id"] == "session"


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda w: w["id"])
def test_each_fixed_workflow_exposes_only_its_own_base_bank(workflow):
    session = new([workflow["id"]])
    topic_fields = [f for f in fields(session) if f["concern_id"] != "session"]
    bank = {q["key"] for q in workflow["questions"]} | {"concern_description", "sensitive_permission"}
    # WF-30 is a multi-topic agenda, for which the own-words concern is valid.
    assert all(f["key"] in bank for f in topic_fields)
    assert not any(f["key"] in SHARED_QUESTIONS for f in topic_fields)
    assert all(f["input_type"] in {"textarea", "permission"} for f in topic_fields)


@pytest.mark.parametrize("workflow", [w for w in WORKFLOWS if any(q["key"] == "symptom_frequency" for q in w["questions"])], ids=lambda w: w["id"])
@pytest.mark.parametrize("status,value", [("FILLED", "It is present all the time."), ("UNCERTAIN", None), ("SKIPPED", None)])
def test_fixed_frequency_is_baseline_without_assuming_episodes(workflow, status, value):
    session = new([workflow["id"]])
    concern = session["concerns"][0]
    concern["signals"].pop("episodes", None)
    engine._apply_conditions(session)
    frequency = next(f for f in fields(session) if f["concern_id"] == concern["id"] and f["key"] == "symptom_frequency")
    assert frequency["status"] == "MISSING"
    forms.apply_baseline(session, [answer(concern["id"], "symptom_frequency", value, status)], complete=True)
    slot = concern["slots"]["symptom_frequency"]
    assert slot["status"] == status and slot["value"] == value
    assert slot["baseline"] is True
    assert {"concern_id": concern["id"], "key": "symptom_frequency"} in session["baseline"]["field_keys"]
    assert not concern["signals"].get("episodes", {}).get("present")


def test_form_save_is_exact_evidence_and_does_not_need_a_model():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    original = "  Left calf — mostly after a long walk.  "
    forms.apply_baseline(session, [answer(owner, "leg.pain_site", original)])
    slot = session["concerns"][0]["slots"]["leg.pain_site"]
    assert slot["status"] == "FILLED" and slot["value"] == original
    assert slot["evidence"]["span"] == original
    assert slot["evidence"]["source"] == "patient_form"
    msg = next(m for m in session["messages"] if m["id"] == slot["evidence"]["message_id"])
    assert original in msg["text"]
    assert session["stage"] == "baseline" and session["summary"] is None


def test_invalid_batch_is_atomic_and_cannot_address_another_concern():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    before = deepcopy(session)
    with pytest.raises(ValueError):
        forms.apply_baseline(session, [answer(owner, "leg.pain_site", "Left calf"), answer("someone-else", "concern_description", "Overwrite")])
    assert session == before
    with pytest.raises(ValueError):
        forms.apply_baseline(session, [answer(owner, "leg.pain_site", "Left"), answer(owner, "leg.pain_site", "Right")])
    assert session == before


def test_unknown_skipped_empty_and_deferred_are_distinct_and_not_repeated():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    forms.apply_baseline(session, [answer("session", "current_medications", status="UNCERTAIN"),
                                   answer("session", "allergies", "private declined value", "SKIPPED"),
                                   answer(owner, "leg.pain_site", "   ")], complete=True)
    assert session["shared_slots"]["current_medications"]["status"] == "UNCERTAIN"
    assert session["shared_slots"]["allergies"]["status"] == "SKIPPED"
    assert session["shared_slots"]["allergies"]["value"] is None
    slot = session["concerns"][0]["slots"]["leg.pain_site"]
    assert slot["status"] == "MISSING" and slot["baseline_deferred"]
    assert {"concern_id": owner, "key": "leg.pain_site"} in session["baseline"]["deferred_keys"]
    assert all(engine._owner_slots(session, f["concern_id"])[f["key"]]["baseline"] for f in session["baseline"]["field_keys"])
    assert session["plan"]["coverage"] == 0 and session["plan"]["resolution"] > 0
    engine.build_review(session)
    assert "private declined value" not in session["summary"]["text"]


def test_verbatim_unknown_control_cannot_claim_information_coverage():
    session = new()
    forms.apply_baseline(session, [answer("session", "allergies", "I don't know.")])
    assert session["shared_slots"]["allergies"]["status"] == "UNCERTAIN"
    assert session["plan"]["coverage"] == 0


def test_safety_runs_before_any_form_fields_are_accepted():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    forms.apply_baseline(session, [answer("session", "appointment_goal", "Discuss my appointment"),
                                   answer(owner, "concern_description", "I have chest pain now.")], complete=True)
    assert session["status"] == "interrupted"
    assert session["shared_slots"]["appointment_goal"]["status"] == "MISSING"
    assert session["summary"] is None and session["current_question"] is None
    with pytest.raises(ValueError):
        forms.apply_baseline(session, [], complete=True)


def test_custom_topic_is_subject_to_safety_and_consent_gates():
    assert new(custom=["I have chest pain now"])["status"] == "interrupted"
    session = new(custom=["I withdraw my consent"])
    assert not session["consent"] and session["status"] == "withdrawn"


def test_form_consent_withdrawal_halts_without_accepting_values():
    session = new()
    forms.apply_baseline(session, [answer("session", "appointment_goal", "I withdraw my consent")], complete=True)
    assert session["status"] == "withdrawn" and not session["consent"]
    assert session["shared_slots"]["appointment_goal"]["status"] == "MISSING"


def test_sensitive_details_require_explicit_permission_in_same_batch():
    session = new(["WF-19"])
    owner = session["concerns"][0]["id"]
    with pytest.raises(ValueError, match="Choose Yes"):
        forms.apply_baseline(session, [answer(owner, "menstrual_baseline", "My usual pattern")])
    forms.apply_baseline(session, [answer(owner, "sensitive_permission", "Yes"),
                                   answer(owner, "menstrual_baseline", "My usual pattern")])
    assert session["concerns"][0]["slots"]["menstrual_baseline"]["value"] == "My usual pattern"


def test_draft_correction_replaces_current_value_preserves_history_and_invalidates_summary():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    forms.apply_baseline(session, [answer(owner, "leg.pain_site", "Left calf")], complete=True)
    engine.build_review(session)
    version = session["summary"]["version"]
    forms.apply_baseline(session, [answer(owner, "leg.pain_site", "Right calf")])
    slot = session["concerns"][0]["slots"]["leg.pain_site"]
    assert slot["value"] == "Right calf" and slot["history"][-1]["value"] == "Left calf"
    assert session["summary"] is None and session["stage"] == "baseline"
    engine.build_review(session)
    assert session["summary"]["version"] == version + 1
    assert "Left calf" not in session["summary"]["text"]


def test_identical_form_resubmission_keeps_evidence_revision_and_extraction_cache():
    session = new()
    answers = [answer("session", "current_medications", "None reported"), answer("session", "allergies", status="SKIPPED")]
    forms.apply_baseline(session, answers, complete=True)
    baseline_revision = session["baseline"]["revision"]
    evidence = deepcopy(session["shared_slots"]["current_medications"]["evidence"])
    messages = deepcopy(session["messages"])
    session["baseline"]["extraction_revision"] = baseline_revision
    session["baseline"]["extracted_at"] = "test-timestamp"
    forms.apply_baseline(session, answers, complete=True)
    assert session["baseline"]["revision"] == baseline_revision
    assert session["baseline"]["extraction_revision"] == baseline_revision
    assert session["baseline"]["extracted_at"] == "test-timestamp"
    assert session["shared_slots"]["current_medications"]["evidence"] == evidence
    assert session["messages"] == messages


def test_editing_baseline_removes_derived_medicine_items_and_old_signal_evidence():
    session = new(["WF-01"])
    owner = session["concerns"][0]["id"]
    old = "Vitamin D 1000 IU every morning"
    forms.apply_baseline(session, [answer("session", "current_medications", old)], complete=True)
    msg = {"id": "form_test", "text": old, "created_at": engine._now()}
    engine._accept_extraction(session, {"items": [{"kind": "medication", "concern_id": "session", "name": "Vitamin D",
        "evidence": old, "fields": [{"key": "dose", "value": "1000 IU", "evidence": "1000 IU", "certainty": "stated"}]}],
        "signals": [{"concern_id": owner, "key": "medication_use", "present": True, "evidence": old}]}, msg, False)
    assert session["items"]
    forms.apply_baseline(session, [answer("session", "current_medications", "None")], complete=True)
    assert session["items"] == []
    assert not any(key.startswith("medication.") for key in session["shared_slots"])
    assert "medication_use" not in session["concerns"][0]["signals"]
    engine.build_review(session)
    assert "Vitamin D" not in session["summary"]["text"]


@pytest.fixture
def form_api(product_env, monkeypatch):
    from app.product import routes
    calls = []
    def followup(session):
        calls.append(session["id"])
        session["stage"] = "followup"
        return session
    monkeypatch.setattr(routes.pipeline, "start_followup", followup)
    monkeypatch.setattr(routes.pipeline, "build_review", engine.build_review)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(routes.router, prefix="/api/v1")
    clients = []
    def login(email="patient@example.test", role="patient"):
        client = TestClient(app, headers={"Origin": "http://testserver"})
        sign_in(client, product_env, email, role)
        clients.append(client)
        return client
    yield login, calls
    for client in clients:
        client.close()


def test_api_custom_none_validation_and_followup_gate(form_api):
    login, calls = form_api
    client = login()
    created = client.post("/api/v1/intakes", json={"consent": True, "custom_concerns": ["My paperwork"]})
    assert created.status_code == 201
    session = created.json()
    assert session["concerns"][0]["title"] == "My paperwork"
    url = f"/api/v1/intakes/{session['id']}"
    assert client.post(url + "/followup").status_code == 409
    assert client.put(url + "/baseline", json={"answers": [], "complete": True}).status_code == 200
    assert calls == [session["id"]]
    assert client.post(url + "/followup").status_code == 200
    assert client.post("/api/v1/intakes", json={"consent": True, "custom_concerns": ["   "]}).status_code == 422
    assert client.post("/api/v1/intakes", json={"consent": True, "custom_concerns": ["x" * 151]}).status_code == 422


def test_api_form_owner_csrf_stale_revision_and_whole_batch_validation(form_api):
    login, _ = form_api
    patient = login()
    other = login("other@example.test")
    session = patient.post("/api/v1/intakes", json={"consent": True, "workflow_ids": ["WF-01"]}).json()
    url = f"/api/v1/intakes/{session['id']}"
    form = patient.get(url + "/form").json()
    assert other.get(url + "/form").status_code == 404
    assert other.put(url + "/baseline", json={"answers": []}).status_code == 404
    assert patient.put(url + "/baseline", json={"answers": []}, headers={"Origin": "https://evil.test"}).status_code == 403
    payload = {"answers": [answer("session", "allergies", "None reported")], "revision": form["revision"]}
    assert patient.put(url + "/baseline", json=payload).status_code == 200
    assert patient.put(url + "/baseline", json=payload).status_code == 409
    payload = {"answers": [answer("session", "allergies", "Overwrite"), answer("session", "invented_key", "bad")]}
    assert patient.put(url + "/baseline", json=payload).status_code == 422
    assert load_intake(session["id"])["shared_slots"]["allergies"]["value"] == "None reported"


def test_api_approved_baseline_is_immutable_and_withdrawal_allows_edit(form_api):
    login, _ = form_api
    client = login()
    session = client.post("/api/v1/intakes", json={"consent": True}).json()
    url = f"/api/v1/intakes/{session['id']}"
    summary = client.post(url + "/review").json()["summary"]
    assert client.post(url + "/approve", json={"version": summary["version"], "doctor_email": "doctor@example.test"}).status_code == 200
    assert client.put(url + "/baseline", json={"answers": []}).status_code == 409
    assert client.post(url + "/followup").status_code == 409
    assert client.post(url + "/withdraw").status_code == 200
    assert client.put(url + "/baseline", json={"answers": []}).status_code == 200


def test_api_safety_never_calls_followup(form_api):
    login, calls = form_api
    client = login()
    session = client.post("/api/v1/intakes", json={"consent": True}).json()
    url = f"/api/v1/intakes/{session['id']}"
    result = client.put(url + "/baseline", json={"answers": [answer("session", "appointment_goal", "I have chest pain now")], "complete": True})
    assert result.status_code == 200 and result.json()["status"] == "interrupted"
    assert calls == []
    assert client.put(url + "/baseline", json={"answers": []}).status_code == 409


def test_api_legacy_draft_form_uses_stable_general_concern(form_api):
    login, _ = form_api
    client = login()
    user = client.get("/api/v1/auth/me").json()["user"]
    legacy = engine.new_intake(user, "gpt-6-sol", [])
    save_intake(legacy)
    url = f"/api/v1/intakes/{legacy['id']}"
    first = client.get(url + "/form").json()
    second = client.get(url + "/form").json()
    assert first == second and load_intake(legacy["id"])["concerns"] == []
    field = first["groups"][1]["fields"][0]
    result = client.put(url + "/baseline", json={"answers": [answer(field["concern_id"], field["key"], "Prepare workplace paperwork")]})
    assert result.status_code == 200
    assert result.json()["concerns"][0]["slots"]["concern_description"]["value"] == "Prepare workplace paperwork"


def test_api_concurrent_ai_step_cannot_overwrite_newer_saved_form(form_api, monkeypatch):
    from app.product import routes
    login, _ = form_api
    client = login()
    session = client.post("/api/v1/intakes", json={"consent": True}).json()
    def racing_followup(state):
        newer = load_intake(state["id"])
        newer["title"] = "Newer saved version"
        save_intake(newer)
        return state
    monkeypatch.setattr(routes.pipeline, "start_followup", racing_followup)
    result = client.put(f"/api/v1/intakes/{session['id']}/baseline", json={"answers": [], "complete": True})
    assert result.status_code == 409
    assert load_intake(session["id"])["title"] == "Newer saved version"
