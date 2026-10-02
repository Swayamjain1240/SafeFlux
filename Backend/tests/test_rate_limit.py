"""Baseline rate limiting (rule 8)."""


def test_requests_over_limit_receive_429_envelope(settings_factory, build_client):
    with build_client(
        settings_factory(RATE_LIMIT_REQUESTS=3, RATE_LIMIT_WINDOW_SECONDS=30)
    ) as limited:
        responses = [limited.get("/api/v1/does-not-exist") for _ in range(4)]

    blocked = responses[-1]
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMITED"
    assert blocked.headers["Retry-After"] == "30"

    # The three requests inside the window still went through normally.
    assert all(r.status_code == 404 for r in responses[:-1])


def test_rate_limit_window_recovers(settings_factory, build_client):
    import time

    with build_client(
        settings_factory(RATE_LIMIT_REQUESTS=2, RATE_LIMIT_WINDOW_SECONDS=1)
    ) as limited:
        assert limited.get("/api/v1/ping-a").status_code == 404
        assert limited.get("/api/v1/ping-b").status_code == 404
        assert limited.get("/api/v1/ping-c").status_code == 429
        time.sleep(1.1)
        assert limited.get("/api/v1/ping-d").status_code == 404
