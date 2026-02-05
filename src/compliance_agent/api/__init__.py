"""
API module for the EU AI Act Compliance Agent.

This package contains the FastAPI application and request/response models.
"""

from compliance_agent.api.app import create_app
from compliance_agent.api.models import AssessRequest

__all__ = ["create_app", "AssessRequest"]
