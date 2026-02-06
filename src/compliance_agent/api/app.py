from fastapi import FastAPI

from compliance_agent.api.models import AssessRequest


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

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
