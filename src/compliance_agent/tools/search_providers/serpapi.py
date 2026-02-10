"""
SerpAPI search provider implementation.

This module provides a search provider that uses SerpAPI for web searches.
"""

from typing import List

from langchain_community.utilities import SerpAPIWrapper

from compliance_agent.tools.search_providers.base import (
    SearchProvider,
    SearchProviderError,
)


class SerpAPIProvider(SearchProvider):
    """
    Search provider implementation using SerpAPI.

    SerpAPI provides access to Google search results and other search engines.
    Requires SERPAPI_API_KEY environment variable to be set.
    """

    def __init__(self, api_key: str):
        """
        Initialize the SerpAPI provider.

        Args:
            api_key: The SerpAPI API key.
        """
        if not api_key:
            raise SearchProviderError(
                self.name,
                "API key is required but was not provided.",
            )
        self._wrapper = SerpAPIWrapper(serpapi_api_key=api_key)

    @property
    def name(self) -> str:
        """Return the name of the search provider."""
        return "SerpAPI"

    def _execute_search(self, query: str) -> dict:
        """
        Execute the raw search query against SerpAPI.

        Args:
            query: The search query string.

        Returns:
            Raw response dictionary from SerpAPI.

        Raises:
            SearchProviderError: If the search fails.
        """
        try:
            return self._wrapper.results(query)
        except Exception as e:
            raise SearchProviderError(
                self.name,
                f"Search failed for query '{query}': {str(e)}",
                original_error=e,
            )

    def _extract_organic_results(self, raw_results: dict) -> List[dict]:
        """
        Extract organic search results from SerpAPI response.

        SerpAPI uses 'organic_results' key for organic search results.

        Args:
            raw_results: The raw response from SerpAPI.

        Returns:
            List of organic result dictionaries.
        """
        return raw_results.get("organic_results", [])
