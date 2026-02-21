#### Automated EU AI Act Compliance Agent

This project implements autonomous AI agent dedicated to the in-depth research, information gathering, and regulatory
analysis of external AI tools. The agent conducts a structured evaluation of each tool’s capabilities, data handling
practices, and operational procedures against the requirements of the EU AI Act.
The outcome of this process is an Actionable Compliance Report that clearly determines whether the assessed AI tool is
compliant with EU AI Act obligations and therefore suitable for integration into the daily work environment.

#### Running on localhost
```bash
cp .env.example .env # Add your API keys to .env
```

```bash
mkdir .streamlit
touch .streamlit/credentials.toml
```

```toml
# Add your Streamlit credentials for being able to have authenticated access to the UI
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "<random string>" # python -c "import secrets; print(secrets.token_hex(32))"
client_id = "<client id from Google console>"
client_secret = "<client secret from Google console>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
expose_tokens = ["id"] # Required so UI can send ID token to the API
```

Prerequisites:
- python >= 3.9

#### TODO: Check if ADK UI is still working :)
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

### Swagger UI
http://localhost:8000/docs