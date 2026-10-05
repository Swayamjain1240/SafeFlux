"""Telemetry endpoint coverage (Part 5, rule 23).

Covers current/history reads, bounded history limits, SSE authentication and
object-level ownership (IDOR), stream connection limits, and disconnect cleanup
(the stream slot is released on close).
"""

from __future__ import annotations

SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"
RUN_PATH = "/api/v1/simulations/run"

PASSWORD = "correct-horse-battery-staple"


def _plant_payload() -> dict:
    return {
        "name": "Reactor Train A",
        "description": "Baseline MVP process",
        "location": "Line 1",
        "config": {
            "feed_flow_lpm": 120.0,
            "cooling_pct": 90.0,
            "valve_position_pct": 55.0,
            "heater_power_pct": 60.0,
            "shutdown_delay_s": 5,
        },
        "state": {
            "pump_running": True,
            "temperature_c": 80.0,
            "pressure_bar": 4.0,
            "level_pct": 45.0,
        },
        "safety_limits": {
            "max_temperature_c": 150.0,
            "max_pressure_bar": 10.0,
            "max_level_pct": 90.0,
        },
        "safeguards": {
            "auto_shutdown_enabled": True,
            "high_temperature_trip": True,
            "high_pressure_trip": True,
            "high_level_trip": True,
            "trip_delay_s": 5,
        },
    }


def _signup(client, email: str):
    response = client.post(
        SIGNUP_PATH, json={"fullName": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return client


def _authed(build_client, settings_factory, email: str):
    client = build_client(settings_factory(TELEMETRY_REPLAY_INTERVAL_MS=0))
    _signup(client, email)
    return client


def _create_plant(client) -> str:
    response = client.post(PLANTS_PATH, json=_plant_payload())
    assert response.status_code == 201, response.text
    return response.json()["data"]["plant"]["id"]


def _run(client, plant_id: str, duration: float = 120.0, faults: list | None = None):
    body = {
        "plant_id": plant_id,
        "scenario": {
            "duration_s": duration,
            "time_step_s": 1.0,
            "label": "telemetry",
            "faults": faults or [],
        },
    }
    response = client.post(RUN_PATH, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _read_sse_events(client, path: str) -> list[str]:
    events: list[str] = []
    with client.stream("GET", path) as response:
        assert response.status_code == 200, response.text
        for line in response.iter_lines():
            if line.startswith("event: "):
                events.append(line[len("event: ") :].strip())
    return events


# --------------------------------------------------------------------------
# reads
# --------------------------------------------------------------------------


def test_current_and_history_after_run(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id)

    current = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/current")
    assert current.status_code == 200
    frame = current.json()["data"]["frame"]
    assert frame is not None
    assert frame["type"] == "telemetry"
    assert frame["plant_id"] == plant_id
    assert "true_temperature_c" not in frame["values"]  # uses clean variable names
    assert "temperature_c" in frame["values"]
    assert "observed_temperature_c" not in frame  # observed kept separate
    assert set(frame["observed"]) == {"temperature_c", "pressure_bar"}

    history = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/history")
    assert history.status_code == 200
    data = history.json()["data"]
    assert data["count"] == 120  # default limit
    assert data["frames"][-1]["sequence"] == 120


def test_current_is_empty_before_any_run(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    response = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/current")
    assert response.status_code == 200
    assert response.json()["data"]["frame"] is None


def test_history_limit_is_bounded(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id)

    limited = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/history?limit=10")
    assert limited.status_code == 200
    body = limited.json()["data"]
    assert body["count"] == 10
    assert body["limit"] == 10

    for bad in ("?limit=0", "?limit=-5", "?limit=100000"):
        response = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/history{bad}")
        assert response.status_code == 422, bad


def test_history_retains_only_newest_frames(build_client, settings_factory):
    client = build_client(
        settings_factory(TELEMETRY_REPLAY_INTERVAL_MS=0, TELEMETRY_MAX_HISTORY=5)
    )
    _signup(client, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id)

    response = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/history")
    frames = response.json()["data"]["frames"]
    assert len(frames) == 5
    assert [f["sequence"] for f in frames] == [116, 117, 118, 119, 120]


# --------------------------------------------------------------------------
# stream: happy path, auth, ownership
# --------------------------------------------------------------------------


def test_stream_replays_frames_and_completes(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id, duration=10.0)

    events = _read_sse_events(client, f"{PLANTS_PATH}/{plant_id}/telemetry/stream")
    assert events.count("telemetry") == 11
    assert events[-1] == "complete"


def test_stream_requires_authentication(client):
    response = client.get(f"{PLANTS_PATH}/anything/telemetry/stream")
    assert response.status_code == 401


def test_stream_without_telemetry_returns_404(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    response = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/stream")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_stream_enforces_ownership(build_client, settings_factory):
    owner = _authed(build_client, settings_factory, "owner@example.com")
    plant_id = _create_plant(owner)
    _run(owner, plant_id)

    intruder = _authed(build_client, settings_factory, "intruder@example.com")
    response = intruder.get(f"{PLANTS_PATH}/{plant_id}/telemetry/stream")
    assert response.status_code == 404

    # Current/history are protected the same way.
    assert intruder.get(f"{PLANTS_PATH}/{plant_id}/telemetry/current").status_code == 404
    assert intruder.get(f"{PLANTS_PATH}/{plant_id}/telemetry/history").status_code == 404


# --------------------------------------------------------------------------
# stream: limits and cleanup
# --------------------------------------------------------------------------


def test_stream_connection_limit_returns_429(build_client, settings_factory):
    client = build_client(
        settings_factory(TELEMETRY_REPLAY_INTERVAL_MS=0, TELEMETRY_MAX_STREAMS_PER_PLANT=1)
    )
    _signup(client, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id)

    service = client.app.state.telemetry
    service.acquire(plant_id, "pre-holder")  # occupy the single per-plant slot
    try:
        response = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/stream")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert response.headers.get("Retry-After") is not None
    finally:
        service.release(plant_id, "pre-holder")


def test_stream_releases_slot_on_completion(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id, duration=5.0)

    _read_sse_events(client, f"{PLANTS_PATH}/{plant_id}/telemetry/stream")
    assert client.app.state.telemetry.active_streams(plant_id) == 0


def test_stream_releases_slot_on_early_disconnect(build_client, settings_factory):
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id, duration=5.0)

    # Read a single frame then close early: the slot must be freed.
    with client.stream("GET", f"{PLANTS_PATH}/{plant_id}/telemetry/stream") as response:
        for line in response.iter_lines():
            if line.startswith("data:"):
                break
    assert client.app.state.telemetry.active_streams(plant_id) == 0


def test_reconnect_after_disconnect_gets_current_state(build_client, settings_factory):
    """Reconnect contract: a dropped client can immediately re-read current."""
    client = _authed(build_client, settings_factory, "ada@example.com")
    plant_id = _create_plant(client)
    _run(client, plant_id, duration=5.0)

    with client.stream("GET", f"{PLANTS_PATH}/{plant_id}/telemetry/stream") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                break
    assert client.app.state.telemetry.active_streams(plant_id) == 0

    current = client.get(f"{PLANTS_PATH}/{plant_id}/telemetry/current")
    assert current.status_code == 200
    assert current.json()["data"]["frame"] is not None
