"""Environment validation (rules 2, 12, 16, 17): bad config must fail safely."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def _base(**overrides) -> dict:
    base = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": "sqlite:///./safeflux.db",
        "JWT_SECRET": "a" * 40,
        "FRONTEND_URL": "http://localhost:5173",
        "_env_file": None,
    }
    base.update(overrides)
    return base


def test_missing_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    values = _base()
    del values["JWT_SECRET"]

    with pytest.raises(ValidationError) as exc_info:
        Settings(**values)

    assert "JWT_SECRET" in str(exc_info.value)


def test_short_jwt_secret_rejected_in_production():
    with pytest.raises(ValidationError):
        Settings(**_base(ENVIRONMENT="production", JWT_SECRET="short-secret"))


def test_debug_forbidden_in_production():
    with pytest.raises(ValidationError):
        Settings(**_base(ENVIRONMENT="production", JWT_SECRET="p" * 48, DEBUG=True))


def test_wildcard_frontend_url_rejected():
    with pytest.raises(ValidationError):
        Settings(**_base(FRONTEND_URL="*"))


def test_frontend_url_with_path_rejected():
    with pytest.raises(ValidationError):
        Settings(**_base(FRONTEND_URL="http://localhost:5173/app"))


def test_unsupported_database_url_rejected():
    with pytest.raises(ValidationError):
        Settings(**_base(DATABASE_URL="mysql://user:pass@host/db"))


def test_placeholder_secret_rejected():
    with pytest.raises(ValidationError):
        Settings(**_base(JWT_SECRET="change-me"))


def test_secret_never_appears_in_repr():
    secret = "super-secret-value-that-must-not-leak"
    settings = Settings(**_base(JWT_SECRET=secret))

    assert secret not in repr(settings)
    assert secret not in str(settings)


def test_get_settings_fails_with_field_names_only(monkeypatch):
    """Startup with missing config must name fields, never echo values."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit) as exc_info:
        get_settings()

    message = str(exc_info.value)
    assert "JWT_SECRET" in message
    # No secret material and no traceback may appear in the startup message.
    assert "unit-test-secret" not in message
    assert "Traceback" not in message
