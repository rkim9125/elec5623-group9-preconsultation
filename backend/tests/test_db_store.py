from copy import deepcopy

import pytest
from sqlalchemy import URL, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core import flow
from app.core.engine import confirm_slot, edit_slot, mark_unknown, skip_slot
from app.core.errors import PersistenceConflict, SessionNotFound, SummaryNotReady
from app.core.models import Candidate, TranscriptEntry
from app.db.manage import upgrade_database
from app.db.models import Base
from app.db.session import create_db_engine, store_transaction
from app.db.store import DatabaseSessionStore
from app.llm.base import GeneratedSummary
from app.llm.fake import FakeLLM


def create(factory, state):
    with store_transaction(factory) as store:
        store.create(state)


def test_restart_roundtrip_and_serialization(database_factory, state):
    state.transcript.append(
        TranscriptEntry(role="patient", text="Synthetic 中文 input")
    )
    state.slots["chief_complaint"].candidates.append(
        Candidate(value="test", evidence_span="test")
    )
    state.slots["allergies"].value = []
    state.slots["symptom_duration_days"].value = 0
    state.slots["chief_complaint"].required = False
    create(database_factory, state)
    engine = database_factory.kw["bind"]
    url = engine.url
    engine.dispose()
    reopened = create_db_engine(url)
    try:
        with store_transaction(sessionmaker(bind=reopened)) as store:
            restored = store.get(state.session_id)
            assert restored.model_dump(mode="json") == state.model_dump(mode="json")
            assert restored.created_at.tzinfo is not None
    finally:
        reopened.dispose()


def test_history_order_idempotence_and_candidate_archive(database_factory, state):
    create(database_factory, state)
    with store_transaction(database_factory) as store:
        saved = store.get(state.session_id)
        flow.ingest_message(saved, "sore throat for 3 days", FakeLLM())
        store.save(saved)
        candidates = store.list_candidates(saved.session_id)
        messages = store.list_messages(saved.session_id)
        assert candidates
        confirm_slot(saved, "chief_complaint")
        edit_slot(saved, "symptom_severity", "mild")
        edit_slot(saved, "symptom_severity", "moderate")
        mark_unknown(saved, "current_medications")
        skip_slot(saved, "past_conditions")
        expected_history = deepcopy(saved.history)
        store.save(saved)
        store.save(saved)
        assert store.list_messages(saved.session_id) == messages
        assert store.list_candidates(saved.session_id) == candidates
    with store_transaction(database_factory) as store:
        saved = store.get(state.session_id)
        assert saved.history == expected_history
        correction = next(
            entry for entry in saved.history if entry.event.value == "corrected"
        )
        assert (correction.previous_value, correction.new_value) == ("mild", "moderate")
        assert saved.slots["current_medications"].status.value == "unknown"
        assert saved.slots["past_conditions"].status.value == "skipped"


@pytest.mark.parametrize("target", ["transcript", "history"])
def test_rewriting_append_only_data_rolls_back(database_factory, state, target):
    state.transcript.append(TranscriptEntry(role="patient", text="original"))
    edit_slot(state, "symptom_severity", "mild")
    create(database_factory, state)
    with pytest.raises(ValueError):
        with store_transaction(database_factory) as store:
            saved = store.get(state.session_id)
            saved.slots["symptom_severity"].value = "moderate"
            if target == "transcript":
                saved.transcript[0].text = "rewritten"
            else:
                saved.history.clear()
            store.save(saved)
    with store_transaction(database_factory) as store:
        assert store.get(state.session_id) == state


def test_summary_and_state_rollback_together(database_factory, state):
    create(database_factory, state)
    with pytest.raises(RuntimeError):
        with store_transaction(database_factory) as store:
            saved = store.get(state.session_id)
            summary = flow.finalise(saved, FakeLLM())
            store.put_summary(saved.session_id, summary)
            store.save(saved)
            raise RuntimeError("injected failure before commit")
    with store_transaction(database_factory) as store:
        assert store.get(state.session_id).status.value == "in_progress"
        assert store.list_summary_versions(state.session_id) == []
        assert [e["event"] for e in store.list_audit(state.session_id)] == [
            "session_created"
        ]


def test_versions_and_explicit_approval(database_factory, state):
    create(database_factory, state)
    first = GeneratedSummary(sections={"test": "version one"})
    second = GeneratedSummary(sections={"test": "version two"})
    with store_transaction(database_factory) as store:
        store.put_summary(state.session_id, first)
        with pytest.raises(SummaryNotReady):
            store.get_approved_summary(state.session_id)
        store.record_summary_approval(state.session_id, 1, "synthetic-patient")
        store.put_summary(state.session_id, second)
    with store_transaction(database_factory) as store:
        versions = store.list_summary_versions(state.session_id)
        assert [v["version"] for v in versions] == [1, 2]
        assert versions[1]["approved_at"] is None
        assert store.get_summary(state.session_id) == second
        assert store.get_approved_summary(state.session_id)["summary"] == first


def test_stale_writer_cannot_overwrite_committed_data(database_factory, state):
    create(database_factory, state)
    with database_factory() as db_a, database_factory() as db_b:
        a, b = DatabaseSessionStore(db_a), DatabaseSessionStore(db_b)
        state_a, state_b = a.get(state.session_id), b.get(state.session_id)
        edit_slot(state_a, "symptom_severity", "mild")
        a.save(state_a)
        db_a.commit()
        edit_slot(state_b, "symptom_severity", "moderate")
        with pytest.raises(PersistenceConflict):
            b.save(state_b)
        db_b.rollback()
    with store_transaction(database_factory) as store:
        assert store.get(state.session_id).slots["symptom_severity"].value == "mild"


def test_missing_duplicate_and_cross_session_isolation(database_factory, state):
    create(database_factory, state)
    with pytest.raises(PersistenceConflict):
        create(database_factory, state)
    other = state.model_copy(deep=True)
    other.session_id = "other"
    create(database_factory, other)
    with store_transaction(database_factory) as store:
        with pytest.raises(SessionNotFound):
            store.get("absent")
        saved = store.get(state.session_id)
        edit_slot(saved, "symptom_severity", "moderate")
        store.save(saved)
        assert store.get("other").slots["symptom_severity"].value is None


def test_metadata_and_explicit_sources(database_factory, state):
    state.transcript.append(TranscriptEntry(role="patient", text="synthetic evidence"))
    state.slots["chief_complaint"].candidates.append(
        Candidate(value="example", evidence_span="synthetic evidence")
    )
    create(database_factory, state)
    with store_transaction(database_factory) as store:
        sid = state.session_id
        message = store.list_messages(sid)[0]
        candidate = store.list_candidates(sid)[0]
        store.add_source_reference(
            sid,
            "chief_complaint",
            message_id=message["message_id"],
            candidate_id=candidate["candidate_id"],
            quote="synthetic evidence",
        )
        aid = store.add_attachment(
            sid,
            object_key="synthetic/demo.pdf",
            filename="demo.pdf",
            media_type="application/pdf",
            size_bytes=42,
        )
        store.add_source_reference(
            sid, "chief_complaint", attachment_id=aid, location={"page": 1}
        )
        store.record_model_call(
            sid,
            operation="extract",
            model="fake",
            status="success",
            prompt_version="v1",
            input_tokens=12,
            output_tokens=5,
            latency_ms=10,
        )
    with store_transaction(database_factory) as store:
        assert len(store.list_source_references(sid)) == 2
        assert store.list_attachments(sid)[0]["object_key"] == "synthetic/demo.pdf"
        assert store.list_model_calls(sid)[0]["prompt_version"] == "v1"


def test_foreign_keys_reject_cross_session_sources(database_factory, state):
    state.transcript.append(TranscriptEntry(role="patient", text="one"))
    create(database_factory, state)
    other = flow.start_session()
    create(database_factory, other)
    with store_transaction(database_factory) as store:
        message_id = store.list_messages(state.session_id)[0]["message_id"]
    with pytest.raises(IntegrityError):
        with store_transaction(database_factory) as store:
            store.add_source_reference(
                other.session_id, "chief_complaint", message_id=message_id
            )


def test_migration_matches_models_and_is_repeatable(database_factory):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    engine = database_factory.kw["bind"]
    upgrade_database(engine)
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
        assert set(inspect(conn).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version"
        }
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def test_committed_data_visible_to_separate_python_process(database_factory, state):
    import os
    import subprocess
    import sys

    create(database_factory, state)
    env = os.environ.copy()
    env["DATABASE_URL"] = str(database_factory.kw["bind"].url)
    code = "from app.db.session import store_transaction;\nwith store_transaction() as store:\n print(store.get('s1').session_id)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == state.session_id
