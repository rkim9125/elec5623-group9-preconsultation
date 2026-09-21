"""Bind patient approval to the exact server-stored summary version."""

import hashlib
import json

from app.core.models import SessionState
from app.llm.base import GeneratedSummary


def summary_digest(state: SessionState, summary: GeneratedSummary) -> str:
    payload = {
        "session_id": state.session_id,
        "summary_ref": state.summary_ref,
        **summary.model_dump(mode="json"),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def summary_is_approved(state: SessionState, summary: GeneratedSummary) -> bool:
    return bool(state.summary_approved_at and state.summary_approved_sha256 == summary_digest(state, summary))
