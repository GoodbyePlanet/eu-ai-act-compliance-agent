import streamlit as st

def require_login():
    """Handles Google Workspace authentication."""
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

        # Stop execution so the rest of the app doesn't load for unauthenticated users
        st.stop()