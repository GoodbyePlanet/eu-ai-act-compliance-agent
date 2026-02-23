import io
import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from compliance_agent import session_service
from compliance_agent.api.models import (
    AgentProtocol,
    AssessRequest,
    AssessResponse,
    BillingStateResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    ComponentHealth,
    HealthResponse,
    PortalSessionResponse,
    SessionInfo,
    SessionListItem,
    SessionListResponse,
)
from compliance_agent.billing import (
    AuthenticatedUser,
    BillingService,
    InsufficientCreditsError,
    get_authenticated_user,
)
from compliance_agent.billing.db import init_billing_schema
from compliance_agent.billing.stripe_service import StripeService
from compliance_agent.config import APP_NAME
from compliance_agent.services import PDFService, get_report_for_session

logger = logging.getLogger(__name__)


def _read_static_html(filename: str) -> str:
    """Read an HTML file from the current working directory."""
    path = os.path.join(os.getcwd(), filename)
    with open(path, "r") as f:
        return f.read()


def create_app(agent: AgentProtocol) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="EU AI Act Compliance Agent",
        description="API for assessing AI tools against EU AI Act regulations",
        version="1.0.0",
    )

    billing_service = BillingService()
    stripe_service = StripeService(billing_service=billing_service)

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
            credit_state = await billing_service.get_credit_state(user_id=payload.user_sub)
            response["request_units_remaining"] = credit_state.request_units_balance
            response["billing_status"] = "ok"

        return response

    @app.get("/billing/me", response_model=BillingStateResponse)
    async def billing_me(
        auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> BillingStateResponse:
        """Return the current authenticated user's billing state."""
        user_ref = await billing_service.ensure_user(
            google_sub=auth_user.subject,
            email=auth_user.email,
        )
        state = await billing_service.get_credit_state(user_id=user_ref.id)
        return BillingStateResponse(**state.__dict__)

    @app.post("/billing/checkout-session", response_model=CheckoutSessionResponse)
    async def create_checkout_session(
        payload: CheckoutSessionRequest,
        auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> CheckoutSessionResponse:
        """Create a Stripe checkout session for a credit pack."""
        logger.info(f"Creating checkout session for user {auth_user.email}, pack {payload.pack_code}")
        user_ref = await billing_service.ensure_user(
            google_sub=auth_user.subject,
            email=auth_user.email,
        )
        checkout_session_response = await stripe_service.create_checkout_session(
            user_id=user_ref.id,
            email=user_ref.email,
            pack_code=payload.pack_code,
        )
        return CheckoutSessionResponse(**checkout_session_response)

    @app.post("/billing/portal-session", response_model=PortalSessionResponse)
    async def create_portal_session(
        auth_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> PortalSessionResponse:
        """Create a Stripe billing portal session."""
        logger.info(f"Creating portal session for user {auth_user.email}")
        user_ref = await billing_service.ensure_user(
            google_sub=auth_user.subject,
            email=auth_user.email,
        )
        result = await stripe_service.create_portal_session(user_id=user_ref.id, email=user_ref.email)
        return PortalSessionResponse(**result)

    @app.post("/billing/webhooks/stripe")
    async def stripe_webhook(
        request: Request,
        stripe_signature: Optional[str] = Header(default=None, alias="Stripe-Signature"),
    ) -> dict:
        """Handle Stripe webhook events with signature verification and idempotency."""
        logger.info("Received Stripe webhook event")
        if not stripe_signature:
            raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

        body = await request.body()
        try:
            event = stripe_service.construct_event(payload=body, stripe_signature=stripe_signature)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

        event_type = event.get("type", "")
        if event_type == "checkout.session.completed":
            processed, status_text = await stripe_service.process_checkout_completed(event=event, raw_payload=body)
            logger.info(f"Processing Stripe checkout session completed event {status_text}")

            # TODO: What do we do with this response?
            return {"status": status_text, "processed": processed}

        return {"status": "ignored", "event_type": event_type}

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

        if not sessions:
            return None

        latest_session_meta = max(sessions, key=lambda s: s.last_update_time)

        if time.time() - latest_session_meta.last_update_time <= 300:
            full_session = await session_service.get_session(
                app_name=APP_NAME, user_id=resolved_email, session_id=latest_session_meta.id
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

        sorted_sessions = sorted(
            user_sessions, key=lambda s: s.last_update_time, reverse=True
        )

        formatted_sessions: List[SessionListItem] = []
        for session in sorted_sessions:
            raw_date = datetime.fromtimestamp(session.last_update_time, tz=timezone.utc)
            date_str = raw_date.strftime("%b %d, %I:%M %p")

            state = getattr(session, "state", {}) or {}
            ai_tool = state.get("ai_tool", "Unknown Tool")

            formatted_sessions.append(
                SessionListItem(
                    session_id=session.id, ai_tool=ai_tool, created_at=date_str
                )
            )

        return SessionListResponse(sessions=formatted_sessions)

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
            pdf_content = PDFService.generate_pdf(
                report_content=report["summary"], ai_tool_name=report["ai_tool"]
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
