"""Patient-authored baseline forms backed by the existing evidence state.

The form is the fixed workflow bank, not the fully expanded adaptive schema.
Direct answers are explicit evidence; they never need model extraction to save.
"""
from __future__ import annotations

from copy import deepcopy

from . import engine, presentation
from .workflows import CORE_QUESTIONS, SHARED_QUESTIONS, get_workflow

SHARED_FIELDS = (
    "appointment_goal", "current_medications", "allergies", "relevant_history",
    "patient_worry", "clinician_questions",
)
# These are alternate ways of asking for the agenda already captured by topic
# selection, the individual descriptions and the shared appointment goal.
AGENDA_ALIASES = ("main_concern", "agenda_items", "preparation_focus", "topic_clarification")
LABELS = {
    "concern_description": "In your own words", "appointment_goal": "Your appointment goal",
    "current_medications": "Medicines and supplements", "allergies": "Allergies and reactions",
    "relevant_history": "Relevant medical history", "patient_worry": "What matters most to you",
    "clinician_questions": "Questions for your clinician", "priority_concern": "Your first priority",
    "sensitive_permission": "Permission to include personal details",
}


def _editable(session: dict) -> None:
    if not session.get("consent"):
        raise ValueError("Consent was withdrawn. Begin a new preparation to continue.")
    if session.get("status") in {"approved", "interrupted"}:
        raise ValueError("This preparation cannot accept form changes in its current state.")


def initialize(session: dict, custom_concerns: list[str] | None = None) -> dict:
    """Start a new form-first session without an initial interview question."""
    _editable(session)
    for title in dict.fromkeys(custom_concerns or []):
        engine._add_concern(session, "GENERAL", title,
                            {"source": "patient_selection", "title": title})
    if not session["concerns"]:
        engine._add_concern(session, "GENERAL", "Something else / my own concern",
                            {"source": "patient_selection", "workflow_id": "GENERAL"})
    session.update(experience_version=2, stage="baseline", baseline={"completed": False})
    session["agenda_mode"] = session.get("agenda_mode", False) or len(session["concerns"]) > 1
    session["messages"] = []
    session["current_question"] = None
    session["plan"]["next_target"] = None
    session["assistant"] = {"mode": "ready", "overview": "Complete the preparation form in your own time.",
                            "focus": "Your appointment", "rationale": "AI will check for useful follow-up details after your form.",
                            "suggested_topics": [], "questions_remaining": 0, "question_count": 0}
    engine._apply_conditions(session)
    engine._metrics(session)
    # A custom topic is patient text and passes the same pre-extraction gate.
    for title in custom_concerns or []:
        if engine.check_safety(title).triggered or engine._WITHDRAW.search(title):
            msg = engine._message(session, "patient", title)
            _gate(session, msg)
            break
    return session


def _field(owner: str, key: str, slot: dict, definition: dict | None = None, *, permission: bool = False,
           workflow_id: str | None = None) -> dict:
    definition = definition or {}
    guidance = presentation.for_field(workflow_id, key)
    question = definition.get("question", slot.get("question", ""))
    if guidance:
        question = guidance.pop("question", question)
    field = {"concern_id": owner, "key": key,
            "label": LABELS.get(key, definition.get("label", slot["label"])),
            "question": question,
            "value": None if slot["status"] in {"SKIPPED", "MISSING", "NOT_APPLICABLE"} else slot.get("value"),
            "status": "MISSING" if slot["status"] == "NOT_APPLICABLE" else slot["status"],
            "required": key in {"concern_description", "appointment_goal", "current_medications", "allergies"},
            "input_type": "permission" if key == "sensitive_permission" else "textarea",
            "requires_permission": permission}
    if guidance:
        field["presentation"] = guidance
    return field


def get_form(session: dict) -> dict:
    """Return a stable, concise form with shared background collected once."""
    groups = []
    shared = list(SHARED_FIELDS)
    if len(session.get("concerns", [])) > 1 or session.get("agenda_mode"):
        shared.insert(1, "priority_concern")
    groups.append({"id": "shared", "workflow_id": None, "title": "Your appointment & background",
                   "description": "These details apply across all your topics. Share what you know; you can leave anything for later.",
                   "fields": [_field("session", key, session["shared_slots"][key]) for key in shared]})
    for concern in session.get("concerns", []):
        workflow = get_workflow(concern["workflow_id"])
        sensitive = concern["workflow_id"] == "WF-19"
        rows = [{"key": "concern_description", "question": CORE_QUESTIONS["concern_description"]}]
        if workflow:
            rows.extend(workflow["questions"])
        if sensitive:
            rows.insert(0, {"key": "sensitive_permission"})
        fields, seen = [], set()
        for row in rows:
            key = row["key"]
            if key in seen or key in SHARED_QUESTIONS or key == "summary_review":
                continue
            seen.add(key)
            slot = concern["slots"].get(key)
            if slot is None:
                continue
            # Conditional-only information belongs to adaptive follow-up. A
            # sensitive module can show fixed fields behind explicit permission.
            generic_frequency = key == "symptom_frequency"
            if slot.get("condition") and slot["status"] == "NOT_APPLICABLE" and not generic_frequency:
                continue
            if slot["status"] == "NOT_APPLICABLE" and not sensitive and not generic_frequency:
                continue
            fields.append(_field(concern["id"], key, slot, row,
                                 permission=sensitive and key != "sensitive_permission",
                                 workflow_id=concern["workflow_id"]))
        groups.append({"id": concern["id"], "workflow_id": concern["workflow_id"], "title": concern["title"],
                       "description": "Include the details you would like your clinician to understand.", "fields": fields})
    return {"groups": groups, "completed": bool(session.get("baseline", {}).get("completed"))}


def _gate(session: dict, msg: dict) -> bool:
    if engine._interrupt(session, msg):
        return True
    if engine._WITHDRAW.search(msg["text"]):
        session.update(consent=False, status="withdrawn", summary=None, current_question=None)
        session["plan"].update(next_target=None, stop_reason="CONSENT_WITHDRAWN")
        engine._message(session, "assistant", "Your consent has been withdrawn. Preparation has stopped and no new handoff will be generated.")
        return True
    return False


def _invalidate_derived(session: dict, changed: list[dict]) -> None:
    """Remove current derived facts whose source form answer was replaced.

    Audit/history remain private, but descendants may not survive into a fresh
    handoff. Direct answers and independently updated conversational facts keep
    their own evidence. The pipeline also reconciles its extraction fingerprint.
    """
    prior = []
    for answer in changed:
        slot = engine._owner_slots(session, answer["concern_id"])[answer["key"]]
        if slot.get("value"):
            prior.append((answer["concern_id"], answer["key"], slot["value"], slot.get("evidence") or {}))

    def stale(evidence: dict | None) -> bool:
        if not isinstance(evidence, dict):
            return False
        is_form_derivative = evidence.get("source") == "saved_baseline_form" or str(evidence.get("message_id", "")).startswith("form_")
        for owner, key, value, old in prior:
            sources = evidence.get("form_sources", [])
            if is_form_derivative and {"concern_id": owner, "key": key} in sources:
                return True
            if is_form_derivative and evidence.get("span") and evidence["span"] in value:
                return True
            if evidence.get("source") not in {"patient_form", "direct_patient_response"} and evidence.get("message_id") == old.get("message_id") and evidence.get("span") and evidence["span"] in value:
                return True
        return False

    removed = []
    for item in list(session.get("items", [])):
        if stale(item.get("evidence")):
            slots = engine._owner_slots(session, item["concern_id"])
            for key in item.get("fields", {}).values():
                slots.pop(key, None)
            session["items"].remove(item)
            removed.append({"kind": "item", "id": item["id"]})
    for owner, slots in [("session", session["shared_slots"])] + [(c["id"], c["slots"]) for c in session["concerns"]]:
        for key, slot in slots.items():
            if stale(slot.get("evidence")):
                engine._update_slot(slot, None, "MISSING", None, correction=True)
                slot.pop("exclude_from_handoff", None)
                removed.append({"kind": "slot", "concern_id": owner, "key": key})
    for concern in session["concerns"]:
        for key, signal in list(concern.get("signals", {}).items()):
            if stale(signal.get("evidence")):
                del concern["signals"][key]
                removed.append({"kind": "signal", "concern_id": concern["id"], "key": key})
    if removed:
        session.setdefault("audit", []).append({"event": "form_derived_facts_invalidated", "removed": removed})


def apply_baseline(session: dict, answers: list[dict], *, complete: bool = False) -> dict:
    """Validate the whole batch, then save exact form evidence atomically.

    API code persists only the successfully returned state. This helper also
    validates before mutating so invalid batches cannot partially change state.
    """
    _editable(session)
    if not session.get("concerns"):
        # Legacy free-text drafts can adopt the new form without losing history.
        session = deepcopy(session)
        engine._add_concern(session, "GENERAL", "Your appointment concern")
    form = get_form(session)
    fields = {(field["concern_id"], field["key"]): field
              for group in form["groups"] for field in group["fields"]}
    validated, seen = [], set()
    for answer in answers:
        owner, key = answer.get("concern_id", "session"), answer.get("key")
        identity = (owner, key)
        if identity not in fields:
            raise ValueError("One or more answers do not belong to this preparation form. Refresh the form and try again.")
        if identity in seen:
            raise ValueError("Provide only one answer for each preparation field.")
        seen.add(identity)
        status, value = answer.get("status", "FILLED"), answer.get("value")
        if status not in {"FILLED", "UNCERTAIN", "SKIPPED", "MISSING"}:
            raise ValueError("Choose an answer, unknown, prefer not to answer, or leave the field empty.")
        if value is not None and (not isinstance(value, str) or len(value) > 6000):
            raise ValueError("Keep each preparation answer under 6,000 characters.")
        if isinstance(value, str) and not value.strip():
            value = None
        if status == "MISSING" and value is not None:
            raise ValueError("An unanswered field cannot contain a value.")
        if status == "FILLED" and value is None:
            status = "MISSING"
        elif status == "FILLED" and engine._UNKNOWN.match(value):
            status = "UNCERTAIN"
        elif status == "FILLED" and engine._SKIP.match(value):
            status = "SKIPPED"
        if key == "sensitive_permission" and status == "FILLED" and not engine._YES.match(value or ""):
            status = "SKIPPED" if engine._NO.match(value or "") else "UNCERTAIN"
        validated.append({"concern_id": owner, "key": key, "value": value, "status": status})
    if sum(len(answer.get("value") or "") for answer in validated) > 200000:
        raise ValueError("The preparation form is too long. Shorten the answers before saving.")
    pending = {(answer["concern_id"], answer["key"]): answer for answer in validated}
    for answer in validated:
        field = fields[(answer["concern_id"], answer["key"])]
        if not field["requires_permission"] or answer["status"] == "MISSING":
            continue
        slots = engine._owner_slots(session, answer["concern_id"])
        permission = pending.get((answer["concern_id"], "sensitive_permission"), slots["sensitive_permission"])
        permitted = permission["status"] == "FILLED" and bool(engine._YES.match(permission.get("value") or ""))
        if not permitted and answer["status"] in {"FILLED", "UNCERTAIN"}:
            raise ValueError("Choose Yes to include personal details, or leave those details empty.")
    changed = [a for a in validated if
               ("MISSING" if engine._owner_slots(session, a["concern_id"])[a["key"]]["status"] == "NOT_APPLICABLE" else engine._owner_slots(session, a["concern_id"])[a["key"]]["status"],
                engine._owner_slots(session, a["concern_id"])[a["key"]].get("value")) !=
               (a["status"], a["value"] if a["status"] not in {"SKIPPED", "MISSING"} else None)]
    # Preserve source text even for an explicit refusal, but never put declined
    # words in slot values or handoff. Safety runs before any field is accepted.
    lines = [f"{fields[(a['concern_id'], a['key'])]['label']}: {a.get('value') or ('I am not sure.' if a['status'] == 'UNCERTAIN' else 'Prefer not to answer.' if a['status'] == 'SKIPPED' else 'Left for later.')}"
             for a in validated]
    text = "Preparation form\n" + "\n".join(lines)
    needs_gate = engine.check_safety(text).triggered or engine._WITHDRAW.search(text)
    msg = engine._message(session, "patient", text) if changed or needs_gate else None
    if msg and _gate(session, msg):
        return session
    _invalidate_derived(session, changed)
    changes = []
    for answer in changed:
        owner, key, status = answer["concern_id"], answer["key"], answer["status"]
        slot = engine._owner_slots(session, owner)[key]
        value = answer["value"] if status not in {"SKIPPED", "MISSING"} else None
        span = answer.get("value") or ("I am not sure." if status == "UNCERTAIN" else "Prefer not to answer." if status == "SKIPPED" else "Left for later.")
        evidence = engine._provenance(msg, span, "patient_form")
        evidence.update(concern_id=owner, key=key)
        before = deepcopy(slot)
        engine._update_slot(slot, value, status, evidence, correction=True)
        # Directly editing a field supersedes any older broad narrative that
        # might still carry its previous value, while keeping private history.
        if before.get("value") and before["value"] != value:
            session["_has_corrections"] = True
            session["shared_slots"]["main_concern"]["exclude_from_handoff"] = True
            concern = engine._concern(session, owner)
            if concern and key != "concern_description":
                concern["slots"]["concern_description"]["exclude_from_handoff"] = True
        if key == "concern_description" and status == "FILLED":
            slot.pop("exclude_from_handoff", None)
        concern = engine._concern(session, owner)
        if concern:
            concern["preparation_status"] = "in progress"
            if key == "sensitive_permission":
                granted = status == "FILLED" and bool(engine._YES.match(value or ""))
                concern["signals"]["sensitive_permission"] = {"present": granted, "evidence": evidence}
                if not granted and status == "FILLED":
                    slot["status"] = "SKIPPED" if engine._NO.match(value or "") else "UNCERTAIN"
        changes.append({"concern_id": owner, "key": key, "from": before["status"], "to": slot["status"]})
    engine._apply_conditions(session)
    if session.get("summary"):
        session["_summary_version"] = max(session.get("_summary_version", 0), session["summary"].get("version", 0))
    session.update(experience_version=2, status="active", stage="followup" if complete else "baseline",
                   summary=None, current_question=None)
    session["plan"]["next_target"] = None
    baseline = session.setdefault("baseline", {})
    baseline.update(completed=complete, saved_at=engine._now())
    if complete:
        marked = list(fields)
        marked.extend(("session", key) for key in AGENDA_ALIASES if key in session["shared_slots"])
        baseline["field_keys"] = [{"concern_id": owner, "key": key} for owner, key in dict.fromkeys(marked)]
        baseline["field_ids"] = [f"{owner}:{key}" for owner, key in dict.fromkeys(marked)]
        baseline["deferred_keys"] = []
        for owner, key in dict.fromkeys(marked):
            slot = engine._owner_slots(session, owner)[key]
            slot["baseline"] = True
            slot["baseline_deferred"] = slot["status"] == "MISSING"
            if slot["baseline_deferred"]:
                baseline["deferred_keys"].append({"concern_id": owner, "key": key})
        baseline["completed_at"] = engine._now()
    # A real update invalidates previous baseline extraction, while saving an
    # identical form should not consume model calls on a follow-up retry.
    if changes:
        baseline["revision"] = baseline.get("revision", 0) + 1
        baseline.pop("extracted_at", None)
        baseline.pop("extraction_revision", None)
    engine._metrics(session)
    session.setdefault("audit", []).append({"event": "baseline_completed" if complete else "baseline_saved",
                                            "message_id": msg["id"] if msg else None, "changes": changes})
    return session
