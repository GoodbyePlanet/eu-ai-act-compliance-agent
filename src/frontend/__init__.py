from __future__ import annotations

from typing import Any

__all__ = [
    "run_assessment",
    "delete_session_by_id_and_email",
    "fetch_billing_state",
    "generate_pdf",
    "fetch_recent_session",
    "fetch_session_history",
    "fetch_session_by_id_and_email",
    "fetch_ui_bootstrap",
    "get_auth_headers",
    "require_login",
    "render_sidebar",
    "render_main_content",
]

_MODULE_MAP: dict[str, str] = {
    "run_assessment": "frontend.api_client",
    "delete_session_by_id_and_email": "frontend.api_client",
    "fetch_billing_state": "frontend.api_client",
    "generate_pdf": "frontend.api_client",
    "fetch_recent_session": "frontend.api_client",
    "fetch_session_history": "frontend.api_client",
    "fetch_session_by_id_and_email": "frontend.api_client",
    "fetch_ui_bootstrap": "frontend.api_client",
    "get_auth_headers": "frontend.auth",
    "require_login": "frontend.auth",
    "render_sidebar": "frontend.sidebar",
    "render_main_content": "frontend.main_content",
}


def __getattr__(name: str) -> Any:
    if name in _MODULE_MAP:
        import importlib
        module = importlib.import_module(_MODULE_MAP[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
