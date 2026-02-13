import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Tool Assessment Agent",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if not st.user.is_logged_in:
    st.markdown(
        "<h1 style='text-align: center; margin-top: 50px; max-width: 800px;'>EU AI Act Compliance Agent</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; jmax-width: 800px;'>To start the EU AI Act assessment,"
        " please authenticate with your Google Workspace account.</p>",
        unsafe_allow_html=True,
    )
    left_co, cent_co, last_co = st.columns([1, 1, 1])
    with cent_co:
        if st.button("Log in with Google", use_container_width=True):
            st.login()

    st.stop()

st.markdown(f"Welcome, **{st.user.name}**")
st.title("AI Tool Assessment Agent")

with st.sidebar:
    st.write(f"Logged in as: {st.user.email}")
    if st.button("Log out"):
        st.logout()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "tool_report_resp" not in st.session_state:
    st.session_state.tool_report_resp = None

if "ai_tool_name" not in st.session_state:
    st.session_state.ai_tool_name = None

if "pdf_data" not in st.session_state:
    st.session_state.pdf_data = None

ai_tool = st.text_area(
    "Write the name of the AI tool to assess", placeholder="e.g. Notion AI"
)

if st.button("Submit"):
    if not ai_tool:
        st.warning("Please fill in name of the AI tool to assess.")
    else:
        with st.spinner(
            "Agent is browsing the web for compliance docs... This may take a few minutes...."
        ):
            payload = {"ai_tool": ai_tool, "session_id": st.session_state.session_id}
            response = requests.post(f"{API_URL}/run", json=payload)

            if response.ok:
                st.session_state.tool_report_resp = response.json().get("summary")
                st.session_state.ai_tool_name = ai_tool
                st.session_state.pdf_data = None
            else:
                st.error("Failed to assess AI tool.")

if st.session_state.tool_report_resp:
    st.divider()

    try:
        with st.spinner("Generating PDF..."):
            pdf_response = requests.get(
                f"{API_URL}/pdf",
                params={"session_id": st.session_state.session_id},
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
