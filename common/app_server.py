from fastapi import FastAPI
from pydantic import BaseModel


class AssessRequest(BaseModel):
    ai_tool: str
    session_id: str


def create_app(agent):
    app = FastAPI()

    @app.post("/run")
    async def run(payload: AssessRequest):
        return await agent.execute(payload)

    return app
