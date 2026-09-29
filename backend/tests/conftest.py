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
