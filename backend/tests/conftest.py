import os

# The pre-product backend (/api/sessions and the app/core engine) is no longer
# mounted by default — app/product/ replaced it and only reuses check_safety.
# Its tests still describe working behaviour, so they run against it here until
# the team decides whether to delete that stack outright. Set before any test
# module imports app.core.main, which reads this flag at import time.
os.environ.setdefault("ENABLE_LEGACY_API", "1")

import pytest

from app.core.models import SessionState
from app.core.schema import SCHEMA_VERSION, build_initial_slots


def make_state(session_id: str = "s1") -> SessionState:
    return SessionState(
        session_id=session_id,
        schema_version=SCHEMA_VERSION,
        slots=build_initial_slots(),
    )


@pytest.fixture
def state() -> SessionState:
    return make_state()


@pytest.fixture
def database_factory(tmp_path):
    """Each test gets a migrated, disposable database; never touches preconsult.db."""
    from sqlalchemy import URL
    from sqlalchemy.orm import sessionmaker
    from app.db.manage import upgrade_database
    from app.db.session import create_db_engine

    engine = create_db_engine(URL.create("sqlite", database=str(tmp_path / "test.db")))
    upgrade_database(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()
