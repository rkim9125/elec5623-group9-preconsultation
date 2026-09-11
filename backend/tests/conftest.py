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
