from fastapi.testclient import TestClient

from compliance_agent.api.app import create_app
import compliance_agent.api.app as app_module


class DummyAgent:
    async def execute(self, payload: object) -> None:
        return None


def test_root_returns_landing_page_html():
    """Root endpoint should serve the landing page HTML file."""
    app = create_app(agent=DummyAgent())
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "EU AI ACT | Assessment Agent" in response.text
    assert "Initialize Assessment" in response.text


def test_about_route_returns_about_page_html():
    """About endpoint should serve the EU AI Act information page."""
    app = create_app(agent=DummyAgent())
    client = TestClient(app)

    response = client.get("/about-eu-ai-act")

    assert response.status_code == 200
    assert "About the EU AI Act" in response.text
    assert "Risk Tiers" in response.text


def test_about_route_returns_500_when_file_is_missing(monkeypatch):
    """Missing about a page file should return a server error."""

    def _raise_file_not_found(filename: str) -> str:
        raise FileNotFoundError(filename)

    monkeypatch.setattr(app_module, "_read_static_html", _raise_file_not_found)

    app = create_app(agent=DummyAgent())
    client = TestClient(app)

    response = client.get("/about-eu-ai-act")

    assert response.status_code == 500
    assert response.json()["detail"] == "About EU AI Act page is not available"
