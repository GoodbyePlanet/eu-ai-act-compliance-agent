"""
Abstract base class for search providers.

This module defines the interface that all search providers must implement,
enabling extensibility and consistent behavior across different search APIs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SearchResult:
    """
    Represents a single search result with structured data.

    Attributes:
        title: The title of the search result.
        link: The URL of the search result.
        snippet: A brief description or excerpt from the page.
        source_type: Classification as "Official/Primary" or "Secondary".
    """

    title: str
    link: str
    snippet: str
    source_type: str = "Secondary"

    def to_dict(self) -> dict:
        """Convert the search result to a dictionary."""
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
            "source_type": self.source_type,
        }


class SearchProvider(ABC):
    """
    Abstract base class for search providers.

    All search provider implementations must inherit from this class
    and implement the required methods.
    """

    # Domains that indicate official/primary sources
    PRIMARY_DOMAINS = ("docs.", "legal.", "privacy.", "support.", "help.")

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the search provider."""
        pass

    @abstractmethod
    def _execute_search(self, query: str) -> dict:
        """
        Execute the raw search query against the provider's API.

        Args:
            query: The search query string.

        Returns:
            Raw response dictionary from the search API.
        """
        pass

    @abstractmethod
    def _extract_organic_results(self, raw_results: dict) -> List[dict]:
        """
        Extract organic search results from the raw API response.

        Args:
            raw_results: The raw response from the search API.

        Returns:
            List of organic result dictionaries.
        """
        pass

    def _classify_source(self, url: str) -> str:
        """
        Classify a URL as Official/Primary or Secondary based on domain patterns.

        Args:
            url: The URL to classify.

        Returns:
            "Official/Primary" if the URL matches primary domain patterns,
            otherwise "Secondary".
        """
        url_lower = url.lower()
        if any(domain in url_lower for domain in self.PRIMARY_DOMAINS):
            return "Official/Primary"
        return "Secondary"

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Execute a search and return structured results.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.

        Returns:
            List of SearchResult objects.

        Raises:
            SearchProviderError: If the search fails.
        """
        raw_results = self._execute_search(query)
        organic = self._extract_organic_results(raw_results)

        results = []
        for result in organic[:max_results]:
            link = result.get("link", "")
            search_result = SearchResult(
                title=result.get("title", ""),
                link=link,
                snippet=result.get("snippet", ""),
                source_type=self._classify_source(link),
            )
            results.append(search_result)

        return results


class SearchProviderError(Exception):
    """Exception raised when a search provider encounters an error."""

    def __init__(
        self,
        provider_name: str,
        message: str,
        original_error: Optional[Exception] = None,
    ):
        self.provider_name = provider_name
        self.original_error = original_error
        super().__init__(f"[{provider_name}] {message}")
