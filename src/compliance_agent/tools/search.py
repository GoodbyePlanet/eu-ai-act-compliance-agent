"""
Search tools for the EU AI Act Compliance Agent.

This module contains the web search tool used for gathering
compliance information about AI tools.
"""

import json
import logging

from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool

from compliance_agent.tools.search_providers import (
    SearchProviderError,
    create_search_provider,
)

load_dotenv()
logger = logging.getLogger(__name__)
_search_provider = None


def _get_search_provider():
    """
    Lazily initialize and return the search provider.

    Uses module-level caching to avoid reinitializing on every search.
    """
    global _search_provider
    if _search_provider is None:
        _search_provider = create_search_provider()
        logger.info(f"Initialized search provider: {_search_provider.name}")
    return _search_provider


def deep_compliance_search(query: str) -> str:
    """
    Conducts a targeted web search for AI tool metadata.

    Returns structured data including page titles, snippets, and source URLs.
    Results are classified as "Official/Primary" or "Secondary" based on
    the source domain.

    Args:
        query: The specific compliance-related search term.

    Returns:
        JSON string containing search results with titles, links, snippets,
        and source type classification.
    """
    logger.info(f"Tool called with query: {query}")

    try:
        provider = _get_search_provider()
        results = provider.search(query, max_results=5)

        if not results:
            logger.info(f"No results found for: {query}")
            return "No specific results found for this query."

        structured_data = [result.to_dict() for result in results]

        logger.info(f"Found {len(structured_data)} results.")
        return json.dumps(structured_data, indent=2)

    except SearchProviderError as e:
        logger.error(f"Search provider error: {str(e)}")
        return json.dumps({"error": f"Search failed: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected search error: {str(e)}")
        return json.dumps({"error": f"Search failed: {str(e)}"})


compliance_search_tool = FunctionTool(deep_compliance_search)
