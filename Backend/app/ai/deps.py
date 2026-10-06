"""Dependency wiring for the investigation endpoints (Part 8).

The service (and with it the provider factory and the duplicate-run guard) lives
on the app instance, so tests can replace it through
``app.dependency_overrides`` without touching a single route.
"""

from __future__ import annotations

from fastapi import Request

from app.ai.service import InvestigationService


def get_ai_service(request: Request) -> InvestigationService:
    """Return the app's investigation service, creating it once if absent."""
    service = getattr(request.app.state, "ai_service", None)
    if service is None:
        service = InvestigationService()
        request.app.state.ai_service = service
    return service


__all__ = ["get_ai_service"]
