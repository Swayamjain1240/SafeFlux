"""API router aggregation. All endpoints live under /api/v1."""

from fastapi import APIRouter

from app.api.routes import auth, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
