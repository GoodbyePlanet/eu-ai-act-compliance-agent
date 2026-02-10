"""
Google Serper search provider implementation.

This module provides a search provider that uses Google Serper API for web searches.
"""

from typing import List

from langchain_community.utilities import GoogleSerperAPIWrapper

from compliance_agent.tools.search_providers.base import (
    SearchProvider,
    SearchProviderError,
)


class GoogleSerperProvider(SearchProvider):
    """
    Search provider implementation using Google Serper API.

    Google Serper provides fast access to Google search results.
    Requires SERPER_API_KEY environment variable to be set.
    """

    def __init__(self, api_key: str):
        """
        Initialize the Google Serper provider.

        Args:
            api_key: The Serper API key.
        """
        if not api_key:
            raise SearchProviderError(
                self.name,
                "API key is required but was not provided.",
            )
        self._wrapper = GoogleSerperAPIWrapper(serper_api_key=api_key)

    @property
    def name(self) -> str:
        """Return the name of the search provider."""
        return "GoogleSerper"

    def _execute_search(self, query: str) -> dict:
        """
        Execute the raw search query against Google Serper API.

        Args:
            query: The search query string.

        Returns:
            Raw response dictionary from Google Serper.

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
        Extract organic search results from Google Serper response.

        Google Serper uses 'organic' key for organic search results.

        Args:
            raw_results: The raw response from Google Serper.

        Returns:
            List of organic result dictionaries.
        """
        return raw_results.get("organic", [])
