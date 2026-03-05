"""Public package exports for compliance agent runtime objects."""

from __future__ import annotations

from typing import Any

__all__ = ["execute", "root_agent", "runner", "session_service"]


def __getattr__(name: str) -> Any:
    """Lazily load heavy runtime objects only when explicitly requested."""
    if name in __all__:
        from compliance_agent.agent import execute, root_agent, runner, session_service

        return {
            "execute": execute,
            "root_agent": root_agent,
            "runner": runner,
            "session_service": session_service,
        }[name]
    raise AttributeError(f"module 'compliance_agent' has no attribute '{name}'")
