"""Patient-maintained background, with a deliberately small reusable field set.

Symptoms, medications, allergies, pregnancy status, weight and other current
measurements are encounter information. They are never persisted or reused by
this module. A profile snapshot is background context, not a verified finding.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .database import get_connection, utc_now


class PatientProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_of_birth: str = Field(default="", max_length=10)
    sex_at_birth: Literal["", "female", "male", "intersex", "prefer_not_to_say"] = ""
    # An ABO-only answer means the patient does not know their Rh factor.
    blood_group: Literal["", "unknown", "A", "B", "AB", "O", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] = ""
    medical_history: str = Field(default="", max_length=4000)
    surgical_history: str = Field(default="", max_length=4000)
    family_history: str = Field(default="", max_length=4000)
    accessibility_needs: str = Field(default="", max_length=4000)

    @field_validator("date_of_birth")
    @classmethod
    def valid_birth_date(cls, value: str) -> str:
        if not value:
            return ""
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Use YYYY-MM-DD for date of birth.") from None
        if parsed.isoformat() != value or parsed > date.today():
            raise ValueError("Date of birth must be a valid date in the past.")
        return value

    @field_validator("medical_history", "surgical_history", "family_history", "accessibility_needs")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValueError("Background information contains invalid characters.")
        return value.strip()

    @model_validator(mode="after")
    def bounded_history(self):
        # The reusable history becomes one encounter answer (6,000 character
        # limit), so reserve space for the descriptive headings as well.
        if sum(len(getattr(self, key)) for key in ("medical_history", "surgical_history", "family_history")) > 5900:
            raise ValueError("Keep medical, surgical and family history under 5,900 characters in total.")
        return self


PROFILE_FIELDS = tuple(PatientProfileInput.model_fields)


def empty_profile() -> dict:
    return {"version": 1, **PatientProfileInput().model_dump(), "updated_at": None, "field_updated_at": {}}


def load_profile(user_id: str) -> dict:
    with get_connection() as conn:
        row = conn.execute("SELECT data FROM patient_profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return empty_profile()
    stored = json.loads(row["data"])
    # Explicit keys keep old or future transient fields out of reusable context.
    return {**empty_profile(), **{key: stored[key] for key in (*PROFILE_FIELDS, "updated_at", "field_updated_at") if key in stored}}


def save_profile(user_id: str, body: PatientProfileInput) -> dict:
    values = body.model_dump()
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT data FROM patient_profiles WHERE user_id = ?", (user_id,)).fetchone()
        previous = json.loads(row["data"]) if row else empty_profile()
        changed = [key for key in PROFILE_FIELDS if values[key] != previous.get(key, "")]
        if not changed:
            return {**empty_profile(), **previous}
        at = utc_now()
        timestamps = {**previous.get("field_updated_at", {})}
        timestamps.update({key: at for key in changed})
        profile = {"version": 1, **values, "updated_at": at, "field_updated_at": timestamps}
        conn.execute("INSERT INTO patient_profiles (user_id, data, updated_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                     (user_id, json.dumps(profile, ensure_ascii=False), at))
    return profile


def snapshot_for_intake(user_id: str) -> dict:
    """Return a copy; later edits cannot rewrite the history of an intake."""
    profile = deepcopy(load_profile(user_id))
    if profile.get("date_of_birth"):
        born = date.fromisoformat(profile["date_of_birth"])
        today = date.today()
        # Age is derived for this appointment, never saved as reusable profile data.
        profile["age_years"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        profile["age_as_of"] = today.isoformat()
    return profile


def prefill_answers(user_id: str, *, profile: dict | None = None) -> list[dict]:
    """Reuse only the patient's enduring history, never inferred clinical facts."""
    profile = profile if profile is not None else load_profile(user_id)
    parts = [f"{label}: {profile[key]}" for key, label in (
        ("medical_history", "Medical history"),
        ("surgical_history", "Surgical history"),
        ("family_history", "Family history"),
    ) if profile[key]]
    return [{"concern_id": "session", "key": "relevant_history", "value": "\n".join(parts), "status": "FILLED"}] if parts else []
