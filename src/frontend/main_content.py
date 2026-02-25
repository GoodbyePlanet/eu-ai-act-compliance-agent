import uuid

import streamlit as st

from frontend import fetch_billing_state, generate_pdf, run_assessment


def render_main_content():
    if "assessment_in_progress" not in st.session_state:
        st.session_state.assessment_in_progress = False
    if "pending_assessment_payload" not in st.session_state:
        st.session_state.pending_assessment_payload = None

    st.markdown(
        """
        <style>
            [data-testid="stElementContainer"] [data-testid="stMarkdownContainer"] p strong a {
                color: black !important;
                font-weight: bold;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"Welcome, **{st.user.name}** - (**{st.user.email}**)")
    st.title("AI Tool Assessment Agent")

    billing_state = st.session_state.get("billing_state")
    credits_left_today = None if not billing_state else int(billing_state.get("credits_left_today", 0))
    is_active_session = st.session_state.ai_tool_name is not None
    is_processing = bool(st.session_state.assessment_in_progress)

    pending_error = st.session_state.pop("assessment_error_message", None)
    if pending_error:
        st.error(pending_error)

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
        if st.session_state.get("backend_unavailable", False):
            st.warning("Daily credits are unavailable because the backend API is offline.")
        else:
            st.warning("Could not load daily credits. Please refresh balance and try again.")

    submit_disabled = (not can_submit) or is_processing
    if st.button("Submit", disabled=submit_disabled):
        if not user_input:
            st.warning("Please fill in the name of the AI tool to assess.")
        else:
            st.session_state.pending_assessment_payload = {
                "ai_tool": user_input,
                "session_id": st.session_state.session_id,
                "request_id": str(uuid.uuid4()),
                "user_email": st.user.email,
            }
            st.session_state.assessment_in_progress = True
            st.rerun()

    pending_payload = st.session_state.pending_assessment_payload
    if is_processing and pending_payload:
        with st.spinner("Agent is browsing the web for compliance docs... This may take a few minutes...."):
            try:
                response = run_assessment(pending_payload)
            except RuntimeError as exc:
                st.session_state.assessment_error_message = str(exc)
                st.session_state.pending_assessment_payload = None
                st.session_state.assessment_in_progress = False
                st.rerun()

            st.session_state.pending_assessment_payload = None
            st.session_state.assessment_in_progress = False

            if response.ok:
                res_json = response.json()
                st.session_state.tool_report_resp = res_json.get("summary")
                if not is_active_session:
                    st.session_state.ai_tool_name = pending_payload["ai_tool"]

                st.session_state.billing_state = fetch_billing_state()
                st.session_state.pdf_data = None
                st.rerun()

            detail = "Failed to assess AI tool."
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            st.session_state.assessment_error_message = detail
            st.rerun()

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

        except RuntimeError as exc:
            st.warning(str(exc))
        except Exception:
            st.error("Failed to generate PDF.")

        st.markdown(st.session_state.tool_report_resp)
