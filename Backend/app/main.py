"""FastAPI application factory.

Kept intentionally small (docs/ARCHITECTURE.md §7): routing, middleware,
error handling. Business logic lives in services/modules.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limit import RateLimitMiddleware
from app.core.security import SecurityHeadersMiddleware, add_cors_middleware
from app.database import init_db
from app.telemetry import CurrentStateStore, TelemetryService

API_PREFIX = "/api/v1"
HEALTH_PATH = f"{API_PREFIX}/health"

logger = logging.getLogger("safeflux")


def configure_logging(settings: Settings) -> None:
    """DEBUG controls log verbosity only — FastAPI debug stays off always."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ANN202
        # MVP: create tables on startup (migration tool arrives later).
        init_db()
        yield

    app = FastAPI(
        title="SafeFlux API",
        description=(
            "SafeFlux — autonomous process-safety failure hunter. "
            "AI searches for danger, the simulator proves it, the engineer decides."
        ),
        version=__version__,
        # Never expose tracebacks or interactive docs in production.
        debug=False,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.auth_limiters = {}
    app.state.simulation_limiters = {}
    app.state.search_limiters = {}
    app.state.telemetry = TelemetryService(
        CurrentStateStore(
            max_history=settings.TELEMETRY_MAX_HISTORY,
            max_plants=settings.TELEMETRY_MAX_PLANTS,
        ),
        max_streams_total=settings.TELEMETRY_MAX_STREAMS,
        max_streams_per_plant=settings.TELEMETRY_MAX_STREAMS_PER_PLANT,
        max_streams_per_user=settings.TELEMETRY_MAX_STREAMS_PER_USER,
        replay_interval_s=settings.TELEMETRY_REPLAY_INTERVAL_MS / 1000.0,
    )

    register_exception_handlers(app)

    # Add order matters: Starlette's last-added middleware is outermost.
    # Desired stack (outer → inner): security headers → CORS → rate limit →
    # body-size guard → routes.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
    app.add_middleware(
        RateLimitMiddleware,
        limit=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        exempt_paths=frozenset({HEALTH_PATH}),
    )
    add_cors_middleware(app, settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)

    app.include_router(api_router, prefix=API_PREFIX)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        from app.core.responses import success_response

        return success_response(
            {"service": "safeflux-api", "version": __version__, "api": API_PREFIX}
        )

    return app


app = create_app()
