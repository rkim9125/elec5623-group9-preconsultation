"""Database table definitions."""

from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared base for all database tables."""

    pass


class SessionRecord(Base):
    """Basic information for one pre-consultation session."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Store timestamps as ISO 8601 strings, including the UTC offset.
    created_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    updated_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    patient_ref: Mapped[str | None] = mapped_column(String(128))
    locale: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    current_prompt: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(none_as_null=True)
    )
    summary_ref: Mapped[str | None] = mapped_column(String(64))


class MessageRecord(Base):
    """One original message in a session's transcript."""

    __tablename__ = "messages"

    __table_args__ = (
        UniqueConstraint("session_id", "message_id", name="uq_messages_owner"),
        CheckConstraint("sequence >= 0", name="ck_messages_sequence"),
        UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_messages_session_sequence",
        ),
    )

    message_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid4().hex,
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sessions.session_id"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    at: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )


class SlotRecord(Base):
    """Current structured state of one slot in one session."""

    __tablename__ = "slot_states"

    # Together, these two columns uniquely identify a slot.
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sessions.session_id"),
        primary_key=True,
    )
    slot_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    options: Mapped[list[str] | None] = mapped_column(
        JSON(none_as_null=True),
        nullable=True,
    )
    value: Mapped[Any] = mapped_column(
        JSON(none_as_null=True),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    source: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    candidates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    updated_at: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )


class SlotHistoryRecord(Base):
    """Append-only copy of C3's history; sequence preserves exact order."""

    __tablename__ = "slot_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "slot_id"], ["slot_states.session_id", "slot_states.slot_id"]
        ),
        CheckConstraint("sequence >= 0", name="ck_history_sequence"),
    )
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_value: Mapped[Any] = mapped_column(JSON(none_as_null=True), nullable=True)
    previous_status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_value: Mapped[Any] = mapped_column(JSON(none_as_null=True), nullable=True)
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    at: Mapped[str] = mapped_column(String(40), nullable=False)


class CandidateRecord(Base):
    """Evidence survives C3 clearing/reordering current candidates."""

    __tablename__ = "candidate_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "slot_id"], ["slot_states.session_id", "slot_states.slot_id"]
        ),
        UniqueConstraint(
            "session_id", "slot_id", "fingerprint", name="uq_candidate_payload"
        ),
        UniqueConstraint(
            "session_id", "slot_id", "candidate_id", name="uq_candidate_owner"
        ),
    )
    candidate_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    slot_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class SummaryRecord(Base):
    """Immutable content versions; approval must be explicitly supplied by C3."""

    __tablename__ = "summary_versions"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_summary_version"),
        CheckConstraint("version > 0", name="ck_summary_version"),
        CheckConstraint(
            "(approved_at IS NULL AND approved_by IS NULL) OR "
            "(approved_at IS NOT NULL AND approved_by IS NOT NULL)",
            name="ck_summary_approval",
        ),
    )
    summary_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sections: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False)
    patient_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_at: Mapped[str | None] = mapped_column(String(40))
    approved_by: Mapped[str | None] = mapped_column(String(128))


class AuditRecord(Base):
    __tablename__ = "audit_events"
    audit_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    at: Mapped[str] = mapped_column(String(40), nullable=False)


class AttachmentRecord(Base):
    """C5 metadata only; file bytes remain in object storage."""

    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint("session_id", "attachment_id", name="uq_attachment_owner"),
        CheckConstraint("size_bytes >= 0", name="ck_attachment_size"),
    )
    attachment_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class SourceReferenceRecord(Base):
    """Explicit evidence locations supplied by C3/C4/C5, never guessed."""

    __tablename__ = "source_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "slot_id"], ["slot_states.session_id", "slot_states.slot_id"]
        ),
        ForeignKeyConstraint(
            ["session_id", "message_id"], ["messages.session_id", "messages.message_id"]
        ),
        ForeignKeyConstraint(
            ["session_id", "attachment_id"],
            ["attachments.session_id", "attachments.attachment_id"],
        ),
        ForeignKeyConstraint(
            ["session_id", "slot_id", "candidate_id"],
            [
                "candidate_records.session_id",
                "candidate_records.slot_id",
                "candidate_records.candidate_id",
            ],
        ),
        CheckConstraint(
            "(message_id IS NOT NULL AND attachment_id IS NULL) OR "
            "(message_id IS NULL AND attachment_id IS NOT NULL)",
            name="ck_source_one_origin",
        ),
    )
    source_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    slot_id: Mapped[str] = mapped_column(String(128), nullable=False)
    candidate_id: Mapped[str | None] = mapped_column(String(32))
    message_id: Mapped[str | None] = mapped_column(String(32))
    attachment_id: Mapped[str | None] = mapped_column(String(32))
    quote: Mapped[str | None] = mapped_column(Text)
    location: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)


class ModelCallRecord(Base):
    """Minimal C4 telemetry; no API keys or duplicated raw prompts."""

    __tablename__ = "model_calls"
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_call_input"),
        CheckConstraint("output_tokens >= 0", name="ck_call_output"),
        CheckConstraint("latency_ms >= 0", name="ck_call_latency"),
    )
    call_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
