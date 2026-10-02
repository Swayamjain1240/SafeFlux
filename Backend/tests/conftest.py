"""Shared test setup.

Environment variables are set BEFORE any app import so Settings always has a
valid, secret-free configuration during tests.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///./safeflux_test.db")
os.environ.setdefault("JWT_SECRET", "unit-test-secret-0123456789abcdef0123456789abcdef")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "100000")
os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def make_settings(**overrides) -> Settings:
    """Settings instance built from explicit values (ignores .env file)."""
    base: dict = {
        "ENVIRONMENT": "development",
        "DEBUG": False,
        "DATABASE_URL": "sqlite:///./safeflux_test.db",
        "JWT_SECRET": "unit-test-secret-0123456789abcdef0123456789abcdef",
        "FRONTEND_URL": "http://localhost:5173",
        "RATE_LIMIT_REQUESTS": 100000,
        "RATE_LIMIT_WINDOW_SECONDS": 60,
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def settings_factory():
    return make_settings


@pytest.fixture()
def client():
    """TestClient for the default application."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def build_client():
    """Factory for TestClients with custom settings or extra routes."""
    apps = []

    def _build(settings: Settings | None = None, base_url: str = "http://testserver"):
        application = create_app(settings)
        apps.append(application)
        return TestClient(application, base_url=base_url)

    yield _build
    apps.clear()
