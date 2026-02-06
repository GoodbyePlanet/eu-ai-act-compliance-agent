from compliance_agent.api import create_app
from compliance_agent import execute

app = create_app(agent=type("Agent", (), {"execute": execute}))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
