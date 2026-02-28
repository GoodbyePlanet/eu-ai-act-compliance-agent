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


class SessionDeleteResponseDict(TypedDict):
    """Type for a delete session response returned by API."""

    session_id: str
    deleted: bool
    message: str


class BillingStateDict(TypedDict):
    """Type for the daily quota state returned by API."""

    daily_limit: int
    used_today: int
    credits_left_today: int
    can_run_request: bool
    resets_at_utc: str


API_URL = os.getenv("API_URL", "http://localhost:8000")
BACKEND_UNAVAILABLE_MESSAGE = "Internal server error."


def _headers() -> Dict[str, str]:
    return get_auth_headers()


def _handle_unauthorized(response: requests.Response) -> None:
    """Force re-authentication when the backend rejects the bearer token."""
    if response.status_code != 401:
        return

    st.session_state.pop("initialized", None)
    st.session_state.pop("billing_state", None)
    st.error("Your sign-in token expired. Please log in again.")
    st.logout()
    st.rerun()


def _mark_backend_unavailable(error: Optional[Exception] = None) -> None:
    """Store backend availability status for centralized UI messaging."""
    st.session_state.backend_unavailable = True
    st.session_state.backend_error_detail = str(error) if error else None


def _mark_backend_available() -> None:
    """Clear backend availability status after a successful request."""
    st.session_state.backend_unavailable = False
    st.session_state.backend_error_detail = None


def _request(method: str, url: str, **kwargs: Any) -> Optional[requests.Response]:
    """Execute an HTTP request and centralize auth failure handling."""
    try:
        response = requests.request(method, url, **kwargs)
    except requests.exceptions.RequestException as exc:
        _mark_backend_unavailable(exc)
        return None
    except Exception:
        _mark_backend_unavailable()
        return None

    _mark_backend_available()
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


def delete_session_by_id_and_email(session_id: str, email: str) -> bool:
    """Delete a historical session and return whether the operation succeeded."""
    response = _request(
        "DELETE",
        f"{API_URL}/sessions/{session_id}",
        params={"user_email": email},
        headers=_headers(),
    )
    if not response:
        return False

    if response.ok:
        data: SessionDeleteResponseDict = response.json()
        return bool(data.get("deleted", False))

    st.error("Failed to delete session.")
    return False


def run_assessment(payload: AssessRequest) -> requests.Response:
    """Run a compliance assessment for the specified AI tool."""
    response = _request("POST", f"{API_URL}/run", json=payload, headers=_headers())
    if response is None:
        raise RuntimeError(BACKEND_UNAVAILABLE_MESSAGE)
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
        raise RuntimeError(BACKEND_UNAVAILABLE_MESSAGE)
    return response


def fetch_billing_state() -> Optional[BillingStateDict]:
    """Fetch the current authenticated user's daily quota state."""
    response = _request("GET", f"{API_URL}/billing/me", headers=_headers())
    if response and response.ok:
        return response.json()
    if response is not None:
        try:
            detail = response.json().get("detail", "Failed to load daily credits.")
        except Exception:
            detail = "Failed to load daily credits."
        st.error(detail)
    return None
