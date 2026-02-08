import io
import logging
from datetime import datetime
from typing import Optional

import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from compliance_agent import session_service
from compliance_agent.config import APP_NAME, USER_ID

logger = logging.getLogger(__name__)


class PDFService:
    """Service for generating PDF compliance reports."""

    @classmethod
    def _convert_markdown_to_paragraphs(cls, markdown_text: str, styles) -> list:
        """
        Convert markdown text to ReportLab Paragraph elements.

        Args:
            markdown_text: Markdown formatted text to convert.
            styles: ReportLab style sheet.

        Returns:
            List of Paragraph elements.
        """
        try:
            html = markdown.markdown(markdown_text, extensions=["fenced_code"])
            paragraphs = []
            for line in html.split("\n"):
                if line.strip():
                    paragraphs.append(Paragraph(line, styles["Normal"]))
            return paragraphs
        except Exception as e:
            logger.error(f"Error converting markdown to paragraphs: {e}")
            return [Paragraph(markdown_text, styles["Normal"])]

    @classmethod
    def generate_pdf(cls, report_content: str, ai_tool_name: str) -> bytes:
        """
        Generate a PDF document from the compliance report.

        Args:
            report_content: Markdown formatted compliance report.
            ai_tool_name: Name of the AI tool being assessed.

        Returns:
            PDF content as bytes.

        Raises:
            ValueError: If report_content is empty or None.
            RuntimeError: If PDF generation fails.
        """
        if not report_content:
            raise ValueError("Report content cannot be empty")

        try:
            pdf_buffer = io.BytesIO()

            doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
            styles = getSampleStyleSheet()

            story = [
                Paragraph("EU AI Act Compliance Assessment", styles["Title"]),
                Paragraph(f"Tool: {ai_tool_name}", styles["Heading2"]),
                Paragraph(
                    f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles["Normal"]
                ),
                Spacer(1, 12),
            ]

            story.extend(cls._convert_markdown_to_paragraphs(report_content, styles))

            doc.build(story)

            return pdf_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error generating PDF for tool '{ai_tool_name}': {e}")
            raise RuntimeError(f"Failed to generate PDF: {e}") from e


async def get_report_for_session(session_id: str) -> Optional[dict]:
    """
    Retrieve the compliance report for a given session.

    Args:
        session_id: Unique session identifier.

    Returns:
        Dictionary containing 'summary' and 'ai_tool' keys, or None if not found.
    """
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )
        if not session:
            logger.warning(f"No session found for session_id: {session_id}")
            return None

        ai_tool_name = _extract_ai_tool_name(session)
        summary = _extract_summary(session)

        return {"summary": summary, "ai_tool": ai_tool_name}
    except Exception as e:
        logger.error(f"Error retrieving session {session_id}: {e}")
        return None


def _extract_ai_tool_name(session) -> str:
    """
    Extract the AI tool name from session data.

    Args:
        session: Session object from the database.

    Returns:
        AI tool name or 'Unknown AI Tool' if not found.
    """
    if hasattr(session, "state") and session.state:
        if "ai_tool" in session.state:
            return session.state["ai_tool"]

    if hasattr(session, "events") and session.events:
        for event in session.events:
            if hasattr(event, "content") and event.content:
                parts = getattr(event.content, "parts", [])
                for part in parts:
                    text = getattr(part, "text", "")
                    if text and "Assess AI tool -" in text:
                        return text.replace("Assess AI tool -", "").strip()

    return "Unknown AI Tool"


def _extract_summary(session) -> str:
    """
    Extract the summary report from session data.

    Args:
        session: Session object from the database.

    Returns:
        Summary text or empty string if not found.
    """
    if hasattr(session, "state") and session.state:
        if "summary" in session.state:
            return session.state["summary"]

    if hasattr(session, "events") and session.events:
        for event in reversed(session.events):
            if hasattr(event, "content") and event.content:
                parts = getattr(event.content, "parts", [])
                for part in parts:
                    text = getattr(part, "text", "")
                    if text and "## AI Tool Assessment Report" in text:
                        return text

    return ""
