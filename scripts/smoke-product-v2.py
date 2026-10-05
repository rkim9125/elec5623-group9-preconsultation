"""Explicit LIVE OpenAI integration check using synthetic bilingual form data.

This consumes API usage. It never authenticates, sends email, or touches the app
database. The resulting synthetic record can seed the isolated browser fixture.
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.product import engine, forms, pipeline
from app.product.routes import clinician_public_session


def run():
    session = engine.new_intake(
        {"id": "synthetic-v2-smoke", "email": "synthetic@example.test", "name": "Alex Morgan"},
        "gpt-6-sol", ["WF-01", "WF-08"], "Three concerns for my planned appointment")
    forms.initialize(session, ["Work certificate"])
    shared = {
        "appointment_goal": "I want to discuss my sleep first, then my leg and paperwork.",
        "priority_concern": "Sleep difficulties first.",
        "current_medications": "Vitamin D 1000 IU daily.",
        "allergies": "No known medicine allergies.",
        "patient_worry": "I worry about feeling tired during early meetings.",
        "clinician_questions": "What should I record about my sleep before our next appointment? What paperwork does my employer need?",
    }
    leg = {
        "concern_description": "我的左小腿走很久后有酸痛，已经三周。",
        "leg.pain_site": "Left calf.", "leg.pain_character": "A dull ache.",
        "symptom_frequency": "After long walks, around twice a week.",
        "leg.activity_context": "After walking for around an hour.",
        "leg.change_factors": "It settles when I rest.",
        "functional_impact": "I take breaks during longer walks.",
    }
    sleep = {
        "concern_description": "For two months I have difficulty falling asleep and sometimes wake during the night.",
        "sleep.main_difficulty": "Falling asleep, and sometimes waking during the night.",
        "symptom_frequency": "Around three nights each week.",
        "sleep.usual_bedtime": "Around 11 pm.", "sleep.usual_wake_time": "Around 7 am.",
        "sleep.observed_context": "Before early work meetings.",
        "functional_impact": "I feel tired in early meetings.",
        "previous_actions": "I tried keeping the same bedtime for two weeks.",
    }
    concerns = {c["id"]: c for c in session["concerns"]}
    answers = []
    for group in forms.get_form(session)["groups"]:
        for field in group["fields"]:
            owner, key = field["concern_id"], field["key"]
            values = shared if owner == "session" else (
                leg if concerns[owner]["workflow_id"] == "WF-01" else
                sleep if concerns[owner]["workflow_id"] == "WF-08" else
                {"concern_description": "I would like to ask about a work certificate and what paperwork is needed."})
            if key in values:
                answers.append({"concern_id": owner, "key": key, "value": values[key], "status": "FILLED"})
            elif key == "relevant_history":
                answers.append({"concern_id": owner, "key": key, "value": None, "status": "UNCERTAIN"})
    forms.apply_baseline(session, answers, complete=True)
    try:
        pipeline.start_followup(session)
        assert session["assistant"]["mode"] in {"live", "ready"}, session["assistant"]["overview"]
        baseline = set(session["baseline"]["field_ids"])
        asked = []
        for turn in range(2):
            question = session.get("current_question")
            if not question:
                break
            identity = f"{question.get('concern_id', 'session')}:{question['key']}"
            assert identity not in baseline and identity not in asked
            asked.append(identity)
            if turn == 0:
                responses = {
                    "sleep.waking_duration": "I am usually awake for around twenty minutes when I wake during the night.",
                    "symptom_onset": "The sleep difficulty began about two months ago; the calf ache started about three weeks ago.",
                    "symptom_duration": "The sleep difficulty has lasted about two months; the calf ache has lasted about three weeks.",
                    "symptom_course": "The pattern has stayed much the same.",
                    "previous_actions.response": "I have not noticed a clear difference from keeping the same bedtime.",
                    "severity": "It feels bothersome to me, but I can still carry out my usual activities.",
                }
                answer = responses.get(question["key"])
                pipeline.process_message(session, answer or "I am not sure.", "answer" if answer else "unknown")
            else:
                pipeline.process_message(session, "", "skip")
        pipeline.build_review(session)
        synthesis = session["summary"]["synthesis"]
        assert synthesis["status"] == "live", synthesis.get("message")
        assert len(synthesis["concern_summaries"]) == 3
        assert synthesis["patient_overview"] and synthesis["clinician_brief"]
        bilingual_source_preserved = any("三周" in str(source.get("value")) for source in synthesis["sources"])
        assert bilingual_source_preserved
        before = session["summary"]["version"]
        pipeline.build_review(session, correction="Please remove Vitamin D and all of its dose and frequency details from my record.")
        assert not session["summary"]["needs_reconciliation"]
        assert session["summary"]["synthesis"]["status"] == "live", session["summary"]["synthesis"].get("message")
        assert session["summary"]["version"] > before
        assert "vitamin d" not in json.dumps(clinician_public_session(session)).lower()
        assert len(session["summary"]["synthesis"]["concern_summaries"]) == 3
        assert any(concern["title"] == "Work certificate" for concern in session["summary"]["synthesis"]["concern_summaries"])
    except Exception:
        (ROOT / ".local/v2-live-smoke-failure.json").write_text(json.dumps(session, ensure_ascii=False, indent=2))
        raise
    (ROOT / ".local/v2-live-smoke.json").write_text(json.dumps(session, ensure_ascii=False, indent=2))
    report = {
        "passed": True, "model": session["model"], "concerns": len(session["concerns"]),
        "followup_turns_exercised": len(asked), "baseline_not_repeated": True,
        "live_synthesis": True, "bilingual_source_preserved": bilingual_source_preserved,
        "correction_reconciled": True, "removed_medicine_absent": True,
        "unrelated_custom_concern_preserved": True,
        "summary_version": session["summary"]["version"], "operations": session["ai_activity"],
    }
    (ROOT / ".local/v2-live-report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
