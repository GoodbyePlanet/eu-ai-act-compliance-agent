import io
import logging
import re
from datetime import datetime
from typing import Optional, List

import markdown
from reportlab.lib.colors import blue, black
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle, StyleSheet1
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from compliance_agent import session_service
from compliance_agent.config import APP_NAME

logger = logging.getLogger(__name__)


class PDFService:
    """Service for generating PDF compliance reports."""

    @classmethod
    def _create_custom_styles(cls, base_styles):
        """
        Create custom styles for better PDF formatting.

        Args:
            base_styles: Default ReportLab style sheet.

        Returns:
            StyleSheet1 with enhanced styles.
        """
        styles = StyleSheet1()
        for name, style in base_styles.byName.items():
            styles.add(style)

        # Enhanced heading styles with more spacing
        styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=base_styles["Title"],
                spaceAfter=18,
                spaceBefore=12,
                fontSize=16,
                textColor=black,
            )
        )

        styles.add(
            ParagraphStyle(
                name="CustomHeading1",
                parent=base_styles["Heading1"],
                spaceAfter=12,
                spaceBefore=18,
                fontSize=14,
                textColor=black,
            )
        )

        styles.add(
            ParagraphStyle(
                name="CustomHeading2",
                parent=base_styles["Heading2"],
                spaceAfter=10,
                spaceBefore=14,
                fontSize=12,
                textColor=black,
            )
        )

        styles.add(
            ParagraphStyle(
                name="CustomNormal",
                parent=base_styles["Normal"],
                fontSize=10,
                leading=12,
            )
        )

        styles.add(
            ParagraphStyle(
                name="Link", parent=base_styles["Normal"], textColor=blue, fontSize=10
            )
        )

        return styles

    @classmethod
    def _convert_markdown_to_paragraphs(cls, markdown_text: str, styles) -> List:
        """
        Convert Markdown text to ReportLab Paragraph elements for enhanced formatting.
        """
        try:

            def replace_links(match):
                text = match.group(1)  # Group 1 is the visible text
                url = match.group(2)  # Group 2 is the actual URL
                return f'<a href="{url}" color="blue">{text}</a>'

            markdown_text = re.sub(
                r"\[([^\]]+)\]\(([^\)]+)\)", replace_links, markdown_text
            )

            md = markdown.Markdown(
                extensions=[
                    "fenced_code",
                    "extra",
                    "nl2br",
                    "sane_lists",
                    "smarty",
                ]
            )
            html = md.convert(markdown_text)
            paragraphs = []
            lines = html.split("\n")

            for line in lines:
                line = line.strip()

                if line.startswith("<h1"):
                    line = line.replace("<h1>", "").replace("</h1>", "")
                    paragraphs.append(Paragraph(line, styles["CustomHeading1"]))
                    paragraphs.append(Spacer(1, 6))

                elif line.startswith("<h2"):
                    line = line.replace("<h2>", "").replace("</h2>", "")
                    paragraphs.append(Paragraph(line, styles["CustomHeading2"]))
                    paragraphs.append(Spacer(1, 6))

                elif line:
                    if line.startswith(("<ul", "<ol", "<pre", "<code")):
                        paragraphs.append(Paragraph(line, styles["CustomNormal"]))
                    else:
                        paragraphs.append(Paragraph(line, styles["CustomNormal"]))

                paragraphs.append(Spacer(1, 3))

            return paragraphs
        except Exception as e:
            logger.error(f"Error converting markdown to paragraphs: {e}")
            return [Paragraph(markdown_text, styles["CustomNormal"])]

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

        logger.info(f"Generating PDF for tool '{ai_tool_name}'")
        try:
            pdf_buffer = io.BytesIO()

            doc = SimpleDocTemplate(
                pdf_buffer,
                pagesize=letter,
                rightMargin=inch,
                leftMargin=inch,
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
            )

            base_styles = getSampleStyleSheet()
            styles = cls._create_custom_styles(base_styles)

            story = [
                Paragraph("EU AI Act Compliance Assessment", styles["CustomTitle"]),
                Spacer(1, 12),
                Paragraph(f"Tool: {ai_tool_name}", styles["CustomHeading2"]),
                Paragraph(
                    f"Date: {datetime.now().strftime('%Y-%m-%d')}",
                    styles["CustomNormal"],
                ),
                Spacer(1, 18),
            ]

            story.extend(cls._convert_markdown_to_paragraphs(report_content, styles))

            doc.build(story)

            return pdf_buffer.getvalue()
        except Exception as e:
            logger.error(f"Error generating PDF for tool '{ai_tool_name}': {e}")
            raise RuntimeError(f"Failed to generate PDF: {e}") from e


async def get_report_for_session(
    session_id: str, user_email: Optional[str] = None
) -> Optional[dict]:
    """
    Retrieve the compliance report for a given session.

    Args:
        session_id: Unique session identifier.
        user_email: Optional user email address.

    Returns:
        Dictionary containing 'summary' and 'ai_tool' keys, or None if not found.
    """
    logger.info(f"Retrieving report for session {session_id}")
    try:
        session = await session_service.get_session(
            app_name=APP_NAME, user_id=user_email, session_id=session_id
        )
        if not session:
            logger.warning(f"No session found for session_id: {session_id}")
            return None

        ai_tool_name = _extract_ai_tool_name(session)
        summary = _extract_summary(session)

        logger.info(f"Report retrieved for session {session_id}")
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
