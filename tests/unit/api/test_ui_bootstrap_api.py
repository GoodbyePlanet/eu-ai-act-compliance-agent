from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

import compliance_agent.api.app as app_module
from compliance_agent.api.app import create_app
from compliance_agent.billing import AuthenticatedUser, get_authenticated_user
from compliance_agent.config import APP_NAME


@dataclass(frozen=True)
class _FakeCreditState:
    daily_limit: int
    used_today: int
    credits_left_today: int
    can_run_request: bool
    resets_at_utc: str


class _FakeBillingService:
    def is_enabled(self) -> bool:
        return True

    async def ensure_user(self, google_sub: str, email: str) -> Any:
        return type("UserRef", (), {"id": "user-123", "email": email})()

    async def get_daily_credit_state(self, user_id: str) -> _FakeCreditState:
        return _FakeCreditState(
            daily_limit=20,
            used_today=5,
            credits_left_today=15,
            can_run_request=True,
            resets_at_utc="2026-03-05T00:00:00+00:00",
        )


class _FailingBillingService:
    def is_enabled(self) -> bool:
        return True

    async def ensure_user(self, google_sub: str, email: str) -> Any:
        raise RuntimeError("billing unavailable")

    async def get_daily_credit_state(self, user_id: str) -> _FakeCreditState:
        raise RuntimeError("billing unavailable")


class _SessionMeta:
    def __init__(self, session_id: str, last_update_time: float, state: dict | None = None):
        self.id = session_id
        self.last_update_time = last_update_time
        self.state = state or {}


class _SessionFull:
    def __init__(self, session_id: str, state: dict):
        self.id = session_id
        self.state = state


class _FakeSessionService:
    def __init__(self) -> None:
        self._sessions_meta = [
            _SessionMeta("session-older", 600.0, {"ai_tool": "Tool A"}),
            _SessionMeta("session-recent", 990.0, {"ai_tool": "Tool B"}),
        ]
        self._sessions_full = {
            (APP_NAME, "user@example.com", "session-recent"): _SessionFull(
                "session-recent",
                {"ai_tool": "Tool B", "summary": "Recent summary"},
            )
        }

    async def list_sessions(self, app_name: str, user_id: str):
        assert app_name == APP_NAME
        assert user_id == "user@example.com"
        return type("ListResponse", (), {"sessions": self._sessions_meta})()

    async def get_session(self, app_name: str, user_id: str, session_id: str):
        return self._sessions_full.get((app_name, user_id, session_id))


class _FailingSessionService:
    async def list_sessions(self, app_name: str, user_id: str):
        raise RuntimeError("session backend unavailable")

    async def get_session(self, app_name: str, user_id: str, session_id: str):
        return None


class _DummyAgent:
    async def execute(self, payload: object):
        return {"summary": "ok", "session_id": "session-1"}


def _build_client(monkeypatch, billing_service_cls: type, session_service: object) -> TestClient:
    monkeypatch.setattr(app_module, "BillingService", billing_service_cls)
    monkeypatch.setattr(app_module, "session_service", session_service)
    monkeypatch.setattr(app_module.time, "time", lambda: 1000.0)

    app = create_app(agent=_DummyAgent())
    app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
        subject="google-sub-1",
        email="user@example.com",
    )
    return TestClient(app)


def test_ui_bootstrap_returns_combined_payload(monkeypatch) -> None:
    """Bootstrap endpoint should return billing, sessions, and recent session in one response."""
    client = _build_client(
        monkeypatch=monkeypatch,
        billing_service_cls=_FakeBillingService,
        session_service=_FakeSessionService(),
    )

    response = client.get("/ui/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing"] == {
        "daily_limit": 20,
        "used_today": 5,
        "credits_left_today": 15,
        "can_run_request": True,
        "resets_at_utc": "2026-03-05T00:00:00+00:00",
    }
    assert payload["recent_session"] == {
        "session_id": "session-recent",
        "ai_tool": "Tool B",
        "summary": "Recent summary",
    }
    assert payload["sessions"] == [
        {
            "session_id": "session-recent",
            "ai_tool": "Tool B",
            "created_at": "1970-01-01T00:16:30+00:00",
        },
        {
            "session_id": "session-older",
            "ai_tool": "Tool A",
            "created_at": "1970-01-01T00:10:00+00:00",
        },
    ]


def test_ui_bootstrap_degrades_when_backends_fail(monkeypatch) -> None:
    """Bootstrap endpoint should still return a valid shape when sessions or billing fail."""
    client = _build_client(
        monkeypatch=monkeypatch,
        billing_service_cls=_FailingBillingService,
        session_service=_FailingSessionService(),
    )

    response = client.get("/ui/bootstrap")

    assert response.status_code == 200
    assert response.json() == {
        "billing": None,
        "recent_session": None,
        "sessions": [],
    }
