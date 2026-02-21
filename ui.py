import uuid

import streamlit as st

from frontend import (
    fetch_billing_state,
    fetch_recent_session,
    render_main_content,
    render_sidebar,
    require_login,
)

st.set_page_config(
    page_title="AI Tool Assessment Agent",
    layout="centered",
    initial_sidebar_state="collapsed",
)

require_login()

if "initialized" not in st.session_state:
    recent_session = fetch_recent_session(st.user.email)

    if recent_session:
        st.session_state.session_id = recent_session.get("session_id")
        st.session_state.ai_tool_name = recent_session.get("ai_tool")
        st.session_state.tool_report_resp = recent_session.get("summary")
    else:
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.ai_tool_name = None
        st.session_state.tool_report_resp = None

    st.session_state.billing_state = fetch_billing_state()
    st.session_state.pdf_data = None
    st.session_state.checkout_url = None
    st.session_state.portal_url = None
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
    st.session_state.billing_state = fetch_billing_state()
if "checkout_url" not in st.session_state:
    st.session_state.checkout_url = None
if "portal_url" not in st.session_state:
    st.session_state.portal_url = None

render_sidebar()
render_main_content()
