import streamlit as st

_EMBEDDED_BROWSER_SIGNALS = (
    "LinkedInApp",
    "FBAN",       # Facebook app
    "FBAV",       # Facebook app
    "Instagram",
    "Twitter",
    "Line/",
    "MicroMessenger",  # WeChat
)


def _is_embedded_browser() -> bool:
    """Return True if the request comes from a known embedded/in-app WebView."""
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        return False
    return any(signal in ua for signal in _EMBEDDED_BROWSER_SIGNALS)


def require_login():
    """Handles Google Workspace authentication."""
    if _is_embedded_browser():
        st.markdown(
            "<h1 style='text-align: center; margin-top: 50px;'>EU AI Act Compliance Agent</h1>",
            unsafe_allow_html=True,
        )
        st.info(
            "Google sign-in is not supported inside in-app browsers (e.g. LinkedIn, Facebook).\n\n"
            "Please open this link in your device's default browser (Chrome, Safari, Firefox, etc.) "
            "and try again.",
            icon="ℹ️",
        )
        st.stop()

    if not st.user.is_logged_in:
        if st.query_params.get("auto_login") == "true":
            st.login()
        else:
            st.markdown(
                "<h1 style='text-align: center; margin-top: 50px; max-width: 800px;'>EU AI Act Compliance Agent</h1>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='text-align: center; max-width: 800px;'>To start AI tool assessment,"
                " please authenticate with your Google Workspace account.</p>",
                unsafe_allow_html=True,
            )
            left_co, cent_co, last_co = st.columns([1, 1, 1])
            with cent_co:
                if st.button("Log in with Google", use_container_width=True):
                    st.login()

        # Stop execution so the rest of the app doesn't load for unauthenticated users
        st.stop()


def get_auth_headers() -> dict:
    """Return bearer auth headers from Streamlit OIDC tokens."""
    token = ""
    if st.user.is_logged_in and hasattr(st.user, "tokens"):
        token = st.user.tokens.get("id", "")

    if not token:
        return {}

    return {"Authorization": f"Bearer {token}"}
