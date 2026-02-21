from compliance_agent.billing.tool_lock import canonicalize_tool_name, validate_follow_up_tool_lock


def test_canonicalize_tool_name_normalizes_text():
    """Canonicalization should normalize punctuation and casing."""
    result = canonicalize_tool_name("  Notion-AI!! ")
    assert result == "notion ai"


def test_follow_up_allows_same_tool_context():
    """Follow-up mentioning canonical tool should pass."""
    result = validate_follow_up_tool_lock(
        message="Can you focus more on Notion AI DPA status?",
        canonical_tool="Notion AI",
    )

    assert result.allowed is True


def test_follow_up_blocks_new_tool_attempt():
    """A short tool-name-like follow-up should be blocked."""
    result = validate_follow_up_tool_lock(
        message="Microsoft Copilot",
        canonical_tool="Notion AI",
    )

    assert result.allowed is False
    assert "different AI tool" in result.reason
