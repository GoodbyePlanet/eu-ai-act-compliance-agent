from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

import compliance_agent.api.app as app_module
from compliance_agent.api.app import create_app
from compliance_agent.billing import AuthenticatedUser, InsufficientCreditsError, get_authenticated_user


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
            used_today=16,
            credits_left_today=4,
            can_run_request=True,
            resets_at_utc="2026-02-24T00:00:00+00:00",
        )


class _OkAgent:
    async def execute(self, payload: object) -> dict[str, str]:
        return {"summary": "ok", "session_id": "session-1"}


class _InsufficientCreditsAgent:
    async def execute(self, payload: object) -> None:
        raise InsufficientCreditsError("Daily limit reached (20/20). Try again after reset at 2026-02-24T00:00:00+00:00.")


def _build_client(monkeypatch, agent: object) -> TestClient:
    monkeypatch.setattr(app_module, "BillingService", _FakeBillingService)

    app = create_app(agent=agent)
    app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
        subject="google-sub-1",
        email="user@example.com",
    )
    return TestClient(app)


def test_run_returns_credits_left_today(monkeypatch) -> None:
    """Run endpoint should include daily quota fields in response."""
    client = _build_client(monkeypatch=monkeypatch, agent=_OkAgent())

    response = client.post("/run", json={"ai_tool": "Notion AI"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "ok"
    assert payload["session_id"] == "session-1"
    assert payload["credits_left_today"] == 4
    assert payload["billing_status"] == "ok"


def test_run_returns_402_for_daily_limit(monkeypatch) -> None:
    """Run endpoint should return 402 when the daily quota rejects the request."""
    client = _build_client(monkeypatch=monkeypatch, agent=_InsufficientCreditsAgent())

    response = client.post("/run", json={"ai_tool": "Notion AI"})

    assert response.status_code == 402
    assert "Daily limit reached" in response.json()["detail"]


def test_billing_me_returns_daily_quota_state(monkeypatch) -> None:
    """Billing me endpoint should expose daily quota fields."""
    client = _build_client(monkeypatch=monkeypatch, agent=_OkAgent())

    response = client.get("/billing/me")

    assert response.status_code == 200
    assert response.json() == {
        "daily_limit": 20,
        "used_today": 16,
        "credits_left_today": 4,
        "can_run_request": True,
        "resets_at_utc": "2026-02-24T00:00:00+00:00",
    }


def test_removed_checkout_route_returns_not_found(monkeypatch) -> None:
    """Checkout endpoint should be removed after Stripe deprecation."""
    client = _build_client(monkeypatch=monkeypatch, agent=_OkAgent())

    response = client.post("/billing/checkout-session", json={"pack_code": "CREDITS_5"})

    assert response.status_code == 404
