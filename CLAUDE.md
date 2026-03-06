# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An autonomous AI compliance agent that researches external AI tools and generates structured EU AI Act compliance reports. The system uses Google ADK with LiteLLM (Anthropic Claude) to run the agent, FastAPI for the backend API, and Streamlit for the frontend UI.

## Development Commands

```bash
# Setup
make install           # Install package in dev mode (uses uv sync)
make reinstall         # Force reinstall all dependencies

# Running locally (requires make run-db-local first for the API)
make run-db-local      # Start Postgres on localhost:5432 via Docker
make run-api           # Start FastAPI on http://localhost:8000 (uvicorn --reload)
make run-ui            # Start Streamlit on http://localhost:8501 (auto-switches to local OAuth profile)
make stop-db-local     # Stop local Postgres

# Testing
make test-all                                           # Run all tests
uv run pytest tests/unit/ -v                           # Run all tests directly
uv run pytest tests/unit/guardrails/test_callbacks.py -v   # Run a single test file
uv run pytest tests/unit/guardrails/test_callbacks.py::TestValidateInputGuardrail::test_valid_input_returns_none -v  # Run a single test
uv run pytest -k "test_valid" -v                       # Run tests matching a pattern
```

## Architecture

### Request Flow

1. **Streamlit UI** (`ui.py` / `src/frontend/`) — User enters an AI tool name. On load, `fetch_ui_bootstrap()` fetches sessions + billing state in one API call.
2. **FastAPI API** (`main.py` / `src/compliance_agent/api/app.py`) — `POST /run` authenticates via Google OIDC, optionally enforces billing quota, then calls `agent.execute()`.
3. **Agent** (`src/compliance_agent/agent.py`) — Google ADK `Runner` drives the `root_agent`. It iteratively calls `deep_compliance_search` (capped at `MAX_SEARCHES=20`), then returns a Markdown compliance report.
4. **Session persistence** — `DatabaseSessionService` (Google ADK) stores conversation state in Postgres. Session state carries `ai_tool` and `summary` fields used across follow-up requests (human-in-the-loop).
5. **PDF generation** — `GET /pdf?session_id=...` retrieves the session summary and converts it via `PDFService` (ReportLab + Markdown).

### Key Modules

- `src/compliance_agent/agent.py` — Constructs the `root_agent`, `runner`, `session_service`, and `billing_service` as module-level singletons; defines `execute()` for running assessments.
- `src/compliance_agent/api/app.py` — `create_app(agent)` factory that wires all FastAPI routes. The `AgentProtocol` type allows injecting a test double.
- `src/compliance_agent/config.py` — All prompt strings (`AGENT_INSTRUCTION`, `AGENT_DESCRIPTION`), `APP_NAME`, `MAX_SEARCHES`, and `DISCLAIMER_TEXT`.
- `src/compliance_agent/guardrails/callbacks.py` — Three ADK callbacks: `validate_input_guardrail` (before agent), `output_validation_guardrail` (after agent), `tool_input_guardrail` (before tool). Blocks prompt injection and off-topic searches.
- `src/compliance_agent/tools/search.py` — Wraps the search provider into an ADK-compatible `compliance_search_tool`.
- `src/compliance_agent/tools/search_providers/` — `factory.py` auto-selects Serper (preferred) or SerpAPI based on available env keys.
- `src/compliance_agent/billing/` — Daily credit quota enforcement via a `CreditLedgerEntry` append-only table. Controlled by `BILLING_ENABLED` env var.
- `src/frontend/` — Streamlit components: `auth.py` (Google OAuth via `require_login()`), `api_client.py` (HTTP calls to the FastAPI backend), `sidebar.py`, `main_content.py`.

### Authentication

- **Backend**: Google OIDC JWT validation (`GOOGLE_OIDC_AUDIENCE`, `GOOGLE_OIDC_ISSUER`). `get_authenticated_user` dependency used on all protected routes.
- **Frontend**: Streamlit native OAuth via `.streamlit/secrets.toml`. Two profiles exist (`secrets.local.toml`, `secrets.traefik.toml`); `scripts/use_streamlit_auth_profile.sh` switches between them.

### Deployment

- **Local (no Docker)**: `make run-db-local` + `make run-api` + `make run-ui`
- **Full Docker (Traefik)**: `docker compose up --build` — serves landing page at `http://localhost`, UI at `http://localhost/app`, API at `http://localhost/api`
- **Production**: Uses `docker-compose.prod.yml` overlay with `.env.prod`

## Environment Variables

Required in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `AI_MODEL` | LiteLLM model string (e.g. `anthropic/claude-sonnet-4-6`) |
| `ANTHROPIC_API_KEY` | Claude LLM access |
| `DATABASE_URL` | `postgresql+asyncpg://...` connection string |
| `SERPER_API_KEY` or `SERPAPI_API_KEY` | Web search (Serper takes priority) |
| `GOOGLE_OIDC_AUDIENCE` | Google OAuth client ID for JWT validation |
| `BILLING_ENABLED` | `true`/`false` — enables daily quota enforcement |
| `DAILY_FREE_CREDITS` | Daily request limit per user (default: `20`) |

## Code Style

- **Imports**: stdlib → third-party → local, with blank lines between groups.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants, `_underscore` prefix for private members.
- **Type hints**: Required on all function signatures.
- **Docstrings**: Google-style for all public functions/classes.
- **Package exports**: Define `__all__` in every `__init__.py`.
- **Tests**: pytest with Arrange-Act-Assert pattern; fixtures in `conftest.py`; mock external APIs (SerpAPI, Google ADK).
- **`pythonpath`** for pytest is set to `src/` in `pyproject.toml`, so imports use `from compliance_agent...` and `from frontend...`.
