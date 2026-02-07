import io

from fastapi import FastAPI, HTTPException
from starlette.responses import StreamingResponse

from compliance_agent.api.models import AssessRequest
from compliance_agent.services import get_report_for_session, PDFService


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
        report = get_report_for_session(session_id)

        # Error handling if no report found
        if not report:
            raise HTTPException(
                status_code=404,
                detail="No report found for the given session"
            )

        pdf_content = PDFService.generate_pdf(
            report_content=report['summary'],
            ai_tool_name=report['ai_tool']
        )

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="ai_tool_assessment.pdf"'
            }
        )

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
