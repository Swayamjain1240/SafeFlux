"""The one place SafeFlux talks to an external model provider (Part 8).

Provider choice is a *configuration* decision, never a code fact: the base URL
and the model id live in ``NEBIUS_BASE_URL`` / ``NEBIUS_MODEL`` and are validated
here, so no model id is permanently hard-coded and no key is ever written into a
source file.

Security properties of this module:

- the key is read from settings as a ``SecretStr`` and unwrapped only to build the
  ``Authorization`` header; it is never logged, never returned and never placed in
  an error message,
- an ``http://`` base URL is only accepted for a loopback host, so a mistyped
  environment variable cannot send the key in clear text to the internet,
- provider failures are mapped to a small error vocabulary (``auth``,
  ``rate_limit``, ``timeout``, ``connection``, ``server``, ``invalid_response``),
  and any detail is redacted and length-capped before it can be logged,
- only transient categories are retried, with a bounded attempt count and a short
  backoff, so a provider outage cannot turn into an unbounded loop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.ai.constants import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_TEMPERATURE,
    PROVIDER_MAX_ATTEMPTS,
    PROVIDER_NAME,
    PROVIDER_TIMEOUT_S,
    ProviderErrorCategory,
)
from app.ai.security import redact_secrets

#: Categories worth one more attempt: nothing about them is the request's fault.
_TRANSIENT: frozenset[ProviderErrorCategory] = frozenset(
    {
        ProviderErrorCategory.TIMEOUT,
        ProviderErrorCategory.CONNECTION,
        ProviderErrorCategory.SERVER,
    }
)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


class ProviderError(RuntimeError):
    """A provider failure described by category, never by raw response body."""

    def __init__(self, category: ProviderErrorCategory, detail: str = "") -> None:
        safe_detail = redact_secrets(" ".join(str(detail).split()))[:200]
        super().__init__(f"provider error: {category.value}")
        self.category = category
        self.detail = safe_detail

    def to_dict(self) -> dict[str, str]:
        """Log-safe representation (no key, no header, no raw body)."""
        return {"error_category": self.category.value, "detail": self.detail}


def validate_base_url(value: str | None) -> str | None:
    """Accept an https URL, or an http URL on loopback only. ``None`` if unusable.

    A key must never travel in clear text: a typo in ``NEBIUS_BASE_URL`` should
    fail loudly instead of quietly downgrading the transport.
    """
    if not value:
        return None
    candidate = value.strip().rstrip("/")
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme == "https" and parsed.netloc:
        return candidate
    if parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTS:
        return candidate
    return None


@dataclass(frozen=True)
class ProviderConfig:
    """Everything the provider needs, resolved once from Settings."""

    api_key: str | None
    base_url: str | None
    model: str | None
    timeout_s: float = PROVIDER_TIMEOUT_S
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    max_attempts: int = PROVIDER_MAX_ATTEMPTS

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    @property
    def chat_url(self) -> str | None:
        if not self.base_url:
            return None
        return f"{self.base_url.rstrip('/')}/chat/completions"

    @classmethod
    def from_settings(cls, settings: object) -> "ProviderConfig":
        """Build from Settings without ever holding the secret as a plain field.

        ``SecretStr`` is unwrapped here and nowhere else, so the rest of the
        package can treat configuration as an opaque value.
        """
        raw_key = getattr(settings, "NEBIUS_API_KEY", None)
        api_key = raw_key.get_secret_value() if hasattr(raw_key, "get_secret_value") else None
        return cls(
            api_key=api_key or None,
            base_url=validate_base_url(getattr(settings, "NEBIUS_BASE_URL", None)),
            model=(getattr(settings, "NEBIUS_MODEL", None) or None),
            timeout_s=float(getattr(settings, "AI_PROVIDER_TIMEOUT_S", PROVIDER_TIMEOUT_S)),
            max_output_tokens=int(
                getattr(settings, "AI_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS)
            ),
            temperature=float(getattr(settings, "AI_TEMPERATURE", DEFAULT_TEMPERATURE)),
            max_attempts=max(1, int(getattr(settings, "AI_PROVIDER_MAX_ATTEMPTS", PROVIDER_MAX_ATTEMPTS))),
        )


@dataclass(frozen=True)
class ProviderResponse:
    """One completion, with the accounting the budget needs."""

    text: str
    model: str
    latency_ms: int
    attempts: int = 1
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None

    @property
    def tokens(self) -> int:
        return (self.prompt_tokens or 0) + (self.completion_tokens or 0)


class AiProvider(Protocol):
    """The whole surface the agent is allowed to depend on."""

    name: str
    model_id: str

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:  # pragma: no cover - protocol declaration
        ...


class NebiusProvider:
    """OpenAI-compatible Token Factory client (the only shipping provider)."""

    name = PROVIDER_NAME

    def __init__(self, config: ProviderConfig, client: httpx.Client | None = None) -> None:
        self._config = config
        self._client = client
        self.model_id = config.model or ""

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def _post(self, *, payload: dict[str, Any]) -> httpx.Response:
        """One HTTP attempt. The key lives only inside this call frame."""
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = self._config.chat_url or ""
        if self._client is not None:
            return self._client.post(url, json=payload, headers=headers)
        with httpx.Client(timeout=self._config.timeout_s) as client:
            return client.post(url, json=payload, headers=headers)

    def _classify(self, response: httpx.Response) -> ProviderErrorCategory | None:
        status = response.status_code
        if 200 <= status < 300:
            return None
        if status in (401, 403):
            return ProviderErrorCategory.AUTH
        if status == 429:
            return ProviderErrorCategory.RATE_LIMIT
        if status >= 500:
            return ProviderErrorCategory.SERVER
        return ProviderErrorCategory.INVALID_RESPONSE

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        max_output_tokens: int | None = None,
    ) -> ProviderResponse:
        if not self._config.configured:
            raise ProviderError(ProviderErrorCategory.NOT_CONFIGURED)

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": self._config.temperature,
            "max_tokens": max_output_tokens or self._config.max_output_tokens,
        }

        started = time.monotonic()
        last_error: ProviderError | None = None
        attempts = 0

        for attempt in range(1, self._config.max_attempts + 1):
            attempts = attempt
            try:
                response = self._post(payload=payload)
            except httpx.TimeoutException as exc:
                last_error = ProviderError(ProviderErrorCategory.TIMEOUT, str(exc))
            except httpx.HTTPError as exc:
                last_error = ProviderError(ProviderErrorCategory.CONNECTION, str(exc))
            else:
                category = self._classify(response)
                if category is None:
                    return self._to_response(response, started, attempts)
                # The body may echo request context, so it is only ever used as a
                # detail string, which ProviderError redacts and caps.
                last_error = ProviderError(category, response.text[:400])

            if last_error.category not in _TRANSIENT or attempt == self._config.max_attempts:
                raise last_error
            time.sleep(min(0.25 * attempt, 1.0))

        # Unreachable: the loop either returns or raises.
        raise last_error or ProviderError(ProviderErrorCategory.CONNECTION)

    def _to_response(
        self, response: httpx.Response, started: float, attempts: int
    ) -> ProviderResponse:
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            body = response.json()
        except ValueError as exc:
            raise ProviderError(ProviderErrorCategory.INVALID_RESPONSE, "not json") from exc

        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ProviderError(ProviderErrorCategory.INVALID_RESPONSE, "no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = (message or {}).get("content") if isinstance(message, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(ProviderErrorCategory.INVALID_RESPONSE, "empty content")

        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        return ProviderResponse(
            text=text,
            model=str(body.get("model") or self.model_id),
            latency_ms=latency_ms,
            attempts=attempts,
            prompt_tokens=usage.get("prompt_tokens") if isinstance(usage, dict) else None,
            completion_tokens=usage.get("completion_tokens") if isinstance(usage, dict) else None,
            finish_reason=choices[0].get("finish_reason") if isinstance(choices[0], dict) else None,
        )


def build_provider(config: ProviderConfig, client: httpx.Client | None = None) -> AiProvider:
    """The provider used in production. Tests inject their own implementation."""
    return NebiusProvider(config, client=client)


__all__ = [
    "AiProvider",
    "NebiusProvider",
    "ProviderConfig",
    "ProviderError",
    "ProviderResponse",
    "build_provider",
    "validate_base_url",
]
