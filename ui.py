import uuid

import requests
import streamlit as st

st.set_page_config(page_title="PD AI Tool Assessment Agent")
st.title("PD AI Tool Assessment Agent")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "report_data" not in st.session_state:
    st.session_state.tool_report_resp = None

ai_tool = st.text_area("Write the name of the AI tool to assess", placeholder="e.g. Notion AI")

if st.button("Submit"):
    if not ai_tool:
        st.warning("Please fill in name of the AI tool to assess.")
    else:
        with st.spinner("Agent is browsing the web for compliance docs... This may take a few minutes...."):
            payload = {"ai_tool": ai_tool, "session_id": st.session_state.session_id}
            response = requests.post("http://localhost:8000/run", json=payload)

            if response.ok:
                st.session_state.tool_report_resp = response.json().get("summary")
            else:
                st.error("Failed to assess AI tool.")

if st.session_state.tool_report_resp:
    st.divider()
    if st.button("Looks good, download PDF", key="pdf_download", disabled=False):
        try:
            st.session_state.pdf_downloading = True
            pdf_response = requests.get(
                "http://localhost:8000/pdf",
                params={"session_id": st.session_state.session_id}
            )

            if pdf_response.ok:
                st.download_button(
                    label="Download PDF",
                    data=pdf_response.content,
                    file_name=f"ai_tool_assessment_{ai_tool}.pdf"
                )
            else:
                st.error("Failed to generate PDF")

        except Exception as e:
            st.error(f"Download error: {e}")

        finally:
            st.session_state.pdf_downloading = False

    st.markdown(st.session_state.tool_report_resp)
