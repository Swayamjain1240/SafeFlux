"""Baseline HTTP security headers (rules 10–12)."""


def test_security_headers_present(client):
    response = client.get("/api/v1/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    # Development must never send HSTS (would pin dev to HTTPS).
    assert "Strict-Transport-Security" not in response.headers


def test_production_https_adds_hsts(settings_factory, build_client):
    with build_client(
        settings_factory(ENVIRONMENT="production", JWT_SECRET="p" * 48),
        base_url="https://testserver",
    ) as prod_client:
        response = prod_client.get("/api/v1/health")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_production_disables_interactive_docs(settings_factory, build_client):
    with build_client(settings_factory(ENVIRONMENT="production", JWT_SECRET="p" * 48)) as prod_client:
        assert prod_client.get("/docs").status_code == 404
        assert prod_client.get("/openapi.json").status_code == 404


def test_development_exposes_docs(settings_factory, build_client):
    with build_client(settings_factory()) as dev_client:
        assert dev_client.get("/docs").status_code == 200
        assert dev_client.get("/openapi.json").status_code == 200
