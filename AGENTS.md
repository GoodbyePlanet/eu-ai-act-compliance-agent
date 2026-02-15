 n# AGENTS.md

Guidelines for agentic coding agents working in this EU AI Act compliance agent repository.

## Project Overview

Python-based AI compliance assessment tool that evaluates AI tools against EU AI Act regulations using web research to generate structured compliance reports.

## Project Structure

```
├── main.py                    # FastAPI entry point
├── ui.py                      # Streamlit frontend
├── Makefile                   # Build/run commands
├── pyproject.toml             # Project config (hatchling build, pytest, pyright)
├── src/compliance_agent/
│   ├── __init__.py            # Package exports (execute, root_agent, runner)
│   ├── agent.py               # Core AI agent logic
│   ├── config.py              # Constants (AGENT_DESCRIPTION, APP_NAME, etc.)
│   ├── api/
│   │   ├── app.py             # FastAPI app factory
│   │   └── models.py          # Pydantic request/response models
│   ├── guardrails/
│   │   └── callbacks.py       # Input/output validation callbacks
│   ├── services/
│   │   └── pdf_service.py     # PDF report generation
│   └── tools/
│       ├── search.py          # Compliance search tool
│       └── search_providers/  # SerpAPI/Serper implementations
└── tests/unit/                # Unit tests with pytest
```

## Build/Development Commands

```bash
# Environment setup
make venv              # Create virtual environment
make install           # Install package in dev mode
uv sync                # Sync dependencies

# Running the application
make run-api           # Start FastAPI backend
make run-ui            # Start Streamlit frontend
make web               # Start ADK web server (default)
make help              # Show all commands
```

## Testing Commands

```bash
# Run all tests
make test-all
pytest tests/unit/ -v

# Run a single test file
pytest tests/unit/guardrails/test_callbacks.py -v

# Run a single test class
pytest tests/unit/guardrails/test_callbacks.py::TestValidateInputGuardrail -v

# Run a single test method
pytest tests/unit/guardrails/test_callbacks.py::TestValidateInputGuardrail::test_valid_input_returns_none -v

# Run tests matching a pattern
pytest -k "test_valid" -v

# Run with coverage
pytest --cov=src tests/
```

## Code Style Guidelines

### Import Organization
Strict ordering: standard library, third-party, local imports.

```python
# Standard library
import json
import os
from typing import Optional, Dict, Any, List

# Third-party
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

# Local imports
from compliance_agent.config import AGENT_DESCRIPTION, APP_NAME
from compliance_agent.tools import compliance_search_tool
```

### Naming Conventions
- **Functions/Variables**: `snake_case` (e.g., `deep_compliance_search`, `session_service`)
- **Classes**: `PascalCase` (e.g., `SearchProvider`, `PDFService`, `AssessRequest`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `AGENT_DESCRIPTION`, `MAX_INPUT_LENGTH`)
- **Private members**: underscore prefix (e.g., `_search_provider`, `_execute_search`)

### Type Hints
Required on all function signatures. Use `typing` module types.

```python
def deep_compliance_search(query: str) -> str:
    ...

async def execute(request: AssessRequest) -> Optional[Dict[str, Any]]:
    ...

def create_search_provider(provider_type: Optional[ProviderType] = None) -> SearchProvider:
    ...
```

### Docstrings
Use Google-style docstrings for all public functions and classes.

```python
def deep_compliance_search(query: str) -> str:
    """
    Conducts a targeted web search for AI tool metadata.

    Args:
        query: The specific compliance-related search term.

    Returns:
        JSON string containing search results with titles, links,
        snippets, and source type classification.

    Raises:
        SearchProviderError: If the search API call fails.
    """
```

### Error Handling
Use specific exceptions, preserve error chains, log with context.

```python
try:
    return self._wrapper.results(query)
except Exception as e:
    raise SearchProviderError(
        self.name,
        f"Search failed for query '{query}': {str(e)}",
        original_error=e,
    )
```

### Async Patterns
Use `async for` for streaming, handle async exceptions properly.

```python
async def execute(request):
    async for event in runner.run_async(user_id=user_email, session_id=session_id):
        if event.is_final_response():
            return {"summary": event.content.parts[0].text}
```

### Package Exports
Each package defines `__all__` in `__init__.py` for explicit public API.

```python
# compliance_agent/tools/__init__.py
from compliance_agent.tools.search import compliance_search_tool

__all__ = ["compliance_search_tool", "deep_compliance_search"]
```

## Testing Patterns

Tests use pytest with Arrange-Act-Assert pattern and descriptive names.

```python
def test_valid_input_returns_none(self, mock_callback_context):
    """Valid AI tool name should pass validation and return None."""
    # Arrange
    context = mock_callback_context(user_input="ChatGPT")

    # Act
    result = validate_input_guardrail(context)

    # Assert
    assert result is None
```

Use fixtures in `conftest.py` for shared mock objects. Mock external APIs (SerpAPI, Google ADK).

## Key Technologies

- **Backend**: FastAPI + Uvicorn
- **Frontend**: Streamlit
- **AI/LLM**: Google ADK, LiteLLM (Anthropic Claude)
- **Database**: PostgreSQL (SQLAlchemy + asyncpg)
- **Search**: SerpAPI or Google Serper (auto-selected)
- **PDF**: ReportLab + Markdown

## Environment Variables

Required in `.env`:
- `ANTHROPIC_API_KEY` - Claude LLM access
- `DATABASE_URL` - PostgreSQL connection string
- `SERPAPI_API_KEY` or `SERPER_API_KEY` - Web search API (one required)

## Design Patterns

- **Factory**: `create_search_provider()` for provider auto-selection
- **Abstract Base Class**: `SearchProvider` interface
- **Dataclass**: `SearchResult` for structured data
- **Callback**: Guardrail callbacks (before_agent, after_agent, before_tool)
- **App Factory**: `create_app(agent)` in api/app.py
