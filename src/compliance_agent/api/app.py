import io
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import StreamingResponse

from compliance_agent.api.models import AssessRequest
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
    async def read_landing():
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

    @app.get("/pdf")
    async def get_pdf(session_id: str):
        """
        Generate PDF for a given session ID

        Args:
            session_id: Unique session identifier

        Returns:
            StreamingResponse with PDF content
        """
        logger.info(f"Generating PDF for session {session_id}")
        report = await get_report_for_session(session_id)

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
