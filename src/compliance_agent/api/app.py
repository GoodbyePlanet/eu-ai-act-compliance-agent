import io
import logging
import os
from datetime import datetime, timezone

import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from compliance_agent import session_service
from compliance_agent.api.models import AssessRequest
from compliance_agent.config import APP_NAME
from compliance_agent.services import get_report_for_session, PDFService

logger = logging.getLogger(__name__)


def create_app(agent):
    """
    Create and configure the FastAPI application.

    Args:
        agent: An object with an `execute` method that handles assessment requests.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="EU AI Act Compliance Agent",
        description="API for assessing AI tools against EU AI Act regulations",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def read_landing_page():
        """
        Landing page.

        Returns:
            Landing page HTML content.
        """
        path = os.path.join(os.getcwd(), "landing_page.html")
        with open(path, "r") as f:
            return f.read()

    @app.post("/run")
    async def run(payload: AssessRequest):
        """
        Run a compliance assessment for the specified AI tool.

        Args:
            payload: Assessment request containing AI tool name and optional session ID.

        Returns:
            Assessment results including compliance summary and session ID.
        """
        return await agent.execute(payload)


    @app.get("/sessions/recent")
    async def get_recent_session(user_email: str):
        """
        Fetches the most recent session for a user if it was created/updated within the last 5 minutes.

        Args:
            user_email: User email address.

        Returns:
            Recent session data if found, otherwise None.
        """
        logger.info(f"Fetching recent session for user with email: {user_email}")
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required")

        try:
            # list_sessions returns a ListSessionsResponse containing a list of Session objects
            response = await session_service.list_sessions(app_name=APP_NAME, user_id=user_email)
            sessions = response.sessions
        except Exception as e:
            logger.error(f"Error fetching sessions for {user_email}: {e}")
            return None

        if not sessions:
            return None

        # Get the most recently updated session. ADK uses Unix timestamps for last_update_time
        latest_session_meta = max(sessions, key=lambda s: s.last_update_time)

        # Check if it was updated within the last 5 minutes (300 seconds)
        if time.time() - latest_session_meta.last_update_time <= 300:
            full_session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=user_email,
                session_id=latest_session_meta.id
            )

            if full_session and full_session.state:
                return {
                    "session_id": full_session.id,
                    "ai_tool": full_session.state.get("ai_tool"),
                    "summary": full_session.state.get("summary")
                }

        return None

    @app.get("/sessions")
    async def get_user_sessions(user_email: str):
        """
        Fetches all historical sessions for the sidebar, ordered by update date (descending).

        Args:
            user_email: User email address.

        Returns:
            User sessions data if found, otherwise empty list.
        """
        logger.info(f"Fetching sessions for user with email: {user_email}")
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required")

        try:
            response = await session_service.list_sessions(app_name=APP_NAME, user_id=user_email)
            user_sessions = response.sessions
        except Exception as e:
            logger.error(f"Error fetching sessions for {user_email}: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch sessions")

        # Sort descending by the last update time
        sorted_sessions = sorted(user_sessions, key=lambda s: s.last_update_time, reverse=True)

        formatted_sessions = []
        for session in sorted_sessions:
            raw_date = datetime.fromtimestamp(session.last_update_time, tz=timezone.utc)
            date_str = raw_date.strftime("%b %d, %I:%M %p")

            state = getattr(session, "state", {})
            ai_tool = state.get("ai_tool", "Unknown Tool")

            formatted_sessions.append({
                "session_id": session.id,
                "ai_tool": ai_tool,
                "created_at": date_str
            })

        return {"sessions": formatted_sessions}

    @app.get("/sessions/{session_id}")
    async def get_session_by_id(session_id: str, user_email: str):
        """
        Loads a specific session from history.

        Args:
            session_id: Unique session identifier.
            user_email: User email address.

        Returns:
            User session by session ID if found, otherwise HTTP 404.
        """
        logger.info(f"Fetching session {session_id} for user with email: {user_email}")
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required")

        try:
            session_data = await session_service.get_session(
                app_name=APP_NAME,
                user_id=user_email,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {e}")
            raise HTTPException(status_code=500, detail="Error retrieving session")

        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")

        state = session_data.state or {}

        return {
            "session_id": session_data.id,
            "ai_tool": state.get("ai_tool"),
            "summary": state.get("summary")
        }


    @app.get("/pdf")
    async def get_pdf(session_id: str, user_email: str = None):
        """
        Generate PDF for a given session ID

        Args:
            session_id: Unique session identifier
            user_email: Optional user email address

        Returns:
            StreamingResponse with PDF content
        """
        logger.info(f"Generating PDF for session {session_id}")
        report = await get_report_for_session(session_id, user_email)

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

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
