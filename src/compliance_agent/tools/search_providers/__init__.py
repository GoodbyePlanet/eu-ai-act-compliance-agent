"""
Search providers package for the EU AI Act Compliance Agent.

This package provides an extensible search provider architecture
with implementations for various search APIs.

Usage:
    from compliance_agent.tools.search_providers import create_search_provider

    # Auto-select provider based on available API keys
    provider = create_search_provider()
    results = provider.search("EU AI Act compliance")

    # Or explicitly select a provider
    from compliance_agent.tools.search_providers import ProviderType
    provider = create_search_provider(ProviderType.SERPAPI)
"""

from compliance_agent.tools.search_providers.base import (
    SearchProvider,
    SearchProviderError,
    SearchResult,
)
from compliance_agent.tools.search_providers.factory import (
    ProviderType,
    create_search_provider,
    get_available_providers,
)
from compliance_agent.tools.search_providers.serpapi import SerpAPIProvider
from compliance_agent.tools.search_providers.serper import GoogleSerperProvider

__all__ = [
    "SearchProvider",
    "SearchProviderError",
    "SearchResult",
    "ProviderType",
    "create_search_provider",
    "get_available_providers",
    "SerpAPIProvider",
    "GoogleSerperProvider",
]
