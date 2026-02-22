import os
from typing import Any, Dict, List, Optional, TypedDict

import requests
import streamlit as st

from compliance_agent.api import AssessRequest
from frontend.auth import get_auth_headers


class SessionInfoDict(TypedDict):
    """Type for session information returned by API."""

    session_id: str
    ai_tool: Optional[str]
    summary: Optional[str]


class SessionListItemDict(TypedDict):
    """Type for an individual session in the session list."""

    session_id: str
    ai_tool: str
    created_at: str


class BillingStateDict(TypedDict):
    """Type for billing state returned by API."""

    credits_balance: int
    free_credits_remaining: int
    paid_credits_remaining: int
    can_start_new_session: bool
    stripe_customer_exists: bool


API_URL = os.getenv("API_URL", "http://localhost:8000")


def _headers() -> Dict[str, str]:
    return get_auth_headers()


def _handle_unauthorized(response: requests.Response) -> None:
    """Force re-authentication when the backend rejects the bearer token."""
    if response.status_code != 401:
        return

    st.session_state.pop("initialized", None)
    st.session_state.pop("billing_state", None)
    st.session_state.pop("checkout_url", None)
    st.session_state.pop("portal_url", None)
    st.error("Your sign-in token expired. Please log in again.")
    st.logout()
    st.rerun()


def _request(method: str, url: str, **kwargs: Any) -> Optional[requests.Response]:
    """Execute an HTTP request and centralize auth failure handling."""
    try:
        response = requests.request(method, url, **kwargs)
    except Exception as e:
        st.error(f"Could not connect to backend: {e}")
        return None

    _handle_unauthorized(response)
    return response


def fetch_recent_session(email: str) -> Optional[SessionInfoDict]:
    """Fetch the most recent session for a user."""
    response = _request(
        "GET",
        f"{API_URL}/sessions/recent",
        params={"user_email": email},
        headers=_headers(),
    )
    if response and response.ok:
        data: Optional[SessionInfoDict] = response.json()
        return data
    return None


def fetch_session_history(email: str) -> List[SessionListItemDict]:
    """Fetch all historical sessions for a user."""
    response = _request(
        "GET",
        f"{API_URL}/sessions",
        params={"user_email": email},
        headers=_headers(),
    )
    if response and response.ok:
        data: Dict[str, List[SessionListItemDict]] = response.json()
        return data.get("sessions", [])
    return []


def fetch_session_by_id_and_email(session_id: str, email: str) -> None:
    """Load a historical session and update the Streamlit session state."""
    response = _request(
        "GET",
        f"{API_URL}/sessions/{session_id}",
        params={"user_email": email},
        headers=_headers(),
    )
    if not response:
        return

    if response.ok:
        data: SessionInfoDict = response.json()
        st.session_state.session_id = session_id
        st.session_state.ai_tool_name = data.get("ai_tool")
        st.session_state.tool_report_resp = data.get("summary")
        st.session_state.pdf_data = None
    else:
        st.error("Failed to load session data.")


def run_assessment(payload: AssessRequest) -> requests.Response:
    """Run a compliance assessment for the specified AI tool."""
    response = _request("POST", f"{API_URL}/run", json=payload, headers=_headers())
    if response is None:
        raise RuntimeError("Could not connect to backend.")
    return response


def generate_pdf(session_id: str, email: str) -> requests.Response:
    """Generate a PDF report for a given session."""
    response = _request(
        "GET",
        f"{API_URL}/pdf",
        params={"session_id": session_id, "user_email": email},
        headers=_headers(),
    )
    if response is None:
        raise RuntimeError("Could not connect to backend.")
    return response


def fetch_billing_state() -> Optional[BillingStateDict]:
    """Fetch the current authenticated user's billing state."""
    response = _request("GET", f"{API_URL}/billing/me", headers=_headers())
    if response and response.ok:
        return response.json()
    return None


def create_checkout_session(pack_code: str) -> Optional[Dict[str, Any]]:
    """Create a checkout session for a selected credit pack."""
    response = _request(
        "POST",
        f"{API_URL}/billing/checkout-session",
        json={"pack_code": pack_code},
        headers=_headers(),
    )
    if not response:
        return None

    if response.ok:
        return response.json()
    st.error(response.json().get("detail", "Failed to create checkout session."))
    return None


def create_portal_session() -> Optional[Dict[str, Any]]:
    """Create a Stripe billing portal session for invoices/receipts."""
    response = _request("POST", f"{API_URL}/billing/portal-session", headers=_headers())
    if not response:
        return None

    if response.ok:
        return response.json()
    st.error(response.json().get("detail", "Failed to create portal session."))
    return None
