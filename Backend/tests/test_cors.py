"""Strict CORS allowlist (rule 10): explicit origins, credentials, no wildcard."""


def test_allowed_origin_gets_cors_headers(client, settings_factory):
    origin = settings_factory().cors_origins[0]

    response = client.get("/api/v1/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] != "*"


def test_unknown_origin_gets_no_cors_headers(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_preflight_only_allows_configured_origin_and_methods(client, settings_factory):
    origin = settings_factory().cors_origins[0]

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_cors_allowlist_never_contains_wildcard(settings_factory):
    settings = settings_factory(FRONTEND_URL="http://localhost:5173,https://app.example.com")

    assert "*" not in settings.cors_origins
    assert settings.cors_origins == ["http://localhost:5173", "https://app.example.com"]
