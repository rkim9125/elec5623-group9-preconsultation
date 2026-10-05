"""Owned patient intakes and explicit, versioned sharing with clinicians."""
from __future__ import annotations

from copy import deepcopy
import shutil
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import engine, forms, pipeline
from .auth import (csrf_protect, normalize_email, require_user, require_patient,
                   require_doctor, check_rate_limit)
from .config import get_settings, model_options
from .database import (ConcurrentUpdate, load_intake, save_intake, list_intakes,
                       delete_intake, utc_now)
from .workflows import WORKFLOWS

router = APIRouter(tags=["Pre-consultation"])


class CreateIntake(BaseModel):
    consent: Literal[True]
    model: str | None = Field(default=None, max_length=100)
    workflow_ids: list[str] = Field(default_factory=list, max_length=30)
    title: str | None = Field(default=None, max_length=150)
    custom_concerns: list[Annotated[str, Field(min_length=1, max_length=150)]] = Field(default_factory=list, max_length=10)

    @field_validator("custom_concerns")
    @classmethod
    def valid_custom_concerns(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Give each custom concern a short name.")
        return list(dict.fromkeys(value.strip() for value in values))


class BaselineAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    concern_id: str = Field(default="session", min_length=1, max_length=100)
    key: str = Field(min_length=1, max_length=150)
    value: str | None = Field(default=None, max_length=6000)
    status: Literal["FILLED", "UNCERTAIN", "SKIPPED", "MISSING"] = "FILLED"


class BaselineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[BaselineAnswer] = Field(default_factory=list, max_length=400)
    complete: bool = False
    revision: int | None = Field(default=None, ge=1)


class MessageInput(BaseModel):
    text: str = Field(default="", max_length=12000)
    action: Literal["answer", "unknown", "skip"] = "answer"


class CorrectionInput(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class ApprovalInput(BaseModel):
    version: int = Field(ge=1)
    doctor_email: str | None = Field(default=None, max_length=254)

    @field_validator("doctor_email")
    @classmethod
    def email_is_valid(cls, value: str | None) -> str | None:
        return normalize_email(value) if value else None


def public_session(session: dict) -> dict:
    """Return patient data without local storage paths or private engine metadata."""
    result = {key: deepcopy(value) for key, value in session.items() if not key.startswith("_")}
    for attachment in result.get("attachments", []):
        attachment.pop("storage_path", None)
    return result


def clinician_public_session(session: dict) -> dict:
    """Share the approved clinical record, not private conversational history."""
    allowed = {"id", "title", "patient_id", "patient_email", "patient_name",
               "created_at", "updated_at", "status", "model", "consent",
               "concerns", "shared_slots", "summary", "attachments",
               "doctor_email", "reviewed_at", "reviewed_by", "shared_at"}
    result = {key: value for key, value in public_session(session).items() if key in allowed}
    # Slots contain superseded values and source excerpts for the patient's own
    # correction history. Clinicians receive only the current approved values.
    def approved_slot(slot: dict) -> dict:
        value = {key: deepcopy(slot[key]) for key in ("label", "value", "status", "conflict") if key in slot}
        if slot.get("exclude_from_handoff") or slot.get("status") in {"SKIPPED", "NOT_APPLICABLE", "MISSING"}:
            value["value"] = None
        return value
    def without_evidence(value):
        if isinstance(value, dict):
            return {key: without_evidence(item) for key, item in value.items()
                    if key not in {"evidence", "history", "entry_evidence"} and not key.startswith("_")}
        if isinstance(value, list):
            return [without_evidence(item) for item in value]
        return value
    result["summary"] = without_evidence(result.get("summary"))
    result["shared_slots"] = {key: approved_slot(slot) for key, slot in session.get("shared_slots", {}).items()}
    result["concerns"] = [
        {**{key: deepcopy(concern[key]) for key in ("id", "workflow_id", "title", "preparation_status") if key in concern},
         "slots": {key: approved_slot(slot) for key, slot in concern.get("slots", {}).items()}}
        for concern in session.get("concerns", [])
    ]
    return result


def require_owner(intake_id: str, user: dict) -> dict:
    session = load_intake(intake_id)
    if session is None or session.get("patient_id") != user["id"] or user["role"] != "patient":
        raise HTTPException(404, "Intake not found.")
    return session


def require_shared(intake_id: str, user: dict) -> dict:
    session = load_intake(intake_id)
    if (session is None or user["role"] != "doctor" or session.get("status") != "approved"
            or (session.get("doctor_email") or "").lower() != user["email"]
            or not (session.get("summary") or {}).get("approved_at")):
        raise HTTPException(404, "Shared intake not found.")
    return session


def ensure_editable(session: dict) -> None:
    if not session.get("consent"):
        raise HTTPException(409, "Consent has been withdrawn. Begin a new intake to provide consent again.")
    if session.get("status") == "approved":
        raise HTTPException(409, "Withdraw sharing before making changes to this intake.")


def run_engine(operation, *args, **kwargs) -> dict:
    try:
        return operation(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


def persist(session: dict) -> dict:
    try:
        save_intake(session)
    except ConcurrentUpdate as exc:
        raise HTTPException(409, str(exc)) from None
    return public_session(session)


@router.get("/config")
def config(request: Request, response: Response) -> dict:
    settings = get_settings()
    signed_in = False
    try:
        require_user(request)
        signed_in = True
    except HTTPException:
        pass
    response.headers["Cache-Control"] = "no-store"
    return {
        "models": model_options(),
        "default_model": settings.openai_model,
        "auth_configured": settings.mail_configured,
        "mail_configured": settings.mail_configured,
        "doctor_configured": bool(settings.doctor_emails),
        "ai_configured": bool(settings.openai_api_key),
        "care_team": [{"email": email, "name": email} for email in settings.doctor_emails] if signed_in else [],
        "max_upload_mb": settings.max_file_mb,
        "local_storage": True,
    }


@router.get("/workflows")
def workflows(user: dict = Depends(require_user)) -> list[dict]:
    return WORKFLOWS


@router.get("/intakes")
def patient_intakes(user: dict = Depends(require_patient)) -> list[dict]:
    return [public_session(session) for session in list_intakes(user["id"])]


@router.post("/intakes", status_code=201, dependencies=[Depends(csrf_protect)])
def create_intake(body: CreateIntake, request: Request, user: dict = Depends(require_patient)) -> dict:
    check_rate_limit(request, "create_intake", user["email"])
    workflow_ids = list(dict.fromkeys(body.workflow_ids))
    allowed = {workflow["id"] for workflow in WORKFLOWS}
    if set(workflow_ids) - allowed:
        raise HTTPException(422, "One or more selected workflows are unavailable.")
    model = body.model or get_settings().openai_model
    if model not in {option["id"] for option in model_options()}:
        raise HTTPException(422, "Select one of the models configured by the service administrator.")
    session = run_engine(engine.new_intake, user, model, workflow_ids, body.title)
    session["consent"] = True
    session["consented_at"] = utc_now()
    session = run_engine(forms.initialize, session, body.custom_concerns)
    return persist(session)


@router.get("/intakes/{intake_id}")
def patient_intake(intake_id: str, user: dict = Depends(require_patient)) -> dict:
    return public_session(require_owner(intake_id, user))


@router.get("/intakes/{intake_id}/form")
def preparation_form(intake_id: str, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    # Legacy free-text drafts without a topic gain a GENERAL concern when the
    # patient saves a form. A read never mutates the stored preparation.
    view = deepcopy(session)
    if not view.get("concerns"):
        engine._add_concern(view, "GENERAL", "Your appointment concern")
        # A stable ID keeps GET fields addressable on the subsequent PUT.
        view["concerns"][-1]["id"] = f"general-{session['id']}"
    return {**forms.get_form(view), "revision": session.get("revision")}


@router.put("/intakes/{intake_id}/baseline", dependencies=[Depends(csrf_protect)])
def save_baseline(intake_id: str, body: BaselineInput, request: Request, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    ensure_editable(session)
    if session.get("status") == "interrupted":
        raise HTTPException(409, "This preparation was paused by a safety concern and cannot accept more answers.")
    if body.revision is not None and body.revision != session.get("revision"):
        raise HTTPException(409, "This intake changed. Refresh the form before saving it again.")
    if not session.get("concerns"):
        engine._add_concern(session, "GENERAL", "Your appointment concern")
        session["concerns"][-1]["id"] = f"general-{session['id']}"
    try:
        session = forms.apply_baseline(session, [answer.model_dump() for answer in body.answers], complete=body.complete)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    if body.complete and session.get("consent") and session.get("status") != "interrupted":
        check_rate_limit(request, "intake_message", user["email"])
        session = run_engine(pipeline.start_followup, session)
    return persist(session)


@router.post("/intakes/{intake_id}/followup", dependencies=[Depends(csrf_protect)])
def retry_followup(intake_id: str, request: Request, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    ensure_editable(session)
    if session.get("status") == "interrupted":
        raise HTTPException(409, "This preparation was paused by a safety concern.")
    if not session.get("baseline", {}).get("completed"):
        raise HTTPException(409, "Complete the preparation form before requesting AI follow-up.")
    check_rate_limit(request, "intake_message", user["email"])
    return persist(run_engine(pipeline.start_followup, session))


@router.post("/intakes/{intake_id}/messages", dependencies=[Depends(csrf_protect)])
def message(intake_id: str, body: MessageInput, request: Request, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    ensure_editable(session)
    if body.action == "answer" and not body.text.strip():
        raise HTTPException(422, "Enter a message or choose Skip / I’m not sure.")
    if len(session.get("messages", [])) >= 400:
        raise HTTPException(409, "This intake has reached its message limit. Review your summary or begin a new intake.")
    check_rate_limit(request, "intake_message", user["email"])
    session = run_engine(pipeline.process_message, session, body.text.strip(), body.action)
    return persist(session)


@router.post("/intakes/{intake_id}/review", dependencies=[Depends(csrf_protect)])
def review(intake_id: str, request: Request, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    ensure_editable(session)
    if session.get("status") == "interrupted":
        raise HTTPException(409, "This intake was interrupted by a safety concern. Follow the urgent-care guidance shown in the conversation.")
    check_rate_limit(request, "intake_review", user["email"])
    return persist(run_engine(pipeline.build_review, session))


@router.patch("/intakes/{intake_id}/review", dependencies=[Depends(csrf_protect)])
def correct_review(intake_id: str, body: CorrectionInput, request: Request, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    ensure_editable(session)
    if not session.get("summary") or session.get("status") != "review":
        raise HTTPException(409, "Create a draft summary before correcting it.")
    check_rate_limit(request, "intake_review", user["email"])
    return persist(run_engine(pipeline.build_review, session, correction=body.text.strip()))


@router.post("/intakes/{intake_id}/approve", dependencies=[Depends(csrf_protect)])
def approve(intake_id: str, body: ApprovalInput, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    summary = session.get("summary")
    if session.get("status") != "review" or not summary:
        raise HTTPException(409, "Review the current draft summary before approving it.")
    if summary.get("needs_reconciliation"):
        raise HTTPException(409, "A saved correction still needs to be reconciled. Please retry the correction before approving.")
    if summary.get("version") != body.version:
        raise HTTPException(409, "The summary has changed. Review the latest version before sharing it.")
    doctors = get_settings().doctor_emails
    doctor = body.doctor_email or (doctors[0] if len(doctors) == 1 else None)
    if not doctors:
        raise HTTPException(503, "No clinician is configured. Ask the administrator to set DOCTOR_EMAILS.")
    if doctor not in doctors:
        raise HTTPException(422, "Select a registered clinician to receive this summary.")
    now = utc_now()
    session["status"] = "approved"
    session["doctor_email"] = doctor
    session["shared_at"] = now
    session["reviewed_at"] = None
    summary["approved_at"] = now
    summary["approved_version"] = body.version
    return persist(session)


@router.post("/intakes/{intake_id}/withdraw", dependencies=[Depends(csrf_protect)])
def withdraw(intake_id: str, user: dict = Depends(require_patient)) -> dict:
    session = require_owner(intake_id, user)
    if session.get("status") != "approved":
        raise HTTPException(409, "This intake is not currently shared.")
    session["status"] = "withdrawn"
    session["doctor_email"] = None
    session["shared_at"] = None
    session["reviewed_at"] = None
    session["withdrawn_at"] = utc_now()
    if session.get("summary"):
        session["summary"].pop("approved_at", None)
        session["summary"].pop("approved_version", None)
    return persist(session)


@router.delete("/intakes/{intake_id}", status_code=204, dependencies=[Depends(csrf_protect)])
def remove_intake(intake_id: str, user: dict = Depends(require_patient)) -> Response:
    session = require_owner(intake_id, user)
    if not delete_intake(session["id"], user["id"]):
        raise HTTPException(404, "Intake not found.")
    root = get_settings().upload_dir.resolve()
    directory = (root / session["id"]).resolve()
    # Never follow a DB path or a symlink outside the dedicated upload root.
    if directory.parent == root and directory.is_dir():
        shutil.rmtree(directory)
    return Response(status_code=204)


@router.get("/clinician/intakes")
def clinician_intakes(user: dict = Depends(require_doctor)) -> list[dict]:
    return [clinician_public_session(session) for session in list_intakes()
            if session.get("status") == "approved"
            and session.get("doctor_email", "") == user["email"]
            and (session.get("summary") or {}).get("approved_at")]


@router.get("/clinician/intakes/{intake_id}")
def clinician_intake(intake_id: str, user: dict = Depends(require_doctor)) -> dict:
    return clinician_public_session(require_shared(intake_id, user))


@router.post("/clinician/intakes/{intake_id}/reviewed", dependencies=[Depends(csrf_protect)])
def mark_reviewed(intake_id: str, user: dict = Depends(require_doctor)) -> dict:
    session = require_shared(intake_id, user)
    session["reviewed_at"] = utc_now()
    session["reviewed_by"] = user["email"]
    persist(session)
    return clinician_public_session(session)
