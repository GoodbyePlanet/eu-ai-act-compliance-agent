from common.a2a_server import create_app
from agent import execute

app = create_app(agent=type("Agent", (), {"execute": execute}))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8000, reload=True)