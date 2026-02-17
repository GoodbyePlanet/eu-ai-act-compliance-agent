import os
from typing import Any, Dict, List, Optional, TypedDict

import requests
import streamlit as st

from compliance_agent.api import AssessRequest


class SessionInfoDict(TypedDict):
    """Type for session information returned by API."""

    session_id: str
    ai_tool: Optional[str]
    summary: Optional[str]


class SessionListItemDict(TypedDict):
    """Type for individual session in the sessions list."""

    session_id: str
    ai_tool: str
    created_at: str


API_URL = os.getenv("API_URL", "http://localhost:8000")


def fetch_recent_session(email: str) -> Optional[SessionInfoDict]:
    """
    Fetch the most recent session for a user.

    Args:
        email: User email address.

    Returns:
        Session information if found, otherwise None.
    """
    try:
        response = requests.get(
            f"{API_URL}/sessions/recent", params={"user_email": email}
        )
        if response.ok:
            data: Optional[SessionInfoDict] = response.json()
            return data
    except Exception as e:
        st.error(f"Could not connect to backend to check recent sessions: {e}")
    return None


def fetch_session_history(email: str) -> List[SessionListItemDict]:
    """
    Fetch all historical sessions for a user.

    Args:
        email: User email address.

    Returns:
        List of session items, empty list if none found or on error.
    """
    try:
        response = requests.get(f"{API_URL}/sessions", params={"user_email": email})
        if response.ok:
            data: Dict[str, List[SessionListItemDict]] = response.json()
            return data.get("sessions", [])
    except Exception as e:
        st.error(f"Could not connect to backend to fetch session history: {e}")
    return []


def load_historical_session(session_id: str, email: str) -> None:
    """
    Load a historical session and update Streamlit session state.

    Args:
        session_id: Unique session identifier.
        email: User email address.
    """
    try:
        response = requests.get(
            f"{API_URL}/sessions/{session_id}", params={"user_email": email}
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
    """
    Run a compliance assessment for the specified AI tool.

    Args:
        payload: Assessment request containing AI tool name and optional session ID.

    Returns:
        HTTP response from the assessment API.
    """
    return requests.post(f"{API_URL}/run", json=payload.model_dump())


def generate_pdf(session_id: str, email: str) -> requests.Response:
    """
    Generate a PDF report for a given session.

    Args:
        session_id: Unique session identifier.
        email: User email address.

    Returns:
        HTTP response containing PDF content.
    """
    return requests.get(
        f"{API_URL}/pdf", params={"session_id": session_id, "user_email": email}
    )
