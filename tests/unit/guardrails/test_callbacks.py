"""
Unit tests for guardrails callbacks.

Run with: pytest tests/unit/guardrails/test_callbacks.py -v
"""

import pytest

from compliance_agent.guardrails.callbacks import (
    validate_input_guardrail,
    tool_input_guardrail,
    output_validation_guardrail,
    BLOCKED_INPUT_PATTERNS,
    BLOCKED_SEARCH_TERMS,
    COMPLIANCE_SEARCH_TERMS,
    MAX_INPUT_LENGTH,
)


class TestValidateInputGuardrail:
    """Tests for validate_input_guardrail function."""

    def test_valid_input_returns_none(self, mock_callback_context):
        """Valid AI tool name should pass validation and return None."""
        # Arrange
        context = mock_callback_context(user_input="ChatGPT")

        # Act
        result = validate_input_guardrail(context)

        # Assert
        assert result is None

    # TODO: Add more tests for validate_input_guardrail
    # - test_empty_session_returns_none
    # - test_input_too_long_returns_error_content
    # - test_input_at_max_length_returns_none
    # - test_prompt_injection_ignore_instructions_blocked
    # - test_prompt_injection_case_insensitive
    # - test_session_without_events_attribute_returns_none


class TestToolInputGuardrail:
    """Tests for tool_input_guardrail function."""

    # TODO: Add tests for tool_input_guardrail
    # - test_valid_compliance_query_returns_none
    # - test_blocked_term_hack_returns_blocked_dict
    # - test_blocked_term_case_insensitive
    # - test_non_compliance_query_returns_none_with_warning
    # - test_different_tool_name_not_filtered
    # - test_empty_query_returns_none
    pass


class TestOutputValidationGuardrail:
    """Tests for output_validation_guardrail function."""

    # TODO: Add tests for output_validation_guardrail
    # - test_always_returns_none
    # - test_logs_completion_message (use capfd fixture)
    pass


class TestConfigurationConstants:
    """Tests for configuration constants."""

    # TODO: Add tests for constants
    # - test_max_input_length_is_500
    # - test_blocked_input_patterns_not_empty
    # - test_blocked_search_terms_not_empty
    # - test_compliance_search_terms_not_empty
    pass
