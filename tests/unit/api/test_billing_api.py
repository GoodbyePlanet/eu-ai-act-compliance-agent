from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

import compliance_agent.api.app as app_module
from compliance_agent.api.app import create_app
from compliance_agent.billing import AuthenticatedUser, InsufficientCreditsError, get_authenticated_user


@dataclass(frozen=True)
class _FakeCreditState:
    request_units_balance: int
    free_request_units_remaining: int
    paid_request_units_remaining: int
    can_run_request: bool
    stripe_customer_exists: bool
    request_unit_price_eur: float


class _FakeBillingService:
    def is_enabled(self) -> bool:
        return True

    async def ensure_user(self, google_sub: str, email: str) -> Any:
        return type("UserRef", (), {"id": "user-123", "email": email})()

    async def get_credit_state(self, user_id: str) -> _FakeCreditState:
        return _FakeCreditState(
            request_units_balance=4,
            free_request_units_remaining=4,
            paid_request_units_remaining=0,
            can_run_request=True,
            stripe_customer_exists=False,
            request_unit_price_eur=0.2,
        )


class _OkAgent:
    async def execute(self, payload: object) -> dict[str, str]:
        return {"summary": "ok", "session_id": "session-1"}


class _InsufficientCreditsAgent:
    async def execute(self, payload: object) -> None:
        raise InsufficientCreditsError("No request units left. Buy credits to continue.")


def _build_client(monkeypatch, agent: object) -> TestClient:
    monkeypatch.setattr(app_module, "BillingService", _FakeBillingService)

    app = create_app(agent=agent)
    app.dependency_overrides[get_authenticated_user] = lambda: AuthenticatedUser(
        subject="google-sub-1",
        email="user@example.com",
    )
    return TestClient(app)


def test_run_returns_request_units_remaining(monkeypatch) -> None:
    """Run endpoint should include request-unit billing fields in response."""
    client = _build_client(monkeypatch=monkeypatch, agent=_OkAgent())

    response = client.post("/run", json={"ai_tool": "Notion AI"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "ok"
    assert payload["session_id"] == "session-1"
    assert payload["request_units_remaining"] == 4
    assert payload["billing_status"] == "ok"


def test_run_returns_402_for_insufficient_units(monkeypatch) -> None:
    """Run endpoint should return 402 when billing rejects request balance."""
    client = _build_client(monkeypatch=monkeypatch, agent=_InsufficientCreditsAgent())

    response = client.post("/run", json={"ai_tool": "Notion AI"})

    assert response.status_code == 402
    assert response.json()["detail"] == "No request units left. Buy credits to continue."


def test_billing_me_returns_request_unit_state(monkeypatch) -> None:
    """Billing me endpoint should expose request-unit based state fields."""
    client = _build_client(monkeypatch=monkeypatch, agent=_OkAgent())

    response = client.get("/billing/me")

    assert response.status_code == 200
    assert response.json() == {
        "request_units_balance": 4,
        "free_request_units_remaining": 4,
        "paid_request_units_remaining": 0,
        "can_run_request": True,
        "stripe_customer_exists": False,
        "request_unit_price_eur": 0.2,
    }
