import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import streamlit as st

from frontend.api_client import (
    API_URL,
    delete_session_by_id_and_email,
    fetch_session_by_id_and_email,
    fetch_session_history,
)

ABOUT_EU_AI_ACT_PATH = "/about-eu-ai-act"
INTERNAL_API_HOSTNAMES = {"backend"}


def _build_about_eu_ai_act_url(api_url: str) -> str:
    """Build the sidebar link target for the About EU AI Act page.

    Args:
        api_url: Backend base URL used by frontend HTTP requests.

    Returns:
        Relative path when API URL points to an internal Docker hostname,
        otherwise an absolute URL rooted at the provided API URL.
    """
    parsed = urlparse(api_url)

    if parsed.hostname in INTERNAL_API_HOSTNAMES:
        return ABOUT_EU_AI_ACT_PATH

    return f"{api_url.rstrip('/')}{ABOUT_EU_AI_ACT_PATH}"


def _format_assessment_created_at(created_at: str) -> str:
    """Format assessment timestamp for display in UTC without conversion.

    Args:
        created_at: Timestamp from backend session metadata.

    Returns:
        UTC timestamp in "YYYY-MM-DD HH:MM UTC" format or original value when parsing fails.
    """
    if not created_at:
        return created_at

    # Current API format: ISO 8601 UTC timestamp from backend.
    try:
        parsed_iso = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed_iso.tzinfo is None:
            parsed_iso = parsed_iso.replace(tzinfo=timezone.utc)
        return parsed_iso.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        pass

    # Legacy API format fallback: "Mar 04, 07:30 PM" (already UTC in this app).
    try:
        datetime.strptime(created_at, "%b %d, %I:%M %p")
        return f"{created_at} UTC"
    except ValueError:
        return created_at


def render_sidebar():
    with st.sidebar:
        st.markdown(
            """
            <style>
                [data-testid="stSidebarHeader"] {
                    display: flex;
                    -webkit-box-pack: justify;
                    justify-content: space-between;
                    -webkit-box-align: center;
                    margin-top: 1rem;
                    margin-bottom: 0;
                    height: 0;
                }
                [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:last-child {
                    margin-top: auto;
                }
                [data-testid="stSidebar"]  [data-testid="stSidebarUserContent"] {
                    padding-bottom: 1rem;
                }
                [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] hr {
                    margin: 1em 0;
                }
                [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
                    margin-bottom: 0;
                }
                section[data-testid="stSidebar"] a {
                    color: black !important;
                    font-weight: bold;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            if st.button("Log out", use_container_width=True):
                st.logout()
                st.stop()
            st.divider()

        billing_state = st.session_state.get("billing_state")
        if billing_state:
            credits_left_today = int(billing_state.get("credits_left_today", 0))
            daily_limit = int(billing_state.get("daily_limit", 20))
            resets_at_utc = billing_state.get("resets_at_utc", "")
            st.caption(f"Credits left today: {credits_left_today}/{daily_limit}")
            if resets_at_utc:
                st.caption(f"Resets at: {resets_at_utc}")
        else:
            st.caption("Credits left today: unavailable")

        about_url = _build_about_eu_ai_act_url(API_URL)
        st.markdown(f"[Learn about EU AI Act]({about_url})")

        st.divider()
        if st.button("New Assessment", icon=":material/add_circle:", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.ai_tool_name = None
            st.session_state.tool_report_resp = None
            st.session_state.pdf_data = None
            st.rerun()

        st.write("### Assessment History")
        if st.button("Refresh history", use_container_width=True):
            st.session_state.history_needs_refresh = True
            st.rerun()

        if st.session_state.get("history_needs_refresh", True):
            st.session_state.history_cache = fetch_session_history(st.user.email)
            st.session_state.history_needs_refresh = False

        history = st.session_state.get("history_cache", [])

        if not history:
            st.caption("No previous assessments found.")
        else:
            for session in history:
                tool = session.get("ai_tool", "Unknown Tool")
                display_tool = tool
                session_id = session["session_id"]

                time_str = session.get("created_at", "")
                formatted_time = _format_assessment_created_at(time_str)

                load_col, delete_col = st.columns([0.70, 0.30])
                with load_col:
                    if st.button(
                            f"{display_tool}",
                            key=f"load_{session_id}",
                            use_container_width=True,
                    ):
                        fetch_session_by_id_and_email(session_id, st.user.email)
                        st.rerun()
                with delete_col:
                    with st.popover("", icon=":material/more_horiz:", use_container_width=True):
                        st.caption(f"Created: {formatted_time}" if formatted_time else "Created: unknown")
                        if st.button(
                                "Remove assessment",
                                key=f"delete_{session_id}",
                                use_container_width=True,
                        ):
                            deleted = delete_session_by_id_and_email(session_id, st.user.email)
                            if deleted and st.session_state.session_id == session_id:
                                st.session_state.session_id = str(uuid.uuid4())
                                st.session_state.ai_tool_name = None
                                st.session_state.tool_report_resp = None
                                st.session_state.pdf_data = None
                            if deleted:
                                st.session_state.history_cache = [
                                    item
                                    for item in st.session_state.get("history_cache", [])
                                    if item.get("session_id") != session_id
                                ]
                            if deleted:
                                st.rerun()
