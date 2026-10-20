"""Patient-owned historical answers, offered for explicit per-visit confirmation.

These suggestions never become current clinical facts without a patient action.
No extra copy of the history is stored outside its original encounter.
"""
from __future__ import annotations

import json

from .database import get_connection

HISTORY_KEYS = {"current_medications", "allergies"}


def previous_answers(patient_id: str, current: dict) -> dict:
    suggestions = {}
    pending = set(HISTORY_KEYS)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT data FROM intakes WHERE patient_id = ? AND id != ? ORDER BY updated_at DESC",
            (patient_id, current["id"]),
        )
        for row in rows:
            previous = json.loads(row["data"])
            if (not previous.get("consent") or previous.get("status") == "withdrawn"
                    or previous.get("created_at", "") >= current.get("created_at", "")):
                continue
            for key in list(pending):
                slot = previous.get("shared_slots", {}).get(key, {})
                # A later refusal, uncertainty, or cleared answer supersedes an
                # older value. Do not resurrect it as a quick-fill suggestion.
                if slot.get("status") in {"UNCERTAIN", "SKIPPED"} or (
                    slot.get("status") == "MISSING" and slot.get("history")
                ):
                    pending.remove(key)
                    continue
                value = slot.get("value")
                evidence = slot.get("evidence") or {}
                if (slot.get("status") != "FILLED" or slot.get("exclude_from_handoff")
                        or not isinstance(value, str) or not value.strip()
                        or evidence.get("source") not in {"patient_form", "direct_patient_response"}):
                    continue
                pending.remove(key)
                suggestions[key] = {
                    "value": value,
                    "recorded_at": slot.get("updated_at") or previous.get("updated_at") or previous.get("created_at"),
                    "requires_confirmation": True,
                }
            if not pending:
                break
    return suggestions
