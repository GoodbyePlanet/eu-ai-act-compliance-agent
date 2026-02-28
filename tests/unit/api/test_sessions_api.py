from fastapi.testclient import TestClient

import compliance_agent.api.app as app_module
from compliance_agent.api.app import create_app
from compliance_agent.billing import AuthenticatedUser, get_authenticated_user
from compliance_agent.config import APP_NAME


class _Session:
    def __init__(self, session_id: str):
        self.id = session_id
        self.state = {"ai_tool": "Notion AI", "summary": "summary"}


class _FakeSessionService:
    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str, str], _Session] = {}
        self.raise_on_delete = False
        self.last_get_call: tuple[str, str, str] | None = None
        self.last_delete_call: tuple[str, str, str] | None = None

    async def get_session(self, app_name: str, user_id: str, session_id: str):
        self.last_get_call = (app_name, user_id, session_id)
        return self._sessions.get((app_name, user_id, session_id))

    async def delete_session(self, app_name: str, user_id: str, session_id: str) -> None:
        self.last_delete_call = (app_name, user_id, session_id)
        if self.raise_on_delete:
            raise RuntimeError("db failure")
        self._sessions.pop((app_name, user_id, session_id), None)

    def add_session(self, app_name: str, user_id: str, session_id: str) -> None:
        self._sessions[(app_name, user_id, session_id)] = _Session(session_id)


class _NoBillingService:
    def is_enabled(self) -> bool:
        return False


class _DummyAgent:
    async def execute(self, payload: object):
        return {"summary": "ok", "session_id": "session-1"}


def _build_client(monkeypatch, fake_session_service: _FakeSessionService) -> TestClient:
    monkeypatch.setattr(app_module, "BillingService", _NoBillingService)
    monkeypatch.setattr(app_module, "session_service", fake_session_service)

    app = create_app(agent=_DummyAgent())
    app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
        subject="google-sub-1",
        email="user@example.com",
    )
    return TestClient(app)


def test_delete_session_returns_success(monkeypatch) -> None:
    """Delete endpoint should remove an existing user session."""
    fake_session_service = _FakeSessionService()
    fake_session_service.add_session(
        app_name=APP_NAME,
        user_id="user@example.com",
        session_id="session-1",
    )
    client = _build_client(monkeypatch=monkeypatch, fake_session_service=fake_session_service)

    response = client.delete("/sessions/session-1")

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "session-1",
        "deleted": True,
        "message": "Session deleted successfully.",
    }
    assert fake_session_service.last_get_call == (
        APP_NAME,
        "user@example.com",
        "session-1",
    )
    assert fake_session_service.last_delete_call == (
        APP_NAME,
        "user@example.com",
        "session-1",
    )


def test_delete_session_returns_404_when_missing(monkeypatch) -> None:
    """Delete endpoint should return 404 when a session does not exist."""
    fake_session_service = _FakeSessionService()
    client = _build_client(monkeypatch=monkeypatch, fake_session_service=fake_session_service)

    response = client.delete("/sessions/session-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Session not found"


def test_delete_session_returns_500_when_delete_fails(monkeypatch) -> None:
    """Delete endpoint should return 500 when backend deletion fails."""
    fake_session_service = _FakeSessionService()
    fake_session_service.raise_on_delete = True
    fake_session_service.add_session(
        app_name=APP_NAME,
        user_id="user@example.com",
        session_id="session-1",
    )
    client = _build_client(monkeypatch=monkeypatch, fake_session_service=fake_session_service)

    response = client.delete("/sessions/session-1")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to delete session"
