from compliance_agent import execute
from compliance_agent.api import create_app
from compliance_agent.logging_config import setup_logging

app = create_app(agent=type("Agent", (), {"execute": execute}))
setup_logging()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
