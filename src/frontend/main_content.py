import uuid

import streamlit as st

from frontend import fetch_billing_state, generate_pdf, run_assessment


def render_main_content():
    st.markdown(f"Welcome, **{st.user.name}**")
    st.title("AI Tool Assessment Agent")

    billing_state = st.session_state.get("billing_state")
    credits_left_today = None if not billing_state else int(billing_state.get("credits_left_today", 0))
    is_active_session = st.session_state.ai_tool_name is not None

    if is_active_session:
        st.info(f"Currently assessing: **{st.session_state.ai_tool_name}**")
        input_label = "Provide feedback, ask for revisions, or ask follow-up questions:"
        input_placeholder = "e.g., Re-write the summary to focus strictly on GDPR compliance..."
        input_value = ""
    else:
        input_label = "Write the name of the AI tool to assess"
        input_placeholder = "e.g. Notion AI"
        input_value = ""

    user_input = st.text_area(
        input_label,
        value=input_value,
        placeholder=input_placeholder,
        key=f"input_{st.session_state.session_id}",
    )

    can_submit = credits_left_today is not None and credits_left_today > 0
    if credits_left_today == 0:
        st.warning("Daily limit reached (20/20). Try again after the UTC reset.")
    elif credits_left_today is None:
        st.warning("Could not load daily credits. Please refresh balance and try again.")

    if st.button("Submit", disabled=not can_submit):
        if not user_input:
            st.warning("Please fill in the name of the AI tool to assess.")
        else:
            with st.spinner("Agent is browsing the web for compliance docs... This may take a few minutes...."):
                payload = {
                    "ai_tool": user_input,
                    "session_id": st.session_state.session_id,
                    "request_id": str(uuid.uuid4()),
                    "user_email": st.user.email,
                }
                response = run_assessment(payload)

                if response.ok:
                    res_json = response.json()
                    st.session_state.tool_report_resp = res_json.get("summary")
                    if not is_active_session:
                        st.session_state.ai_tool_name = user_input

                    st.session_state.billing_state = fetch_billing_state()
                    st.session_state.pdf_data = None
                    st.rerun()
                else:
                    detail = "Failed to assess AI tool."
                    try:
                        detail = response.json().get("detail", detail)
                    except Exception:
                        pass
                    st.error(detail)

    if st.session_state.tool_report_resp:
        st.divider()

        try:
            with st.spinner("Generating PDF..."):
                pdf_response = generate_pdf(st.session_state.session_id, st.user.email)

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
