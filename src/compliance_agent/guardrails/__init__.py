"""
Guardrails for the EU AI Act Compliance Agent.

This package contains all guardrail callbacks that protect the agent from:
- Prompt injection attacks
- Off-topic or harmful searches
"""

from compliance_agent.guardrails.callbacks import (
    validate_input_guardrail,
    output_validation_guardrail,
    tool_input_guardrail,
    BLOCKED_INPUT_PATTERNS,
    BLOCKED_SEARCH_TERMS,
    COMPLIANCE_SEARCH_TERMS,
    MAX_INPUT_LENGTH,
)

__all__ = [
    "validate_input_guardrail",
    "output_validation_guardrail",
    "tool_input_guardrail",
    "BLOCKED_INPUT_PATTERNS",
    "BLOCKED_SEARCH_TERMS",
    "COMPLIANCE_SEARCH_TERMS",
    "MAX_INPUT_LENGTH",
]
