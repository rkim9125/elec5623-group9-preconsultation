"""Usage: python -m app.db.manage {init,check,seed}. Never deletes existing data."""

import argparse

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.db.session import BACKEND_DIR, engine, store_transaction


def migration_config():
    return Config(str(BACKEND_DIR / "alembic.ini"))


def upgrade_database(target_engine=engine):
    config = migration_config()
    with target_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def seed_demo():
    from app.core import flow
    from app.core.engine import confirm_slot, edit_slot, mark_unknown, skip_slot
    from app.core.errors import SessionNotFound
    from app.llm.fake import FakeLLM

    sid = "demo_c6_001"
    with store_transaction() as store:
        try:
            store.get(sid)
        except SessionNotFound:
            pass
        else:
            print(f"Synthetic session {sid} already exists; kept unchanged.")
            return
        state = flow.start_session(patient_ref="synthetic-demo")
        state.session_id = sid
        store.create(state)
        flow.ingest_message(
            state, "I've had a fever and sore throat for 3 days", FakeLLM()
        )
        store.save(state)
        # This seed knows the exact input message; ordinary DAO saves do not guess provenance.
        message = store.list_messages(sid)[0]
        for candidate in store.list_candidates(sid):
            quote = candidate["payload"].get("evidence_span")
            if quote and quote in message["text"]:
                store.add_source_reference(
                    sid,
                    candidate["slot_id"],
                    message_id=message["message_id"],
                    candidate_id=candidate["candidate_id"],
                    quote=quote,
                )
        confirm_slot(state, "chief_complaint")
        edit_slot(state, "symptom_severity", "mild")
        edit_slot(state, "symptom_severity", "moderate")
        mark_unknown(state, "current_medications")
        skip_slot(state, "past_conditions")
        store.save(state)
    print(
        f"Created synthetic session {sid}, including candidates and correction history."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "check", "seed"])
    args = parser.parse_args()
    if args.action == "init":
        upgrade_database()
        print("Database migrations are up to date.")
    elif args.action == "seed":
        seed_demo()
    else:
        with engine.connect() as connection:
            heads = MigrationContext.configure(connection).get_current_heads()
            expected = tuple(
                ScriptDirectory.from_config(migration_config()).get_heads()
            )
            print("Migration:", heads)
            print("Tables:", inspect(connection).get_table_names())
            if set(heads) != set(expected):
                raise SystemExit(
                    "Database needs migrations: python -m app.db.manage init"
                )


if __name__ == "__main__":
    main()
