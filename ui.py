import uuid

import requests
import streamlit as st

st.set_page_config(page_title="PD AI Tool Assessment Agent")
st.title("PD AI Tool Assessment Agent")

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
            response = requests.post("http://localhost:8000/run", json=payload)

            if response.ok:
                st.session_state.tool_report_resp = response.json().get("summary")
                st.session_state.ai_tool_name = ai_tool
                st.session_state.pdf_data = None
            else:
                st.error("Failed to assess AI tool.")

if st.session_state.tool_report_resp:
    st.divider()

    col1, col2 = st.columns([1, 4])

    with col1:
        if st.button("Generate PDF", key="pdf_generate"):
            try:
                with st.spinner("Generating PDF..."):
                    pdf_response = requests.get(
                        "http://localhost:8000/pdf",
                        params={"session_id": st.session_state.session_id},
                    )

                    if pdf_response.ok:
                        st.session_state.pdf_data = pdf_response.content
                    else:
                        st.error(f"Failed to generate PDF: {pdf_response.status_code}")
                        st.session_state.pdf_data = None

            except Exception as e:
                st.error(f"Download error: {e}")
                st.session_state.pdf_data = None

    with col2:
        if st.session_state.pdf_data:
            tool_name = st.session_state.ai_tool_name or "unknown"
            safe_filename = "".join(
                c if c.isalnum() or c in (" ", "-", "_") else "_" for c in tool_name
            )
            st.download_button(
                label="Download PDF",
                data=st.session_state.pdf_data,
                file_name=f"ai_tool_assessment_{safe_filename}.pdf",
                mime="application/pdf",
                key="pdf_download",
            )

    st.markdown(st.session_state.tool_report_resp)
