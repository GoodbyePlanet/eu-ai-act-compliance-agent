#### Automated EU AI Act Compliance Agent

This project implements autonomous AI agent dedicated to the in-depth research, information gathering, and regulatory
analysis of external AI tools. The agent conducts a structured evaluation of each tool’s capabilities, data handling
practices, and operational procedures against the requirements of the EU AI Act.
The outcome of this process is an Actionable Compliance Report that clearly determines whether the assessed AI tool is
compliant with EU AI Act obligations and therefore suitable for integration into the daily work environment.

#### Running on localhost
```bash
cp .env.example .env
```

Prerequisites:
- python >= 3.9

```bash
# To start ADK UI
make venv
make web
```

```bash
# To Start Agent with FastAPI and Streamlit UI
make run-api
make run-ui
```