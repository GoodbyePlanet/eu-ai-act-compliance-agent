import uuid
from datetime import datetime

import streamlit as st

from frontend.api_client import API_URL, fetch_session_by_id_and_email, fetch_session_history


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
                [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                    height: 95vh;
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

        st.markdown(f"[Learn about EU AI ACT]({API_URL}/about-eu-ai-act)")

        st.write("### Assessment History")
        history = fetch_session_history(st.user.email)

        if not history:
            st.caption("No previous assessments found.")
        else:
            for session in history:
                tool = session.get("ai_tool", "Unknown Tool")
                display_tool = tool if len(tool) <= 10 else tool[:10] + "..."

                time_str = session.get("created_at", "")
                formatted_time = time_str

                if time_str:
                    try:
                        parsed_time = datetime.strptime(time_str, "%b %d, %I:%M %p")
                        formatted_time = parsed_time.strftime("%b %d, %H:%M")
                    except ValueError:
                        pass

                if st.button(f"{display_tool} - {formatted_time}", key=session["session_id"], use_container_width=True):
                    fetch_session_by_id_and_email(session["session_id"], st.user.email)
                    st.rerun()

        with st.container():
            st.divider()
            st.write(f"Logged in as: **{st.user.email}**")
            if st.button("Log out", use_container_width=True):
                st.logout()
                st.stop()
