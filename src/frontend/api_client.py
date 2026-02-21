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


def fetch_recent_session(email: str) -> Optional[SessionInfoDict]:
    """Fetch the most recent session for a user."""
    try:
        response = requests.get(
            f"{API_URL}/sessions/recent",
            params={"user_email": email},
            headers=_headers(),
        )
        if response.ok:
            data: Optional[SessionInfoDict] = response.json()
            return data
    except Exception as e:
        st.error(f"Could not connect to backend to check recent sessions: {e}")
    return None


def fetch_session_history(email: str) -> List[SessionListItemDict]:
    """Fetch all historical sessions for a user."""
    try:
        response = requests.get(
            f"{API_URL}/sessions",
            params={"user_email": email},
            headers=_headers(),
        )
        if response.ok:
            data: Dict[str, List[SessionListItemDict]] = response.json()
            return data.get("sessions", [])
    except Exception as e:
        st.error(f"Could not connect to backend to fetch session history: {e}")
    return []


def fetch_session_by_id_and_email(session_id: str, email: str) -> None:
    """Load a historical session and update the Streamlit session state."""
    try:
        response = requests.get(
            f"{API_URL}/sessions/{session_id}",
            params={"user_email": email},
            headers=_headers(),
        )
        if response.ok:
            data: SessionInfoDict = response.json()
            st.session_state.session_id = session_id
            st.session_state.ai_tool_name = data.get("ai_tool")
            st.session_state.tool_report_resp = data.get("summary")
            st.session_state.pdf_data = None
        else:
            st.error("Failed to load session data.")
    except Exception as e:
        st.error(f"Error loading session: {e}")


def run_assessment(payload: AssessRequest) -> requests.Response:
    """Run a compliance assessment for the specified AI tool."""
    return requests.post(f"{API_URL}/run", json=payload, headers=_headers())


def generate_pdf(session_id: str, email: str) -> requests.Response:
    """Generate a PDF report for a given session."""
    return requests.get(
        f"{API_URL}/pdf",
        params={"session_id": session_id, "user_email": email},
        headers=_headers(),
    )


def fetch_billing_state() -> Optional[BillingStateDict]:
    """Fetch current authenticated user's billing state."""
    try:
        response = requests.get(f"{API_URL}/billing/me", headers=_headers())
        if response.ok:
            return response.json()
    except Exception as e:
        st.error(f"Failed to fetch billing state: {e}")
    return None


def create_checkout_session(pack_code: str) -> Optional[Dict[str, Any]]:
    """Create checkout session for a selected credit pack."""
    try:
        response = requests.post(
            f"{API_URL}/billing/checkout-session",
            json={"pack_code": pack_code},
            headers=_headers(),
        )
        if response.ok:
            return response.json()
        st.error(response.json().get("detail", "Failed to create checkout session."))
    except Exception as e:
        st.error(f"Checkout error: {e}")
    return None


def create_portal_session() -> Optional[Dict[str, Any]]:
    """Create Stripe billing portal session for invoices/receipts."""
    try:
        response = requests.post(f"{API_URL}/billing/portal-session", headers=_headers())
        if response.ok:
            return response.json()
        st.error(response.json().get("detail", "Failed to create portal session."))
    except Exception as e:
        st.error(f"Billing portal error: {e}")
    return None
