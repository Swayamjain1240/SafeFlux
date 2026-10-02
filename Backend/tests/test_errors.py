"""Error handling: consistent envelope, no leaked internals."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_unknown_route_returns_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert isinstance(body["error"]["message"], str)
    assert body["error"]["message"]


def test_wrong_method_returns_error_envelope(client):
    response = client.post("/api/v1/health")

    assert response.status_code == 405
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_validation_error_returns_sanitized_details():
    app = create_app()

    @app.get("/api/v1/_test/echo")
    def echo(value: int):  # pragma: no cover - exercised via TestClient
        return {"success": True, "data": {"value": value}}

    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/_test/echo", params={"value": "not-a-number"})

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    details = body["error"]["details"]
    assert details and details[0]["field"] == "query.value"
    # Submitted values must never be echoed back (injection/leak defense).
    assert "not-a-number" not in response.text


def test_unhandled_exception_returns_safe_500():
    app = create_app()

    @app.get("/api/v1/_test/boom")
    def boom():  # pragma: no cover - exercised via TestClient
        raise RuntimeError("secret-db-password-abc123 should never leak")

    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/_test/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret-db-password-abc123" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_error_responses_include_security_headers(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
