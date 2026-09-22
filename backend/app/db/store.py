"""C6 persistence. Business decisions belong to C3, not this module.

Use one instance per store_transaction(). Methods flush but never commit.
Load a state using this store before saving it (optimistic concurrency token).
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import func, select, update

from app.core.errors import PersistenceConflict, SessionNotFound, SummaryNotReady
from app.core.models import SessionState
from app.db.models import (
    AttachmentRecord,
    AuditRecord,
    CandidateRecord,
    MessageRecord,
    ModelCallRecord,
    SessionRecord,
    SlotHistoryRecord,
    SlotRecord,
    SourceReferenceRecord,
    SummaryRecord,
)
from app.llm.base import GeneratedSummary

STATE_COLUMNS = (
    "session_id",
    "status",
    "created_at",
    "updated_at",
    "patient_ref",
    "locale",
    "schema_version",
    "current_prompt",
    "summary_ref",
)
HISTORY_COLUMNS = (
    "slot_id",
    "event",
    "previous_value",
    "previous_status",
    "new_value",
    "new_status",
    "source",
    "at",
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def record_dict(record):
    return deepcopy(
        {
            column.name: getattr(record, column.name)
            for column in record.__table__.columns
        }
    )


class DatabaseSessionStore:
    def __init__(self, db):
        self.db = db
        self._versions = {}
        self._snapshots = {}

    def _row(self, session_id):
        row = self.db.get(SessionRecord, session_id)
        if row is None:
            raise SessionNotFound(f"No session {session_id!r}")
        return row

    def _claim(self, session_id):
        """CAS prevents one stale browser/request from overwriting another."""
        row = self._row(session_id)
        expected = self._versions.setdefault(session_id, row.version)
        result = self.db.execute(
            update(SessionRecord)
            .where(
                SessionRecord.session_id == session_id,
                SessionRecord.version == expected,
            )
            .values(version=expected + 1),
            execution_options={"synchronize_session": False},
        )
        if result.rowcount != 1:
            raise PersistenceConflict("Session changed; reload it before retrying.")
        self.db.expire(row, ["version"])
        self._versions[session_id] = expected + 1
        return row

    def create(self, state: SessionState) -> None:
        data = state.model_dump(mode="json")
        if self.db.get(SessionRecord, state.session_id) is not None:
            raise PersistenceConflict("Session already exists.")
        self.db.add(
            SessionRecord(**{key: data[key] for key in STATE_COLUMNS}, version=1)
        )
        self.db.flush()
        self._versions[state.session_id] = 1
        self._save_children(data)
        self.append_audit(
            state.session_id,
            "session_created",
            details={"schema_version": state.schema_version},
        )
        self._snapshots[state.session_id] = deepcopy(data)

    def get(self, session_id: str) -> SessionState:
        row = self._row(session_id)
        data = {key: deepcopy(getattr(row, key)) for key in STATE_COLUMNS}
        slots = self.db.scalars(
            select(SlotRecord).where(SlotRecord.session_id == session_id)
        ).all()
        data["slots"] = {
            slot.slot_id: {
                key: value
                for key, value in record_dict(slot).items()
                if key != "session_id"
            }
            for slot in slots
        }
        data["transcript"] = [
            {key: getattr(message, key) for key in ("role", "text", "at")}
            for message in self.db.scalars(
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.sequence)
            )
        ]
        data["history"] = [
            {key: deepcopy(getattr(entry, key)) for key in HISTORY_COLUMNS}
            for entry in self.db.scalars(
                select(SlotHistoryRecord)
                .where(SlotHistoryRecord.session_id == session_id)
                .order_by(SlotHistoryRecord.sequence)
            )
        ]
        state = SessionState.model_validate(data)
        self._versions[session_id] = row.version
        self._snapshots[session_id] = state.model_dump(mode="json")
        return state

    def save(self, state: SessionState) -> None:
        self._row(state.session_id)
        if state.session_id not in self._snapshots:
            raise ValueError("Call get() using this store before save().")
        data = state.model_dump(mode="json")
        if data == self._snapshots[state.session_id]:
            return
        row = self._claim(state.session_id)
        # Schema identity and initial creation time are not mutable state.
        for key in ("created_at", "schema_version"):
            if data[key] != self._snapshots[state.session_id][key]:
                raise ValueError(f"Cannot rewrite {key} on an existing session.")
        self._save_children(data)
        for key in STATE_COLUMNS:
            setattr(row, key, deepcopy(data[key]))
        self.append_audit(
            state.session_id,
            "session_saved",
            details={"version": self._versions[state.session_id]},
        )
        self.db.flush()
        self._snapshots[state.session_id] = deepcopy(data)

    def _append_entries(self, model, session_id, incoming, columns):
        existing = self.db.scalars(
            select(model).where(model.session_id == session_id).order_by(model.sequence)
        ).all()
        if len(incoming) < len(existing):
            raise ValueError(f"{model.__tablename__} is append-only.")
        for sequence, row in enumerate(existing):
            if row.sequence != sequence or any(
                getattr(row, key) != incoming[sequence][key] for key in columns
            ):
                raise ValueError(
                    f"Cannot rewrite existing {model.__tablename__} entries."
                )
        for sequence in range(len(existing), len(incoming)):
            self.db.add(
                model(
                    session_id=session_id,
                    sequence=sequence,
                    **deepcopy(incoming[sequence]),
                )
            )

    def _save_children(self, data):
        sid = data["session_id"]
        existing = {
            slot.slot_id: slot
            for slot in self.db.scalars(
                select(SlotRecord).where(SlotRecord.session_id == sid)
            )
        }
        if not set(existing).issubset(data["slots"]):
            raise ValueError("Cannot remove existing slots during save().")
        for key, slot in data["slots"].items():
            if key != slot["slot_id"]:
                raise ValueError("Slot key does not match slot_id.")
            row = existing.get(key)
            if row is None:
                self.db.add(SlotRecord(session_id=sid, **deepcopy(slot)))
            else:
                for name, value in slot.items():
                    setattr(row, name, deepcopy(value))
        self.db.flush()  # Parent slots must exist before their history/evidence.
        self._append_entries(
            MessageRecord, sid, data["transcript"], ("role", "text", "at")
        )
        self._append_entries(SlotHistoryRecord, sid, data["history"], HISTORY_COLUMNS)
        for slot_id, slot in data["slots"].items():
            for candidate in slot["candidates"]:
                fingerprint = hashlib.sha256(
                    json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                found = self.db.scalar(
                    select(CandidateRecord.candidate_id).where(
                        CandidateRecord.session_id == sid,
                        CandidateRecord.slot_id == slot_id,
                        CandidateRecord.fingerprint == fingerprint,
                    )
                )
                if found is None:
                    self.db.add(
                        CandidateRecord(
                            session_id=sid,
                            slot_id=slot_id,
                            fingerprint=fingerprint,
                            payload=deepcopy(candidate),
                        )
                    )
        self.db.flush()

    def put_summary(self, session_id: str, summary: GeneratedSummary) -> None:
        self._claim(session_id)
        previous = (
            self.db.scalar(
                select(func.max(SummaryRecord.version)).where(
                    SummaryRecord.session_id == session_id
                )
            )
            or 0
        )
        self.db.add(
            SummaryRecord(
                session_id=session_id,
                version=previous + 1,
                created_at=now_iso(),
                **summary.model_dump(mode="json"),
            )
        )
        self.append_audit(
            session_id, "summary_generated", details={"summary_version": previous + 1}
        )
        self.db.flush()

    def get_summary(self, session_id: str) -> GeneratedSummary:
        self._row(session_id)
        row = self.db.scalar(
            select(SummaryRecord)
            .where(SummaryRecord.session_id == session_id)
            .order_by(SummaryRecord.version.desc())
            .limit(1)
        )
        if row is None:
            raise SessionNotFound(f"No summary for session {session_id!r}")
        return self._summary_content(row)

    @staticmethod
    def _summary_content(row):
        return GeneratedSummary.model_validate(
            {
                key: deepcopy(getattr(row, key))
                for key in ("sections", "patient_questions", "model")
            }
        )

    def list_summary_versions(self, session_id):
        return self._list(SummaryRecord, session_id, SummaryRecord.version)

    def record_summary_approval(self, session_id, version, approved_by):
        """Caller C3 must authenticate/authorize the patient's explicit action."""
        if not approved_by or not approved_by.strip():
            raise ValueError("Approval requires an actor reference.")
        self._claim(session_id)
        row = self.db.scalar(
            select(SummaryRecord).where(
                SummaryRecord.session_id == session_id, SummaryRecord.version == version
            )
        )
        if row is None:
            raise SummaryNotReady("Summary version does not exist.")
        if row.approved_at is not None:
            if row.approved_by != approved_by:
                raise PersistenceConflict(
                    "Approval is already recorded for another actor."
                )
            return
        row.approved_at = now_iso()
        row.approved_by = approved_by
        self.append_audit(
            session_id,
            "summary_approved",
            actor=approved_by,
            details={"summary_version": version},
        )

    def get_approved_summary(self, session_id):
        self._row(session_id)
        row = self.db.scalar(
            select(SummaryRecord)
            .where(
                SummaryRecord.session_id == session_id,
                SummaryRecord.approved_at.is_not(None),
            )
            .order_by(SummaryRecord.version.desc())
            .limit(1)
        )
        if row is None:
            raise SummaryNotReady("No explicitly approved summary exists.")
        return {
            "version": row.version,
            "summary_id": row.summary_id,
            "summary": self._summary_content(row),
        }

    def append_audit(self, session_id, event, *, actor="system", details=None):
        self._row(session_id)
        row = AuditRecord(
            session_id=session_id,
            event=event,
            actor=actor,
            details=deepcopy(details or {}),
            at=now_iso(),
        )
        self.db.add(row)
        self.db.flush()
        return row.audit_id

    def _list(self, model, session_id, order):
        self._row(session_id)
        return [
            record_dict(row)
            for row in self.db.scalars(
                select(model).where(model.session_id == session_id).order_by(order)
            )
        ]

    def list_messages(self, session_id):
        return self._list(MessageRecord, session_id, MessageRecord.sequence)

    def list_candidates(self, session_id):
        return self._list(CandidateRecord, session_id, CandidateRecord.candidate_id)

    def list_audit(self, session_id):
        return self._list(AuditRecord, session_id, AuditRecord.at)

    def add_attachment(
        self,
        session_id,
        *,
        object_key,
        filename,
        media_type,
        size_bytes,
        status="uploaded",
    ):
        self._row(session_id)
        row = AttachmentRecord(
            session_id=session_id,
            object_key=object_key,
            filename=filename,
            media_type=media_type,
            size_bytes=size_bytes,
            status=status,
            created_at=now_iso(),
        )
        self.db.add(row)
        self.db.flush()
        return row.attachment_id

    def list_attachments(self, session_id):
        return self._list(AttachmentRecord, session_id, AttachmentRecord.created_at)

    def add_source_reference(
        self,
        session_id,
        slot_id,
        *,
        message_id=None,
        attachment_id=None,
        candidate_id=None,
        quote=None,
        location=None,
    ):
        self._row(session_id)
        if (message_id is None) == (attachment_id is None):
            raise ValueError("Supply exactly one message or attachment source.")
        row = SourceReferenceRecord(
            session_id=session_id,
            slot_id=slot_id,
            message_id=message_id,
            attachment_id=attachment_id,
            candidate_id=candidate_id,
            quote=quote,
            location=deepcopy(location or {}),
            created_at=now_iso(),
        )
        self.db.add(row)
        self.db.flush()  # Composite foreign keys reject cross-session evidence.
        return row.source_id

    def list_source_references(self, session_id):
        return self._list(
            SourceReferenceRecord, session_id, SourceReferenceRecord.created_at
        )

    def record_model_call(
        self,
        session_id,
        *,
        operation,
        model,
        status,
        prompt_version=None,
        input_tokens=None,
        output_tokens=None,
        latency_ms=None,
        error_code=None,
    ):
        self._row(session_id)
        row = ModelCallRecord(
            session_id=session_id,
            operation=operation,
            model=model,
            status=status,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            error_code=error_code,
            created_at=now_iso(),
        )
        self.db.add(row)
        self.db.flush()
        return row.call_id

    def list_model_calls(self, session_id):
        return self._list(ModelCallRecord, session_id, ModelCallRecord.created_at)
