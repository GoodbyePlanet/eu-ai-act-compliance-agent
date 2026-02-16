import os
import uuid
from datetime import datetime

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Tool Assessment Agent",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# --- Authentication ---
if not st.user.is_logged_in:
    st.markdown(
        "<h1 style='text-align: center; margin-top: 50px; max-width: 800px;'>EU AI Act Compliance Agent</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; max-width: 800px;'>To start the EU AI Act assessment,"
        " please authenticate with your Google Workspace account.</p>",
        unsafe_allow_html=True,
    )
    left_co, cent_co, last_co = st.columns([1, 1, 1])
    with cent_co:
        if st.button("Log in with Google", use_container_width=True):
            st.login()
    st.stop()


# --- API Helper Functions ---
def fetch_recent_session(email):
    """Fetches a session if created in the last 5 minutes."""
    try:
        recent_sessions_response = requests.get(f"{API_URL}/sessions/recent", params={"user_email": email})
        if recent_sessions_response.ok:
            return recent_sessions_response.json()
    except Exception as e:
        st.error(f"Could not connect to backend to check recent sessions: {e}")
    return None


def fetch_session_history(email):
    """Fetches all previous sessions for the sidebar."""
    try:
        session_history_response = requests.get(f"{API_URL}/sessions", params={"user_email": email})
        if session_history_response.ok:
            return session_history_response.json().get("sessions", [])
    except Exception:
        pass
    return []


def load_historical_session(session_id, email):
    """Loads a specific session from history into the current view."""
    try:
        session_response = requests.get(f"{API_URL}/sessions/{session_id}", params={"user_email": email})
        if session_response.ok:
            data = session_response.json()
            st.session_state.session_id = session_id
            st.session_state.ai_tool_name = data.get("ai_tool")
            st.session_state.tool_report_resp = data.get("summary")
            st.session_state.pdf_data = None
        else:
            st.error("Failed to load session data.")
    except Exception as e:
        st.error(f"Error loading session: {e}")


# --- Page Load / Reload / Initialization Logic ---
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

# --- Sidebar UI (Session History) ---
with st.sidebar:
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                height: 100vh;
            }
            /* Target the very last container inside the sidebar and push it down */
            [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:last-child {
                margin-top: auto;
            }
            [data-testid="stSidebarUserContent"] {
                padding-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True
    )

    if st.button("➕ New Assessment", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.ai_tool_name = None
        st.session_state.tool_report_resp = None
        st.session_state.pdf_data = None
        st.rerun()

    st.write("### Assessment History")
    history = fetch_session_history(st.user.email)

    if not history:
        st.caption("No previous assessments found.")
    else:
        for session in history:
            tool = session.get("ai_tool", "Unknown Tool")
            display_tool = tool if len(tool) <= 10 else tool[:10] + "..."
            time_str = session.get("created_at", "")
            if time_str:
                try:
                    parsed_time = datetime.strptime(time_str, "%b %d, %I:%M %p")
                    formatted_time = parsed_time.strftime("%b %d, %H:%M")
                except ValueError:
                    pass

            if st.button(f"{display_tool} - {formatted_time}", key=session["session_id"], use_container_width=True):
                load_historical_session(session["session_id"], st.user.email)
                st.rerun()

    with st.container():
        st.divider()
        st.write(f"Logged in as: **{st.user.email}**")
        if st.button("Log out", use_container_width=True):
            st.logout()


# --- Main Page UI ---
st.markdown(f"Welcome, **{st.user.name}**")
st.title("AI Tool Assessment Agent")

is_active_session = st.session_state.ai_tool_name is not None

if is_active_session:
    # They are looking at an existing report
    st.info(f"Currently assessing: **{st.session_state.ai_tool_name}**")
    input_label = "Provide feedback, ask for revisions, or ask follow-up questions:"
    input_placeholder = "e.g., Re-write the summary to focus strictly on GDPR compliance..."
    # Do NOT pre-fill the text area with the tool name if it's a follow up
    input_value = ""
else:
    # They are starting a brand new assessment
    input_label = "Write the name of the AI tool to assess"
    input_placeholder = "e.g. Notion AI"
    input_value = ""

user_input = st.text_area(
    input_label,
    value=input_value,
    placeholder=input_placeholder,
    key=f"input_{st.session_state.session_id}" # Force UI refresh on session change
)

if st.button("Submit Assessment"):
    if not user_input:
        st.warning("Please fill in the name of the AI tool to assess.")
    else:
        with st.spinner("Agent is browsing the web for compliance docs... This may take a few minutes...."):
            payload = {"ai_tool": user_input, "session_id": st.session_state.session_id, "user_email": st.user.email}
            response = requests.post(f"{API_URL}/run", json=payload)

            if response.ok:
                res = response.json().get("summary")
                st.session_state.tool_report_resp = res
                if not is_active_session:
                    st.session_state.ai_tool_name = user_input

                st.session_state.pdf_data = None
                st.rerun()  # Refresh so the new tool appears in the sidebar history
            else:
                st.error("Failed to assess AI tool.")

if st.session_state.tool_report_resp:
    st.divider()

    try:
        with st.spinner("Generating PDF..."):
            pdf_response = requests.get(
                f"{API_URL}/pdf",
                params={"session_id": st.session_state.session_id, "user_email": st.user.email},
            )

            if pdf_response.ok:
                tool_name = st.session_state.ai_tool_name or "unknown"
                safe_filename = "".join(
                    c if c.isalnum() or c in (" ", "-", "_") else "_" for c in tool_name
                )

                st.download_button(
                    label="Download Compliance Assessment PDF",
                    data=pdf_response.content,
                    file_name=f"ai_tool_assessment_{safe_filename}.pdf",
                    mime="application/pdf",
                    key="pdf_download",
                    help="Click to download the PDF report of the AI tool compliance assessment",
                )
            else:
                st.error(f"Failed to generate PDF: {pdf_response.status_code}")

    except Exception as e:
        st.error(f"PDF generation error: {e}")

    st.markdown(st.session_state.tool_report_resp)
