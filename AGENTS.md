# AGENTS.md

This file contains guidelines and commands for agentic coding agents working in this EU AI Act compliance agent repository.

## Project Overview

This is a Python-based AI compliance assessment tool that evaluates AI tools against EU AI Act regulations. The system uses web research to generate structured compliance reports.

## Build/Development Commands

### Environment Setup
```bash
# Create virtual environment (if needed)
make venv

# Install dependencies
uv sync

# Activate virtual environment
make activate  # Shows command to run manually
```

### Running the Application
```bash
# Start FastAPI backend (development mode)
make run-api

# Start Streamlit frontend
make run-ui

# Start ADK web server (alternative backend)
make web

# Default command (starts web server)
make

# Show all available commands
make help
```

### Testing
```bash
# Run all tests (when tests exist)
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with coverage
pytest --cov=. tests/

# Run with verbose output
pytest -v
```

### Linting and Formatting
```bash
# Format code (if using black)
black .

# Lint code (if using flake8)
flake8 .

# Type checking (if using mypy)
mypy .

# Import sorting (if using isort)
isort .
```

## Code Style Guidelines

### Import Organization
- Standard library imports first
- Third-party imports second
- Local application imports last
- Use absolute imports for clarity
- Group related imports together

```python
# Standard library
import json
import os
import uuid

# Third-party
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

# Local imports
from common.app_server import create_app
from agent import execute
```

### Naming Conventions
- **Variables/Functions**: `snake_case` - descriptive, concise names
- **Classes**: `PascalCase` - clear, domain-specific names
- **Constants**: `UPPER_SNAKE_CASE` - module-level constants
- **Private members**: prefixed with underscore (`_private_method`)

### Type Hints
- Use type hints for all function signatures and complex variables
- Prefer `str`, `int`, `bool` over `String`, `Integer` imports
- Use `Optional[T]` for nullable types
- Async functions should be properly typed with `async def`

```python
from typing import Optional, Dict, Any, List
import uuid

def deep_compliance_search(query: str) -> str:
    """Conducts a targeted web search for AI tool metadata."""
    pass

async def execute(request: AssessRequest) -> Optional[Dict[str, Any]]:
    """Executes the compliance assessment."""
    pass
```

### Error Handling
- Use specific exception types, avoid bare `except:`
- Log errors with context information
- Include meaningful error messages
- Use try/except blocks for external API calls and file operations

```python
try:
    result = search_wrapper.results(query)
    if not result:
        logger.warning(f"No results found for query: {query}")
        return "No results found"
except Exception as e:
    logger.error(f"Search failed for query '{query}': {str(e)}")
    return json.dumps({"error": f"Search failed: {str(e)}"})
```

### Documentation
- Use docstrings for all public functions and classes
- Follow Google-style or NumPy-style docstring format
- Include parameter types, return types, and brief descriptions
- Complex logic should have inline comments

```python
def deep_compliance_search(query: str) -> str:
    """
    Conducts a targeted web search for AI tool metadata.
    
    Args:
        query: The specific compliance-related search term.
        
    Returns:
        Structured JSON string with search results including titles,
        snippets, and source URLs.
        
    Raises:
        ValueError: If the query is empty or invalid.
    """
```

### Function Structure
- Keep functions focused on a single responsibility
- Limit function length (< 50 lines when possible)
- Use early returns for validation
- Extract complex logic into helper functions

### Async/Await Patterns
- Mark all async functions with `async` keyword
- Use `await` for async operations
- Handle async exceptions properly
- Use `async for` for async iteration

```python
async def execute(request):
    try:
        async for event in runner.run_async(user_id=USER_ID, session_id=session_id):
            if event.is_final_response():
                return {"summary": event.content.parts[0].text}
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return None
```

## Project Structure

```
/
├── main.py              # FastAPI application entry point
├── agent.py             # Core AI compliance agent logic
├── ui.py                # Streamlit frontend interface
├── common/
│   └── app_server.py    # FastAPI app factory
├── pyproject.toml       # Project configuration
└── AGENTS.md           # This file
```

## Key Technologies

- **Backend**: FastAPI with Uvicorn
- **Frontend**: Streamlit
- **Database**: PostgreSQL via SQLAlchemy + asyncpg
- **AI/LLM**: Google ADK, LangChain, LiteLLM
- **Validation**: Pydantic models
- **Search**: SerpAPI for web research

## Environment Variables

Required environment variables (set in `.env` file):
- `DATABASE_URL`: PostgreSQL connection string
- `SERPAPI_API_KEY`: Search API key for web research

## Development Notes

- The agent uses web search APIs to gather compliance information
- Session management uses database-backed sessions for conversation continuity
- All compliance assessments are structured for PDF conversion
- The system follows EU AI Act risk classification framework
- Error handling should be robust for external API dependencies

## Testing Strategy

When implementing tests:
- Mock external API calls (SerpAPI, Google ADK)
- Test async functions properly with pytest-asyncio
- Verify Pydantic model validation
- Test error scenarios and edge cases
- Validate compliance report structure