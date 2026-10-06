"""Provider client coverage (Part 8, rules 1/2/23).

No network: a fake httpx client is injected, so every transport path (auth
failure, rate limit, server error, timeout, malformed body) is deterministic and
the tests can assert exactly how many attempts were made.

The security properties pinned here:

- an ``http://`` base URL is refused unless it is loopback, so a mistyped env var
  cannot downgrade the transport and send the key in clear text,
- the key travels only in the ``Authorization`` header of the request,
- a provider error never carries the body verbatim: it is redacted and capped.
"""

from __future__ import annotations

import types

import httpx
import pytest
from pydantic import SecretStr

from app.ai.constants import ProviderErrorCategory
from app.ai.provider import (
    NebiusProvider,
    ProviderConfig,
    ProviderError,
    validate_base_url,
)

FAKE_KEY = "sk-live-1234567890abcdefghijklmnop"


def _settings(**overrides):
    base = {
        "NEBIUS_API_KEY": SecretStr(FAKE_KEY),
        "NEBIUS_BASE_URL": "https://api.tokenfactory.nebius.com/v1",
        "NEBIUS_MODEL": "nvidia/nemotron-3-nano-30b-a3b",
        "AI_PROVIDER_TIMEOUT_S": 5.0,
        "AI_MAX_OUTPUT_TOKENS": 128,
        "AI_TEMPERATURE": 0.0,
        "AI_PROVIDER_MAX_ATTEMPTS": 2,
    }
    base.update(overrides)
    return types.SimpleNamespace(**base)


class FakeClient:
    """Minimal stand-in for ``httpx.Client`` that records what it was asked."""

    def __init__(self, responses=None, error=None):
        self._responses = list(responses or [])
        self._error = error
        self.calls: list[dict] = []

    def post(self, url, json=None, headers=None):  # noqa: A002 - mirrors httpx
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        if self._error is not None:
            raise self._error
        if not self._responses:
            raise AssertionError("fake client ran out of responses")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _ok(content: str = '{"focus": "cooling"}', model: str = "nvidia/nemotron-3-nano-30b-a3b"):
    return httpx.Response(
        200,
        json={
            "model": model,
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        },
    )


# ---------------------------------------------------------------------------
# base URL validation
# ---------------------------------------------------------------------------


def test_https_base_url_is_accepted_and_normalised():
    assert validate_base_url("https://api.tokenfactory.nebius.com/v1/") == (
        "https://api.tokenfactory.nebius.com/v1"
    )


def test_http_is_only_allowed_on_loopback():
    assert validate_base_url("http://localhost:8080/v1") == "http://localhost:8080/v1"
    assert validate_base_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"
    # A public http endpoint would send the key in clear text.
    assert validate_base_url("http://api.tokenfactory.nebius.com/v1") is None
    assert validate_base_url("ftp://example.com/v1") is None
    assert validate_base_url("not-a-url") is None
    assert validate_base_url("") is None
    assert validate_base_url(None) is None


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------


def test_config_unwraps_the_secret_but_stays_unconfigured_without_all_three():
    config = ProviderConfig.from_settings(_settings())
    assert config.configured is True
    assert config.api_key == FAKE_KEY
    assert config.chat_url == "https://api.tokenfactory.nebius.com/v1/chat/completions"

    for missing in ("NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL"):
        assert ProviderConfig.from_settings(_settings(**{missing: None})).configured is False


def test_config_refuses_an_insecure_base_url_even_with_a_key():
    config = ProviderConfig.from_settings(_settings(NEBIUS_BASE_URL="http://evil.example.com/v1"))
    assert config.configured is False
    assert config.chat_url is None


def test_unconfigured_provider_never_calls_the_transport():
    client = FakeClient(responses=[_ok()])
    provider = NebiusProvider(ProviderConfig(api_key=None, base_url=None, model=None), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.NOT_CONFIGURED
    assert client.calls == []


# ---------------------------------------------------------------------------
# transport
# ---------------------------------------------------------------------------


def test_successful_completion_reports_text_tokens_and_attempts():
    client = FakeClient(responses=[_ok(content='{"focus": "cooling loss"}')])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    response = provider.complete(system="system", messages=[{"role": "user", "content": "go"}])

    assert response.text == '{"focus": "cooling loss"}'
    assert response.tokens == 150
    assert response.finish_reason == "stop"
    assert response.attempts == 1
    assert response.latency_ms >= 0

    call = client.calls[0]
    assert call["url"].endswith("/v1/chat/completions")
    assert call["headers"]["Authorization"] == f"Bearer {FAKE_KEY}"
    assert call["json"]["model"] == "nvidia/nemotron-3-nano-30b-a3b"
    assert call["json"]["temperature"] == 0.0
    assert call["json"]["messages"][0]["role"] == "system"


def test_auth_failure_is_not_retried_and_never_leaks_the_body():
    client = FakeClient(responses=[httpx.Response(401, text=f'{{"detail": "bad key {FAKE_KEY}"}}')])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.AUTH
    assert FAKE_KEY not in excinfo.value.detail
    assert len(client.calls) == 1
    assert excinfo.value.to_dict()["error_category"] == "auth"


def test_rate_limit_maps_to_its_own_category_without_retrying():
    client = FakeClient(responses=[httpx.Response(429, json={"detail": "slow down"})])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.RATE_LIMIT
    assert len(client.calls) == 1


def test_server_error_is_retried_once_then_succeeds(monkeypatch):
    monkeypatch.setattr("app.ai.provider.time.sleep", lambda _seconds: None)
    client = FakeClient(responses=[httpx.Response(503, text="upstream"), _ok()])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    response = provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert response.attempts == 2
    assert len(client.calls) == 2


def test_server_error_exhausts_attempts_and_raises_the_category(monkeypatch):
    monkeypatch.setattr("app.ai.provider.time.sleep", lambda _seconds: None)
    client = FakeClient(responses=[httpx.Response(500, text="boom"), httpx.Response(500, text="boom")])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.SERVER
    assert len(client.calls) == 2


def test_timeout_is_retried_then_reported_as_timeout(monkeypatch):
    monkeypatch.setattr("app.ai.provider.time.sleep", lambda _seconds: None)
    client = FakeClient(error=httpx.TimeoutException("too slow"))
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.TIMEOUT
    assert len(client.calls) == 2


def test_connection_failure_is_reported_as_connection():
    client = FakeClient(error=httpx.ConnectError("dns dead"))
    provider = NebiusProvider(
        ProviderConfig.from_settings(_settings(AI_PROVIDER_MAX_ATTEMPTS=1)), client=client
    )

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.CONNECTION


def test_malformed_and_empty_bodies_are_invalid_response():
    for response in (
        httpx.Response(200, text="not json at all"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
    ):
        client = FakeClient(responses=[response])
        provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)
        with pytest.raises(ProviderError) as excinfo:
            provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])
        assert excinfo.value.category is ProviderErrorCategory.INVALID_RESPONSE


def test_unexpected_client_error_status_is_invalid_response():
    client = FakeClient(responses=[httpx.Response(418, text="teapot")])
    provider = NebiusProvider(ProviderConfig.from_settings(_settings()), client=client)

    with pytest.raises(ProviderError) as excinfo:
        provider.complete(system="s", messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.category is ProviderErrorCategory.INVALID_RESPONSE
    assert "teapot" in excinfo.value.detail
