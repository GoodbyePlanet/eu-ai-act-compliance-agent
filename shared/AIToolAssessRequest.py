from pydantic import BaseModel

class AIToolAssessRequest(BaseModel):
    ai_tool: str