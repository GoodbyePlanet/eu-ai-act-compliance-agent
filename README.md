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
touch .streamlit/secrets.toml
```

```toml
# Add your Streamlit credentials for being able to have authenticated access to the UI
[auth]
# For local make run-ui, this should be:
# redirect_uri = "http://localhost:8501/oauth2callback"
# For Traefik /app mode, this should be:
# redirect_uri = "http://localhost/app/oauth2callback"
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "<random string>" # python -c "import secrets; print(secrets.token_hex(32))"
client_id = "<client id from Google console>"
client_secret = "<client secret from Google console>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
expose_tokens = ["id"] # Required so UI can send ID token to the API
```

Google Cloud Console OAuth client settings:
- Authorized JavaScript origins: `http://localhost` (origin only, no path)
- Authorized redirect URIs: `http://localhost:8501/oauth2callback`
- Authorized redirect URIs: `http://localhost/app/oauth2callback`

```bash
# Start local DB only (required for make run-api)
make run-db-local
```

```bash
# Start API and UI locally
make run-api
make run-ui
```

Local URLs (non-Traefik mode):
- App UI: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`

`make run-ui` automatically activates local OAuth profile.

To switch OAuth profile manually:
```bash
./scripts/use_streamlit_auth_profile.sh local
./scripts/use_streamlit_auth_profile.sh traefik
```

Stop local DB:
```bash
make stop-db-local
```

Common local errors:
- `Connect call failed ('127.0.0.1', 5432)`: start DB with `make run-db-local`
- `redirect_uri_mismatch`: ensure both redirect URIs above are registered in Google Cloud Console

Prerequisites:
- python >= 3.9

#### TODO: Check if ADK UI is still working :)
```bash
# To start ADK UI
make venv
make web
```

```bash
# Start all app containers behind Traefik reverse proxy
./scripts/use_streamlit_auth_profile.sh traefik
docker compose up --build
```

Traefik URLs:
- Landing page: `http://localhost`
- App UI: `http://localhost/app`
- API docs: `http://localhost/api/docs`

### Production deployment (VPS)
```bash
cp .env.prod.example .env.prod # fill with production values
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
