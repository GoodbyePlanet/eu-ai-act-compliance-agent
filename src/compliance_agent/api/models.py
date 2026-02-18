from typing import List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel


class AssessRequest(BaseModel):
    """Request model for AI tool compliance assessment."""

    ai_tool: str
    session_id: Optional[str] = None
    user_email: Optional[str] = None


class AssessResponse(BaseModel):
    """Response model for AI tool compliance assessment."""

    summary: str
    session_id: str


class SessionInfo(BaseModel):
    """Model for session information returned by recent session endpoint."""

    session_id: str
    ai_tool: Optional[str] = None
    summary: Optional[str] = None


class SessionListItem(BaseModel):
    """Model for individual session in the sessions list."""

    session_id: str
    ai_tool: str
    created_at: str


class SessionListResponse(BaseModel):
    """Response model for listing user sessions."""

    sessions: List[SessionListItem]


class ComponentHealth(BaseModel):
    """Health status for an individual component."""

    status: str
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str
    database: Optional[ComponentHealth] = None


@runtime_checkable
class AgentProtocol(Protocol):
    """Protocol defining the interface for compliance assessment agents."""

    async def execute(self, request: AssessRequest) -> Optional[AssessResponse]:
        """
        Execute a compliance assessment for the given request.

        Args:
            request: Assessment request containing AI tool name and optional session ID.

        Returns:
            Assessment response with summary and session ID, or None if execution fails.
        """
        ...
