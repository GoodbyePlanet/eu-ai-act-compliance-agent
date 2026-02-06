"""
Tools for the EU AI Act Compliance Agent.

This package contains all tools available to the agent for conducting
compliance research and assessments.
"""

from compliance_agent.tools.search import compliance_search_tool, deep_compliance_search

__all__ = ["compliance_search_tool", "deep_compliance_search"]
