"""Authentication helpers for billing-protected API routes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated end-user identity extracted from ID token."""

    subject: str
    email: str


_google_request = google_requests.Request()


def _expected_audience() -> str:
    audience = os.getenv("GOOGLE_OIDC_AUDIENCE")
    if not audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_OIDC_AUDIENCE not configured",
        )
    return audience


def _expected_issuer() -> str:
    return os.getenv("GOOGLE_OIDC_ISSUER", "https://accounts.google.com")


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    return parts[1].strip()


def _verify_token(token: str) -> dict:
    try:
        decoded = id_token.verify_oauth2_token(token, _google_request, audience=_expected_audience())
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired identity token") from exc

    issuer = decoded.get("iss")
    if issuer not in {_expected_issuer(), "accounts.google.com"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token issuer")

    email = decoded.get("email")
    subject = decoded.get("sub")
    if not email or not subject:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Identity token missing required claims")

    return decoded


async def get_authenticated_user(authorization: Optional[str] = Header(default=None)) -> AuthenticatedUser:
    """Resolve an authenticated user from a Google ID bearer token."""
    token = _extract_bearer_token(authorization)
    decoded = _verify_token(token)
    return AuthenticatedUser(subject=decoded["sub"], email=decoded["email"])
