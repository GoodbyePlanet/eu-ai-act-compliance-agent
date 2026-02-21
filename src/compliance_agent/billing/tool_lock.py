"""Tool lock logic for follow-up messages in paid sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolLockResult:
    """Result from follow-up tool lock validation."""

    allowed: bool
    reason: str = ""


def canonicalize_tool_name(value: str) -> str:
    """Normalize a tool name for matching and fingerprinting."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_new_tool_attempt_in_follow_up(message: str, canonical_tool: str) -> bool:
    """Detect probable attempts to switch to another tool inside follow-up text."""
    if not message.strip() or not canonical_tool.strip():
        return False

    msg = canonicalize_tool_name(message)
    canonical = canonicalize_tool_name(canonical_tool)

    if not msg or not canonical:
        return False

    if canonical in msg:
        return False

    canonical_tokens = set(canonical.split())
    message_tokens = set(msg.split())
    if canonical_tokens & message_tokens:
        return False

    words = msg.split()
    # Strong signal: user enters another short tool name as follow-up.
    if len(words) <= 5 and "?" not in message and "." not in message:
        return True

    assessment_intent = re.search(r"\b(assess|evaluate|analy[sz]e|review|check)\b", msg)
    tool_object = re.search(r"\b(tool|model|ai)\b", msg)
    if assessment_intent and (tool_object or len(words) >= 3):
        return True

    return False


def validate_follow_up_tool_lock(message: str, canonical_tool: str) -> ToolLockResult:
    """Validate that follow-up text stays within the session's canonical tool scope."""
    if is_new_tool_attempt_in_follow_up(message, canonical_tool):
        return ToolLockResult(
            allowed=False,
            reason=(
                "Detected a request to assess a different AI tool in this follow-up. "
                "Start a new assessment session to consume another credit."
            ),
        )
    return ToolLockResult(allowed=True)
