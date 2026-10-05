"""Guided controls add optional presentation without changing evidence semantics."""
from copy import deepcopy

import pytest

from app.product import engine, forms
from app.product.database import load_intake
from app.product.workflows import WORKFLOWS
from .test_product_auth import product_env  # noqa: F401 (pytest fixture)
from .test_product_forms import answer, form_api, new  # noqa: F401 (pytest fixture)


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda w: w["id"])
def test_every_workflow_has_useful_optional_guidance_without_default_facts(workflow):
    session = new([workflow["id"]])
    before = deepcopy(session)
    form = forms.get_form(session)
    assert session == before
    shared, group = form["groups"]
    assert shared["workflow_id"] is None
    assert group["workflow_id"] == ("GENERAL" if workflow["id"] == "WF-30" else workflow["id"])
    # WF-30 is agenda mode, whose bank lives in shared appointment fields.
    eligible = shared["fields"] if workflow["id"] == "WF-30" else group["fields"]
    guided = [field for field in eligible if field.get("presentation")]
    assert guided, "Every fixed workflow should offer a relevant answer aid."
    for field in shared["fields"] + group["fields"]:
        assert field["value"] is None and field["status"] == "MISSING"
        aid = field.get("presentation")
        if not aid:
            continue
        assert aid["kind"] in {"choices", "body_map", "scale"}
        assert isinstance(aid["multiple"], bool)
        assert aid["options"] and isinstance(aid["helper"], str)
        assert len({option["value"] for option in aid["options"]}) == len(aid["options"])
        assert len({option["label"] for option in aid["options"]}) == len(aid["options"])
        assert all(option["value"] and option["label"] and "selected" not in option for option in aid["options"])
        assert "question" not in aid  # The form's question remains the accessible prompt.
        if aid["kind"] == "body_map":
            assert aid["illustration"] in {"body", "legs", "back", "neck_shoulders", "arms_hands", "head", "abdomen"}
            assert len({option["region"] for option in aid["options"]}) == len(aid["options"])
            assert "your own body" in aid["helper"]


def test_answer_aids_do_not_replace_exact_dates_readings_or_medicine_details():
    form = forms.get_form(new(["WF-08", "WF-24", "WF-25", "WF-27", "WF-28"]))
    exact_fields = {"current_medications", "allergies", "relevant_history",
                    "symptom_onset", "bp_readings", "glucose_readings",
                    "medication_actual_use", "medication_focus",
                    "previous_tests.test_date", "sleep.usual_bedtime", "sleep.usual_wake_time"}
    present = [field for group in form["groups"] for field in group["fields"] if field["key"] in exact_fields]
    assert len(present) >= 8
    assert all("presentation" not in field for field in present)


def test_frequency_uses_topic_appropriate_units_and_cannot_select_conflicting_options():
    form = forms.get_form(new(["WF-01", "WF-08"]))
    leg, sleep = [next(f for f in group["fields"] if f["key"] == "symptom_frequency")["presentation"]
                  for group in form["groups"][1:]]
    assert leg["multiple"] is sleep["multiple"] is False
    assert "Present all the time" in [o["value"] for o in leg["options"]]
    assert all("night" in o["value"] or "week" in o["value"] for o in sleep["options"])
    # A caller changing its response cannot contaminate a later patient's form.
    sleep["options"][0]["value"] = "changed by a caller"
    again = forms.get_form(new(["WF-08"]))["groups"][1]
    assert "changed by a caller" not in str(again)


def test_body_map_selection_and_custom_detail_save_exactly_and_remain_correctable(form_api):
    login, _ = form_api
    client = login()
    session = client.post("/api/v1/intakes", json={"consent": True, "workflow_ids": ["WF-01"]}).json()
    url = f"/api/v1/intakes/{session['id']}"
    form = client.get(url + "/form").json()
    group = form["groups"][1]
    field = next(f for f in group["fields"] if f["key"] == "leg.pain_site")
    options = {option["region"]: option for option in field["presentation"]["options"]}
    assert options["left_calf"]["value"] == "Left calf"
    assert options["right_knee"]["value"] == "Right knee"
    assert options["left_shin"]["value"] == "Left shin"
    assert options["right_shin"]["value"] == "Right shin"
    raw = "Selected options:\n- Left calf\n- Right knee\n\nAdditional details:\n  Mainly at the outside of my calf.  "
    response = client.put(url + "/baseline", json={"revision": form["revision"], "answers": [answer(group["id"], field["key"], raw)]})
    assert response.status_code == 200
    saved = load_intake(session["id"])
    slot = saved["concerns"][0]["slots"][field["key"]]
    assert slot["value"] == slot["evidence"]["span"] == raw
    assert slot["evidence"]["source"] == "patient_form"
    assert saved["shared_slots"]["allergies"]["status"] == "MISSING"
    retrieved = client.get(url + "/form").json()
    assert next(f for f in retrieved["groups"][1]["fields"] if f["key"] == field["key"])["value"] == raw
    # Suggestions are never an allowlist: new locations and languages remain valid.
    replacement = "Actually only the outside of my left shin — 左侧。"
    response = client.put(url + "/baseline", json={"revision": retrieved["revision"], "answers": [answer(group["id"], field["key"], replacement)]})
    assert response.status_code == 200
    slot = load_intake(session["id"])["concerns"][0]["slots"][field["key"]]
    assert slot["value"] == replacement and slot["history"][-1]["value"] == raw


def test_choices_do_not_bypass_unknown_declined_or_sensitive_permission():
    session = new(["WF-19", "WF-08"])
    menstrual, sleep = session["concerns"]
    field = next(f for f in forms.get_form(session)["groups"][1]["fields"] if f["key"] == "menstrual_focus")
    assert field["presentation"] and field["requires_permission"]
    selected = "Selected options:\n- Timing or regularity"
    before = deepcopy(session)
    with pytest.raises(ValueError, match="Choose Yes"):
        forms.apply_baseline(session, [answer(menstrual["id"], "menstrual_focus", selected)])
    assert session == before
    forms.apply_baseline(session, [answer(menstrual["id"], "sensitive_permission", "Yes"),
                                   answer(menstrual["id"], "menstrual_focus", selected),
                                   answer(sleep["id"], "sleep.main_difficulty", status="UNCERTAIN"),
                                   answer(sleep["id"], "symptom_frequency", status="SKIPPED")], complete=True)
    assert menstrual["slots"]["menstrual_focus"]["value"] == selected
    assert sleep["slots"]["sleep.main_difficulty"]["value"] is None
    assert sleep["slots"]["sleep.main_difficulty"]["status"] == "UNCERTAIN"
    assert sleep["slots"]["symptom_frequency"]["status"] == "SKIPPED"
    engine.build_review(session)
    assert not any(o["value"] in session["summary"]["text"] for o in
                   next(f for f in forms.get_form(session)["groups"][2]["fields"] if f["key"] == "symptom_frequency")["presentation"]["options"])
