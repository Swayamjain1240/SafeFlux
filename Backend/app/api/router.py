"""API router aggregation. All endpoints live under /api/v1."""

from fastapi import APIRouter

from app.api.routes import auth, health, plants, searches, simulations, telemetry

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(plants.router, tags=["plants"])
api_router.include_router(simulations.router, tags=["simulations"])
api_router.include_router(telemetry.router, tags=["telemetry"])
api_router.include_router(searches.router, tags=["searches"])
