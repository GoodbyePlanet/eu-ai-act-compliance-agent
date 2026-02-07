import io
from datetime import datetime

import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from compliance_agent import session_service
from compliance_agent.config import APP_NAME, USER_ID


class PDFService:
    @classmethod
    def _convert_markdown_to_paragraphs(cls, markdown_text: str, styles):
        html = markdown.markdown(markdown_text, extensions=['fenced_code'])
        from reportlab.platypus import Paragraph

        paragraphs = []
        # Simple parsing - you'd want more robust HTML parsing in production
        for line in html.split('\n'):
            paragraphs.append(Paragraph(line, styles['Normal']))

        return paragraphs

    @classmethod
    def generate_pdf(cls, report_content: str, ai_tool_name: str) -> bytes:
        pdf_buffer = io.BytesIO()

        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        story = [
            Paragraph("EU AI Act Compliance Assessment", styles['Title']),
            Paragraph(f"Tool: {ai_tool_name}", styles['Subtitle']),
            Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']),
            Spacer(1, 12)
        ]

        story.extend(cls._convert_markdown_to_paragraphs(report_content, styles))

        doc.build(story)

        return pdf_buffer.getvalue()


async def get_report_for_session(session_id: str) -> dict:
    try:
        session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)
        if not session:
            return None

        return {
            'summary': session.get('summary', ''),
            'ai_tool': session.get('ai_tool', 'Unknown AI Tool')
        }
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return None
