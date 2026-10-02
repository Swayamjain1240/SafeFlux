"""Health endpoint + envelope contract."""

from app import __version__


def test_health_returns_success_envelope(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "safeflux-api"
    assert body["data"]["version"] == __version__
    assert body["data"]["environment"] == "development"


def test_health_carries_security_headers(client):
    response = client.get("/api/v1/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_root_returns_service_envelope(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["service"] == "safeflux-api"
    assert body["data"]["api"] == "/api/v1"


def test_health_is_exempt_from_rate_limiting(settings_factory, build_client):
    app_client = build_client(
        settings_factory(RATE_LIMIT_REQUESTS=2, RATE_LIMIT_WINDOW_SECONDS=60)
    )
    with app_client:
        for _ in range(5):
            response = app_client.get("/api/v1/health")
            assert response.status_code == 200
