"""
Search tools for the EU AI Act Compliance Agent.

This module contains the web search tool used for gathering
compliance information about AI tools.
"""

import json

from dotenv import load_dotenv
from google.adk.tools import FunctionTool
from langchain_community.utilities import SerpAPIWrapper

load_dotenv()

# Initialize the search wrapper
search_wrapper = SerpAPIWrapper()


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
    print(f"DEBUG: Tool called with query: {query}")
    try:
        raw_results = search_wrapper.results(query)
        organic = raw_results.get("organic_results", [])

        if not organic:
            print(f"DEBUG: No results found for: {query}")
            return "No specific results found for this query."

        structured_data = []
        for result in organic[:5]:
            structured_data.append(
                {
                    "title": result.get("title"),
                    "link": result.get("link"),
                    "snippet": result.get("snippet"),
                    "source_type": "Official/Primary"
                    if any(
                        domain in result.get("link", "").lower()
                        for domain in ["docs.", "legal.", "privacy."]
                    )
                    else "Secondary",
                }
            )

        print(f"DEBUG: Found {len(structured_data)} results.")
        return json.dumps(structured_data, indent=2)

    except Exception as e:
        print(f"DEBUG: Search error: {str(e)}")
        return json.dumps({"error": f"Search failed: {str(e)}"})


# Create the FunctionTool wrapper for the agent
compliance_search_tool = FunctionTool(deep_compliance_search)
