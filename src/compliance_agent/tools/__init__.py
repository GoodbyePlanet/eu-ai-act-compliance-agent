"""
Tools for the EU AI Act Compliance Agent.

This package contains all tools available to the agent for conducting
compliance research and assessments.
"""

from compliance_agent.tools.search import compliance_search_tool, deep_compliance_search
from compliance_agent.tools.search_providers import (
    ProviderType,
    SearchProvider,
    SearchProviderError,
    SearchResult,
    create_search_provider,
    get_available_providers,
)

__all__ = [
    "compliance_search_tool",
    "deep_compliance_search",
    "SearchProvider",
    "SearchProviderError",
    "SearchResult",
    "ProviderType",
    "create_search_provider",
    "get_available_providers",
]
