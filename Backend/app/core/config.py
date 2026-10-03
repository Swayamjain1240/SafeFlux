"""Environment-backed configuration for the SafeFlux backend.

Rules enforced here (SAFEFLUX_MASTER.md §13 / §16):
- every required variable is validated at startup (fail fast),
- secrets are wrapped in SecretStr so they can never be logged or returned,
- production forbids DEBUG and requires a strong JWT_SECRET.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "changeme",
    "change_me",
    "replace-me",
    "secret",
    "dev-secret",
    "development",
    "test",
    "password",
}

_SUPPORTED_DB_SCHEMES = {
    "sqlite",
    "sqlite+aiosqlite",
    "postgresql",
    "postgres",
    "postgresql+psycopg",
    "postgresql+asyncpg",
}


class Settings(BaseSettings):
    """Typed, validated application settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- core ---
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    DATABASE_URL: str
    JWT_SECRET: SecretStr
    FRONTEND_URL: str

    # --- baseline hardening knobs (safe defaults) ---
    RATE_LIMIT_REQUESTS: int = 120
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- authentication (Part 2) ---
    SESSION_TTL_MINUTES: int = 1440
    AUTH_RATE_LIMIT_ATTEMPTS: int = 10
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    MAX_REQUEST_BODY_BYTES: int = 65536

    # --- AI provider (Nebius / NVIDIA Nemotron), used from Part 8 ---
    NEBIUS_API_KEY: SecretStr | None = None
    NEBIUS_BASE_URL: str | None = None
    NEBIUS_MODEL: str | None = None

    # ---------------- validators ----------------

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in _SUPPORTED_DB_SCHEMES:
            raise ValueError(
                "DATABASE_URL must be a supported SQLAlchemy URL "
                "(sqlite:///... or postgresql://...)"
            )
        if not parsed.path:
            raise ValueError("DATABASE_URL is missing a database path")
        return value

    @field_validator("FRONTEND_URL")
    @classmethod
    def _validate_frontend_urls(cls, value: str) -> str:
        origins = [part.strip().rstrip("/") for part in value.split(",") if part.strip()]
        if not origins:
            raise ValueError("FRONTEND_URL must contain at least one origin")
        for origin in origins:
            if origin == "*":
                raise ValueError("FRONTEND_URL must never be a wildcard origin")
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    "FRONTEND_URL entries must be http(s) origins like https://app.example.com"
                )
            if parsed.path or parsed.query or parsed.fragment:
                raise ValueError("FRONTEND_URL entries must be bare origins without a path")
        return value

    @field_validator("JWT_SECRET")
    @classmethod
    def _validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value().strip()
        if len(raw) < 16:
            raise ValueError("JWT_SECRET must be at least 16 characters long")
        if raw.lower() in _PLACEHOLDER_SECRETS:
            raise ValueError("JWT_SECRET must not be a placeholder value")
        return SecretStr(raw)

    @field_validator("RATE_LIMIT_REQUESTS")
    @classmethod
    def _validate_rate_limit_requests(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RATE_LIMIT_REQUESTS must be >= 1")
        return value

    @field_validator("RATE_LIMIT_WINDOW_SECONDS")
    @classmethod
    def _validate_rate_limit_window(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be >= 1")
        return value

    @field_validator("SESSION_TTL_MINUTES")
    @classmethod
    def _validate_session_ttl(cls, value: int) -> int:
        if value < 5:
            raise ValueError("SESSION_TTL_MINUTES must be >= 5")
        if value > 43200:  # 30 days
            raise ValueError("SESSION_TTL_MINUTES must be <= 43200")
        return value

    @field_validator("AUTH_RATE_LIMIT_ATTEMPTS", "AUTH_RATE_LIMIT_WINDOW_SECONDS")
    @classmethod
    def _validate_positive_auth_setting(cls, value: int) -> int:
        if value < 1:
            raise ValueError("auth rate-limit settings must be >= 1")
        return value

    @field_validator("MAX_REQUEST_BODY_BYTES")
    @classmethod
    def _validate_max_body_bytes(cls, value: int) -> int:
        if value < 1024:
            raise ValueError("MAX_REQUEST_BODY_BYTES must be >= 1024")
        return value

    @model_validator(mode="after")
    def _production_constraints(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if len(self.JWT_SECRET.get_secret_value()) < 32:
                raise ValueError(
                    "JWT_SECRET must be at least 32 characters in production"
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
        return self

    # ---------------- derived values ----------------

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Explicit CORS allowlist derived from FRONTEND_URL."""
        return [part.strip().rstrip("/") for part in self.FRONTEND_URL.split(",") if part.strip()]

    @property
    def ai_configured(self) -> bool:
        return bool(
            self.NEBIUS_API_KEY
            and self.NEBIUS_BASE_URL
            and self.NEBIUS_MODEL
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once.

    On failure, exit with field names only — never with values, because a
    failing field could be a secret (ValidationError echoes its input).
    """
    try:
        return Settings()
    except ValidationError as exc:
        fields = sorted({str(loc) for err in exc.errors() for loc in err["loc"]})
        raise SystemExit(
            "SafeFlux backend configuration error. "
            f"Invalid or missing environment variables: {', '.join(fields)}. "
            "Copy Backend/.env.example to Backend/.env and fill in real values."
        ) from None
