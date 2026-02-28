import uuid
from datetime import datetime

import streamlit as st

from frontend.api_client import (
    API_URL,
    delete_session_by_id_and_email,
    fetch_session_by_id_and_email,
    fetch_session_history,
)


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

        st.markdown(f"[Learn about EU AI Act]({API_URL}/about-eu-ai-act)")

        st.divider()
        if st.button("New Assessment", icon=":material/add_circle:", use_container_width=True):
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
                display_tool = tool
                session_id = session["session_id"]

                time_str = session.get("created_at", "")
                formatted_time = time_str

                if time_str:
                    try:
                        parsed_time = datetime.strptime(time_str, "%b %d, %I:%M %p")
                        formatted_time = parsed_time.strftime("%b %d, %H:%M")
                    except ValueError:
                        pass

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
                                st.rerun()
