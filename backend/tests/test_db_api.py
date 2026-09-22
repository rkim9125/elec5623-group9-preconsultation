from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.core.main import create_app
from app.core.store import get_store
from app.db.models import SessionRecord
from app.db.session import store_transaction
from app.db.store import DatabaseSessionStore


def make_app(factory):
    app = create_app()

    def dependency():
        with store_transaction(factory) as store:
            yield store

    app.dependency_overrides[get_store] = dependency
    return app


def test_recreated_app_reads_messages_corrections_and_summary(database_factory):
    with TestClient(make_app(database_factory)) as client:
        sid = client.post("/api/sessions", json={}).json()["session_id"]
        assert (
            client.post(
                f"/api/sessions/{sid}/messages", json={"text": "sore throat"}
            ).status_code
            == 200
        )
        for value in ("mild", "moderate"):
            assert (
                client.post(
                    f"/api/sessions/{sid}/slots/symptom_severity",
                    json={"action": "edit", "value": value},
                ).status_code
                == 200
            )
        assert client.post(f"/api/sessions/{sid}/complete").status_code == 200
        original = client.get(f"/api/sessions/{sid}").json()
    with TestClient(make_app(database_factory)) as restarted:
        assert restarted.get(f"/api/sessions/{sid}").json() == original
        assert restarted.get(f"/api/sessions/{sid}/summary").status_code == 200
    with store_transaction(database_factory) as store:
        assert store.list_summary_versions(sid)[0]["approved_at"] is None


def test_complete_route_rolls_back_summary_if_state_save_fails(
    database_factory, monkeypatch
):
    with TestClient(
        make_app(database_factory), raise_server_exceptions=False
    ) as client:
        sid = client.post("/api/sessions", json={}).json()["session_id"]

        def fail_after_write(self, state):
            raise RuntimeError("injected failure after put_summary")

        monkeypatch.setattr(DatabaseSessionStore, "save", fail_after_write)
        response = client.post(f"/api/sessions/{sid}/complete")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL"
    with store_transaction(database_factory) as store:
        assert store.get(sid).status.value == "in_progress"
        assert store.list_summary_versions(sid) == []


def test_commit_failure_does_not_return_false_success(database_factory):
    def fail_commit(_session):
        raise RuntimeError("injected commit failure")

    event.listen(database_factory, "before_commit", fail_commit)
    try:
        with TestClient(
            make_app(database_factory), raise_server_exceptions=False
        ) as client:
            response = client.post("/api/sessions", json={})
            assert response.status_code == 500
            assert response.json()["error"]["code"] == "INTERNAL"
    finally:
        event.remove(database_factory, "before_commit", fail_commit)
    with database_factory() as db:
        assert db.scalar(select(func.count()).select_from(SessionRecord)) == 0
