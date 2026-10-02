from fastapi import APIRouter

from app import __version__
from app.api.routes.schemas import HealthResponse
from app.core.config import get_settings
from app.core.responses import success_response

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="API health probe")
def health() -> dict:
    """Liveness/readiness probe used by the frontend and monitoring.

    Exempt from rate limiting so health checks are never throttled.
    """
    settings = get_settings()
    return success_response(
        {
            "status": "ok",
            "service": "safeflux-api",
            "version": __version__,
            "environment": settings.ENVIRONMENT,
        }
    )
