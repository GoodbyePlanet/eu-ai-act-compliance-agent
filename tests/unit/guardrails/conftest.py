"""
Shared fixtures for guardrails tests.

This module contains mock objects and fixtures used across guardrail tests.
"""

from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_part():
    """Create a mock Part object with text attribute."""

    def _create_part(text: str):
        part = Mock()
        part.text = text
        return part

    return _create_part


@pytest.fixture
def mock_content(mock_part):
    """Create a mock Content object with parts list."""

    def _create_content(text: str):
        content = Mock()
        content.parts = [mock_part(text)]
        return content

    return _create_content


@pytest.fixture
def mock_event(mock_content):
    """Create a mock Event object with author and content."""

    def _create_event(author: str, text: str = None):
        event = Mock()
        event.author = author
        event.content = mock_content(text) if text else None
        return event

    return _create_event


@pytest.fixture
def mock_session(mock_event):
    """Create a mock Session object with events list."""

    def _create_session(events: list = None):
        session = Mock()
        session.events = events if events is not None else []
        return session

    return _create_session


@pytest.fixture
def mock_callback_context(mock_session):
    """Create a mock CallbackContext object with a session."""

    def _create_context(user_input: str = None, events: list = None):
        context = Mock()

        if events is not None:
            # Use provided events list
            context.session = mock_session(events)
        elif user_input is not None:
            # Create a simple session with one user event
            mock_event_obj = Mock()
            mock_event_obj.author = "user"
            mock_event_obj.content = Mock()
            mock_event_obj.content.parts = [Mock()]
            mock_event_obj.content.parts[0].text = user_input
            context.session = mock_session([mock_event_obj])
        else:
            # Empty session
            context.session = mock_session([])

        return context

    return _create_context


@pytest.fixture
def mock_tool():
    """Create a mock Tool object with name attribute."""

    def _create_tool(name: str):
        tool = Mock()
        tool.name = name
        return tool

    return _create_tool
