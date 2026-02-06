"""
Guardrail callbacks for the EU AI Act Compliance Agent.

This module contains all guardrail callback functions that protect the agent from:
- Prompt injection attacks
- Off-topic or harmful searches
"""

import re
from typing import Optional, Dict, Any

from google.adk.tools.tool_context import ToolContext
from google.genai import types

# Patterns that might indicate prompt injection or misuse
BLOCKED_INPUT_PATTERNS = [
    r"ignore.*previous.*instructions",
    r"disregard.*above",
    r"you are now",
    r"pretend to be",
    r"jailbreak",
    r"bypass.*restrictions",
    r"act as.*different",
    r"forget.*instructions",
    r"new persona",
    r"roleplay as",
]

# Maximum input length for AI tool names
MAX_INPUT_LENGTH = 500

# Blocked search terms that are off-topic or potentially harmful
BLOCKED_SEARCH_TERMS = [
    "hack",
    "exploit",
    "bypass security",
    "steal data",
    "illegal",
    "weapons",
    "drugs",
    "violence",
    "malware",
    "phishing",
    "credential",
    "password crack",
]

# Compliance-related terms to encourage on-topic searches
COMPLIANCE_SEARCH_TERMS = [
    "compliance",
    "gdpr",
    "ai act",
    "privacy policy",
    "data protection",
    "dpa",
    "terms of service",
    "security",
    "documentation",
    "api",
    "legal",
    "transparency",
    "oversight",
    "risk",
    "audit",
]


def validate_input_guardrail(callback_context) -> Optional[types.Content]:
    """
    Guardrail: Validates user input before agent processing.

    Checks for:
    - Input length limits
    - Prompt injection patterns

    Returns:
        Content to short-circuit if input is invalid, None otherwise.
    """
    session = callback_context.session

    # Get the last user message from session events
    user_input = ""
    if hasattr(session, "events") and session.events:
        for event in reversed(session.events):
            if event.author == "user" and event.content:
                if event.content.parts:
                    user_input = (
                        event.content.parts[0].text
                        if hasattr(event.content.parts[0], "text")
                        else ""
                    )
                break

    if not user_input:
        return None  # No input to validate, continue

    # Check input length
    if len(user_input) > MAX_INPUT_LENGTH:
        print(f"GUARDRAIL: Input rejected - too long ({len(user_input)} chars)")
        return types.Content(
            role="model",
            parts=[
                types.Part(
                    text=f"Input too long. Please limit your AI tool name/request to {MAX_INPUT_LENGTH} characters."
                )
            ],
        )

    # Check for prompt injection patterns
    user_input_lower = user_input.lower()
    for pattern in BLOCKED_INPUT_PATTERNS:
        if re.search(pattern, user_input_lower):
            print(f"GUARDRAIL: Input rejected - matched blocked pattern: {pattern}")
            return types.Content(
                role="model",
                parts=[
                    types.Part(
                        text="Your request contains disallowed patterns. I can only assist with EU AI Act compliance assessments. Please provide a valid AI tool name."
                    )
                ],
            )

    print("GUARDRAIL: Input validated successfully")
    return None


def tool_input_guardrail(
    tool, args: Dict[str, Any], tool_context: ToolContext
) -> Optional[Dict[str, Any]]:
    """
    Guardrail: Validates and sanitizes tool inputs before execution.

    Checks for:
    - Blocked/off-topic search terms
    - Non-compliance-related queries (warning only)

    Returns:
        Dict to short-circuit the tool with a custom response, None otherwise.
    """
    tool_name = tool.name if hasattr(tool, "name") else str(tool)

    if "deep_compliance_search" in tool_name or "compliance_search" in tool_name:
        query = args.get("query", "").lower()

        # Block dangerous/off-topic search terms
        for blocked in BLOCKED_SEARCH_TERMS:
            if blocked in query:
                print(f"GUARDRAIL: Search blocked - contains term: {blocked}")
                return {
                    "blocked": True,
                    "reason": f"Search query contains off-topic term '{blocked}'. Please focus on compliance-related searches for the AI tool.",
                }

        # Log warning if query doesn't seem compliance-related
        has_compliance_term = any(term in query for term in COMPLIANCE_SEARCH_TERMS)
        if not has_compliance_term:
            print(f"GUARDRAIL WARNING: Query may not be compliance-related: {query}")
        else:
            print(f"GUARDRAIL: Search query approved: {query[:50]}...")

    return None


def output_validation_guardrail(callback_context) -> Optional[types.Content]:
    """
    Guardrail: Validates agent output before returning to user.

    Can be extended to:
    - Add disclaimers to the output
    - Check for completeness of the compliance report
    - Log outputs for audit purposes

    Returns:
        Content to append/modify output, None otherwise.
    """
    print("GUARDRAIL: Output validation completed")
    return None
