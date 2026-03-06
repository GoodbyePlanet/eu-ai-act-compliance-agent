import uuid

import streamlit as st

from frontend.auth import require_login

st.set_page_config(
    page_title="AI Tool Assessment Agent",
    page_icon="static/favicon.png",
    layout="centered",
    initial_sidebar_state="collapsed",
)

require_login()

from compliance_agent.logging_config import setup_logging

setup_logging(logger_name="frontend", propagate=False)

# Import authenticated-only modules after login so the /app login screen can
# render without paying full app bootstrap import cost.
from frontend.api_client import fetch_ui_bootstrap
from frontend.main_content import render_main_content
from frontend.sidebar import render_sidebar

if "initialized" not in st.session_state:
    bootstrap = fetch_ui_bootstrap()
    recent_session = None if bootstrap is None else bootstrap.get("recent_session")

    if recent_session:
        st.session_state.session_id = recent_session.get("session_id")
        st.session_state.ai_tool_name = recent_session.get("ai_tool")
        st.session_state.tool_report_resp = recent_session.get("summary")
    else:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.ai_tool_name = None
        st.session_state.tool_report_resp = None

    st.session_state.billing_state = None if bootstrap is None else bootstrap.get("billing")
    st.session_state.history_cache = [] if bootstrap is None else bootstrap.get("sessions", [])
    st.session_state.history_needs_refresh = bootstrap is None
    st.session_state.pdf_data = None
    st.session_state.initialized = True

# Safety net for missing variables
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "tool_report_resp" not in st.session_state:
    st.session_state.tool_report_resp = None
if "ai_tool_name" not in st.session_state:
    st.session_state.ai_tool_name = None
if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None
if "billing_state" not in st.session_state:
    st.session_state.billing_state = None
if "history_cache" not in st.session_state:
    st.session_state.history_cache = []
if "history_needs_refresh" not in st.session_state:
    st.session_state.history_needs_refresh = True

if st.session_state.get("backend_unavailable", False):
    st.warning("Something went wrong with the backend API. Please try again later.")

render_sidebar()
render_main_content()
