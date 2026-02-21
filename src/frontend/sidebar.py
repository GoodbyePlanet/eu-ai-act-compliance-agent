import uuid
from datetime import datetime

import streamlit as st

from frontend.api_client import (
    API_URL,
    create_checkout_session,
    create_portal_session,
    fetch_billing_state,
    fetch_session_by_id_and_email,
    fetch_session_history,
)


def _refresh_billing_state() -> None:
    st.session_state.billing_state = fetch_billing_state()


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
                }
                [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:last-child {
                    margin-top: auto;
                }
                [data-testid="stSidebarUserContent"] {
                    padding-bottom: 1rem;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        billing_state = st.session_state.get("billing_state") or {}
        credits_balance = int(billing_state.get("credits_balance", 0))

        st.caption(f"Credits remaining: {credits_balance}")
        if st.button("↻ Refresh Credits", use_container_width=True):
            _refresh_billing_state()
            st.rerun()

        if st.button("➕ New Assessment", use_container_width=True, disabled=credits_balance <= 0):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.ai_tool_name = None
            st.session_state.tool_report_resp = None
            st.session_state.pdf_data = None
            st.rerun()

        st.write("### Buy Credits")
        buy_cols = st.columns(3)
        for col, pack_code, label in [
            (buy_cols[0], "CREDITS_5", "5"),
            (buy_cols[1], "CREDITS_20", "20"),
            (buy_cols[2], "CREDITS_50", "50"),
        ]:
            with col:
                if st.button(label, key=f"buy_{pack_code}", use_container_width=True):
                    result = create_checkout_session(pack_code)
                    if result and result.get("checkout_url"):
                        st.session_state.checkout_url = result["checkout_url"]

        if st.session_state.get("checkout_url"):
            st.link_button("Open Checkout", url=st.session_state["checkout_url"], use_container_width=True)

        if st.button("Billing & Invoices", use_container_width=True):
            portal = create_portal_session()
            if portal and portal.get("portal_url"):
                st.session_state.portal_url = portal["portal_url"]

        if st.session_state.get("portal_url"):
            st.link_button("Open Billing Portal", url=st.session_state["portal_url"], use_container_width=True)

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

                if st.button(
                    f"{display_tool} - {formatted_time}",
                    key=session["session_id"],
                    use_container_width=True,
                ):
                    fetch_session_by_id_and_email(session["session_id"], st.user.email)
                    st.rerun()

        with st.container():
            st.divider()
            st.write(f"Logged in as: **{st.user.email}**")
            if st.button("Log out", use_container_width=True):
                st.logout()
                st.stop()
