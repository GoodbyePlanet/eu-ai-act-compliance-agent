from typing import Optional

from pydantic import BaseModel


class AssessRequest(BaseModel):
    """Request model for AI tool compliance assessment."""

    ai_tool: str
    session_id: Optional[str] = None


class AssessResponse(BaseModel):
    """Response model for AI tool compliance assessment."""

    summary: str
    session_id: str
