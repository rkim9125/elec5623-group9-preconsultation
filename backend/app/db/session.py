"""Connections and transaction boundaries; never share an ORM Session globally."""

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.errors import PersistenceConflict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def create_db_engine(database_url):
    url = make_url(database_url)
    options = {}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 10}
        if url.database in (None, "", ":memory:"):
            options["poolclass"] = StaticPool
        elif not Path(url.database).is_absolute():
            url = url.set(database=str(BACKEND_DIR / url.database))
    result = create_engine(url, **options)
    if result.dialect.name == "sqlite":

        @event.listens_for(result, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return result


engine = create_db_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def store_transaction(factory=None):
    """All calls in this block commit together or roll back together."""
    from app.db.store import DatabaseSessionStore

    try:
        with (factory or SessionLocal).begin() as db:
            yield DatabaseSessionStore(db)
    except OperationalError as exc:
        if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
            raise PersistenceConflict(
                "Database is busy; reload the session and retry."
            ) from exc
        raise
