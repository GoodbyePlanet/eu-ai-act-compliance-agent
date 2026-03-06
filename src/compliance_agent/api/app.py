import asyncio
import io
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import StreamingResponse

from compliance_agent.agent import session_service
from compliance_agent.api.models import (
    AgentProtocol,
    AssessRequest,
    AssessResponse,
    BillingStateResponse,
    ComponentHealth,
    HealthResponse,
    SessionDeleteResponse,
    SessionInfo,
    SessionListItem,
    SessionListResponse,
    UIBootstrapResponse,
)
from compliance_agent.billing import (
    AuthenticatedUser,
    BillingService,
    InsufficientCreditsError,
    get_authenticated_user,
)
from compliance_agent.billing.db import init_billing_schema
from compliance_agent.config import APP_NAME
from compliance_agent.services import PDFService, get_report_for_session

logger = logging.getLogger(__name__)


def _read_static_html(filename: str) -> str:
    """Read an HTML file from the current working directory."""
    path = os.path.join(os.getcwd(), filename)
    with open(path, "r") as f:
        return f.read()


def _format_session_list(user_sessions: List) -> List[SessionListItem]:
    """Convert internal session metadata to API session list response shape."""
    sorted_sessions = sorted(
        user_sessions, key=lambda s: s.last_update_time, reverse=True
    )

    formatted_sessions: List[SessionListItem] = []
    for session in sorted_sessions:
        raw_date = datetime.fromtimestamp(session.last_update_time, tz=timezone.utc)
        date_str = raw_date.isoformat()
        state = getattr(session, "state", {}) or {}
        ai_tool = state.get("ai_tool", "Unknown Tool")

        formatted_sessions.append(
            SessionListItem(
                session_id=session.id, ai_tool=ai_tool, created_at=date_str
            )
        )
    return formatted_sessions


def _build_recent_session_if_active(sessions: List) -> Optional[str]:
    """Return session id of most recent active session in the last five minutes."""
    if not sessions:
        return None

    latest_session_meta = max(sessions, key=lambda s: s.last_update_time)
    if time.time() - latest_session_meta.last_update_time <= 300:
        return latest_session_meta.id
    return None


def create_app(agent: AgentProtocol) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="EU AI Act Compliance Agent",
        description="API for assessing AI tools against EU AI Act regulations",
        version="1.0.0",
    )
    app.mount("/static", StaticFiles(directory=os.path.join(os.getcwd(), "static")), name="static")

    billing_service = BillingService()

    @app.middleware("http")
    async def log_request_latency(request: Request, call_next) -> Response:
        """Log end-to-end request timing for latency diagnostics."""
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "HTTP %s %s failed in %.2fms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "HTTP %s %s -> %s in %.2fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    @app.on_event("startup")
    async def on_startup() -> None:
        if billing_service.is_enabled():
            await init_billing_schema()

    @app.get("/", response_class=HTMLResponse)
    async def read_landing_page() -> str:
        """Landing page."""
        try:
            return _read_static_html("landing_page.html")
        except FileNotFoundError as e:
            logger.error(f"Landing page file not found: {e}")
            raise HTTPException(
                status_code=500, detail="Landing page is not available"
            ) from e

    @app.get("/about-eu-ai-act", response_class=HTMLResponse)
    async def read_about_eu_ai_act_page() -> str:
        """About EU AI Act page."""
        try:
            return _read_static_html("about_eu_ai_act.html")
        except FileNotFoundError as e:
            logger.error(f"About page file not found: {e}")
            raise HTTPException(
                status_code=500, detail="About EU AI Act page is not available"
            ) from e

    @app.get("/app", include_in_schema=False)
    async def redirect_to_frontend_app() -> RedirectResponse:
        """Redirect /app to the Streamlit UI in local non-Traefik mode."""
        app_url = os.getenv("STREAMLIT_APP_URL", "http://localhost:8501")
        return RedirectResponse(url=app_url)

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> RedirectResponse:
        """Redirect favicon requests to the static directory."""
        return RedirectResponse(url="/static/favicon.ico")

    @app.post("/run", response_model=AssessResponse)
    async def run(
            payload: AssessRequest,
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> Optional[AssessResponse]:
        """Run a compliance assessment for the specified AI tool."""
        logger.info(f"Running assessment - requesting user {auth_user.email}, tool {payload.ai_tool}")
        if billing_service.is_enabled():
            user_ref = await billing_service.ensure_user(
                google_sub=auth_user.subject,
                email=auth_user.email,
            )
            payload.user_sub = user_ref.id
            payload.user_email = auth_user.email
        else:
            payload.user_email = auth_user.email

        try:
            response = await agent.execute(payload)
        except InsufficientCreditsError as exc:
            raise HTTPException(status_code=402, detail=str(exc)) from exc

        if response is None:
            raise HTTPException(status_code=500, detail="Failed to execute assessment")

        if billing_service.is_enabled() and payload.user_sub:
            credit_state = await billing_service.get_daily_credit_state(user_id=payload.user_sub)
            response["credits_left_today"] = credit_state.credits_left_today
            response["billing_status"] = "ok"

        return response

    @app.get("/billing/me", response_model=BillingStateResponse)
    async def billing_me(
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> BillingStateResponse:
        """Return the current authenticated user's daily quota state."""
        user_ref = await billing_service.ensure_user(
            google_sub=auth_user.subject,
            email=auth_user.email,
        )
        state = await billing_service.get_daily_credit_state(user_id=user_ref.id)
        return BillingStateResponse(**state.__dict__)

    @app.get("/ui/bootstrap", response_model=UIBootstrapResponse)
    async def ui_bootstrap(
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> UIBootstrapResponse:
        """Return initial UI data in one round-trip for authenticated users."""
        resolved_email = auth_user.email

        async def _load_user_sessions() -> List:
            try:
                response = await session_service.list_sessions(
                    app_name=APP_NAME, user_id=resolved_email
                )
                return response.sessions
            except Exception as e:
                logger.error(f"Error fetching sessions for {resolved_email}: {e}")
                return []

        async def _load_billing_state() -> Optional[BillingStateResponse]:
            try:
                user_ref = await billing_service.ensure_user(
                    google_sub=auth_user.subject,
                    email=resolved_email,
                )
                state = await billing_service.get_daily_credit_state(user_id=user_ref.id)
                return BillingStateResponse(**state.__dict__)
            except Exception as e:
                logger.error(f"Error fetching billing state for {resolved_email}: {e}")
                return None

        user_sessions, billing_state = await asyncio.gather(
            _load_user_sessions(),
            _load_billing_state(),
        )

        recent_session: Optional[SessionInfo] = None
        recent_session_id = _build_recent_session_if_active(
            sessions=user_sessions,
        )
        if recent_session_id:
            session_meta = next(
                (session for session in user_sessions if session.id == recent_session_id),
                None,
            )
            session_meta_state = getattr(session_meta, "state", {}) or {}
            if session_meta_state:
                recent_session = SessionInfo(
                    session_id=recent_session_id,
                    ai_tool=session_meta_state.get("ai_tool"),
                    summary=session_meta_state.get("summary"),
                )

            try:
                if recent_session is None or recent_session.summary is None:
                    full_session = await session_service.get_session(
                        app_name=APP_NAME, user_id=resolved_email, session_id=recent_session_id
                    )
                else:
                    full_session = None
                if full_session and full_session.state:
                    recent_session = SessionInfo(
                        session_id=full_session.id,
                        ai_tool=full_session.state.get("ai_tool"),
                        summary=full_session.state.get("summary"),
                    )
            except Exception as e:
                logger.error(f"Error fetching recent full session for {resolved_email}: {e}")

        return UIBootstrapResponse(
            billing=billing_state,
            recent_session=recent_session,
            sessions=_format_session_list(user_sessions),
        )

    @app.get("/sessions/recent", response_model=Optional[SessionInfo])
    async def get_recent_session(
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> Optional[SessionInfo]:
        """Fetch the most recent session if active in the last five minutes."""
        logger.info(f"Fetching recent session for user with email: {auth_user.email}")

        resolved_email = auth_user.email

        try:
            response = await session_service.list_sessions(
                app_name=APP_NAME, user_id=resolved_email
            )
            sessions = response.sessions
        except Exception as e:
            logger.error(f"Error fetching sessions for {resolved_email}: {e}")
            return None

        recent_session_id = _build_recent_session_if_active(
            sessions=sessions,
        )
        if recent_session_id:
            full_session = await session_service.get_session(
                app_name=APP_NAME, user_id=resolved_email, session_id=recent_session_id
            )

            if full_session and full_session.state:
                return SessionInfo(
                    session_id=full_session.id,
                    ai_tool=full_session.state.get("ai_tool"),
                    summary=full_session.state.get("summary"),
                )

        return None

    @app.get("/sessions", response_model=SessionListResponse)
    async def get_user_sessions(
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> SessionListResponse:
        """Fetch all user sessions for sidebar history."""
        resolved_email = auth_user.email
        logger.info(f"Fetching sessions for user with email: {resolved_email}")

        try:
            response = await session_service.list_sessions(
                app_name=APP_NAME, user_id=resolved_email
            )
            user_sessions = response.sessions
        except Exception as e:
            logger.error(f"Error fetching sessions for {resolved_email}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch sessions")

        return SessionListResponse(sessions=_format_session_list(user_sessions))

    @app.get("/sessions/{session_id}", response_model=SessionInfo)
    async def get_session_by_id(
            session_id: str,
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> SessionInfo:
        """Load one historical session from history."""
        resolved_email = auth_user.email
        logger.info(f"Fetching session {session_id} for user with email: {resolved_email}")

        try:
            session_data = await session_service.get_session(
                app_name=APP_NAME, user_id=resolved_email, session_id=session_id
            )
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving session")

        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        state = session_data.state or {}

        return SessionInfo(
            session_id=session_data.id,
            ai_tool=state.get("ai_tool"),
            summary=state.get("summary"),
        )

    @app.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
    async def delete_session_by_id(
            session_id: str,
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> SessionDeleteResponse:
        """Delete session by session_id for the authenticated user."""
        resolved_email = auth_user.email
        logger.info(f"Deleting session {session_id} for user with email: {resolved_email}")

        try:
            session_data = await session_service.get_session(
                app_name=APP_NAME, user_id=resolved_email, session_id=session_id
            )
        except Exception as e:
            logger.error(f"Error checking session {session_id} before delete: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving session") from e

        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        try:
            await session_service.delete_session(
                app_name=APP_NAME, user_id=resolved_email, session_id=session_id
            )
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete session") from e

        return SessionDeleteResponse(
            session_id=session_id,
            deleted=True,
            message="Session deleted successfully.",
        )

    @app.get("/pdf")
    async def get_pdf(
            session_id: str,
            auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> StreamingResponse:
        """Generate PDF for a given session ID."""
        logger.info(f"Generating PDF for session {session_id}")
        report = await get_report_for_session(session_id, auth_user.email)

        if not report:
            raise HTTPException(
                status_code=404, detail="No report found for the given session"
            )

        if not report.get("summary"):
            raise HTTPException(status_code=400, detail="Report has no summary content")

        try:
            pdf_content = PDFService.generate_pdf_cached(
                report_content=report["summary"],
                ai_tool_name=report["ai_tool"],
                session_id=session_id,
            )
        except ValueError as e:
            logger.error(f"Invalid report content for session {session_id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            logger.error(f"PDF generation failed for session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate PDF")

        safe_tool_name = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_" for c in report["ai_tool"]
        ).strip()

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="ai_tool_assessment_{safe_tool_name}.pdf"'
            },
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Check service health including database connectivity."""
        db_health = ComponentHealth(status="healthy")

        try:
            await session_service.list_sessions(
                app_name=APP_NAME, user_id="health-check"
            )
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_health = ComponentHealth(status="unhealthy", message=str(e))

        overall_status = "healthy" if db_health.status == "healthy" else "unhealthy"

        return HealthResponse(status=overall_status, database=db_health)

    return app
