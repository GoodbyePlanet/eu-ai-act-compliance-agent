"""
Search provider factory for automatic provider selection.

This module provides a factory function that automatically selects
and instantiates the appropriate search provider based on available
API keys in the environment.
"""

import os
from enum import Enum
from typing import Optional

from compliance_agent.tools.search_providers.base import (
    SearchProvider,
    SearchProviderError,
)
from compliance_agent.tools.search_providers.serpapi import SerpAPIProvider
from compliance_agent.tools.search_providers.serper import GoogleSerperProvider


class ProviderType(Enum):
    """Enumeration of available search provider types."""

    SERPER = "serper"
    SERPAPI = "serpapi"


def create_search_provider(
    provider_type: Optional[ProviderType] = None,
) -> SearchProvider:
    """
    Create and return a search provider instance.

    If no provider type is specified, it automatically selects based on
    available environment variables. Priority order:
    1. SERPER_API_KEY -> GoogleSerperProvider
    2. SERPAPI_API_KEY -> SerpAPIProvider

    Args:
        provider_type: Optional explicit provider type to use.

    Returns:
        An initialized SearchProvider instance.

    Raises:
        SearchProviderError: If no valid API key is found or provider
            initialization fails.
    """
    serper_api_key = os.environ.get("SERPER_API_KEY", "")
    serpapi_api_key = os.environ.get("SERPAPI_API_KEY", "")

    if provider_type == ProviderType.SERPER:
        if not serper_api_key:
            raise SearchProviderError(
                "Factory",
                "SERPER_API_KEY environment variable is not set.",
            )
        print("Creating GoogleSerper provider (explicitly requested).")
        return GoogleSerperProvider(api_key=serper_api_key)

    if provider_type == ProviderType.SERPAPI:
        if not serpapi_api_key:
            raise SearchProviderError(
                "Factory",
                "SERPAPI_API_KEY environment variable is not set.",
            )
        print("Creating SerpAPI provider (explicitly requested).")
        return SerpAPIProvider(api_key=serpapi_api_key)

    if serper_api_key:
        print("Auto-selected GoogleSerper provider (SERPER_API_KEY found).")
        return GoogleSerperProvider(api_key=serper_api_key)

    if serpapi_api_key:
        print("Auto-selected SerpAPI provider (SERPAPI_API_KEY found).")
        return SerpAPIProvider(api_key=serpapi_api_key)

    raise SearchProviderError(
        "Factory",
        "No search API key found. Set SERPER_API_KEY or SERPAPI_API_KEY.",
    )


def get_available_providers() -> list[ProviderType]:
    """
    Return a list of provider types that have valid API keys configured.

    Returns:
        List of ProviderType values for providers with available API keys.
    """
    available = []

    if os.environ.get("SERPER_API_KEY"):
        available.append(ProviderType.SERPER)

    if os.environ.get("SERPAPI_API_KEY"):
        available.append(ProviderType.SERPAPI)

    return available
