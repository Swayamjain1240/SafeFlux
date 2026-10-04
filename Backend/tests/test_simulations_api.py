"""Simulation endpoint coverage (Part 4, rule 23).

Covers authentication, object-level ownership (IDOR), schema validation, the
hard compute budgets, safe error format and the per-IP simulation rate limit.
"""

from __future__ import annotations

SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"
RUN_PATH = "/api/v1/simulations/run"

PASSWORD = "correct-horse-battery-staple"


def _plant_payload(**overrides) -> dict:
    payload = {
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
            "trip_delay_s": 30,
        },
    }
    payload.update(overrides)
    return payload


def _authed_client(build_client, email: str):
    client = build_client()
    response = client.post(
        SIGNUP_PATH, json={"fullName": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    return client


def _create_plant(client) -> str:
    response = client.post(PLANTS_PATH, json=_plant_payload())
    assert response.status_code == 201, response.text
    return response.json()["data"]["plant"]["id"]


def _scenario(**overrides) -> dict:
    payload = {"duration_s": 120.0, "time_step_s": 1.0, "label": "baseline"}
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# happy path
# --------------------------------------------------------------------------


def test_run_returns_deterministic_result(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)

    body = {"plant_id": plant_id, "scenario": _scenario()}
    first = client.post(RUN_PATH, json=body)
    second = client.post(RUN_PATH, json=body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200
    assert first.json()["success"] is True
    assert first.json()["data"] == second.json()["data"]

    result = first.json()["data"]["result"]
    assert result["summary"]["sample_count"] == 121
    assert result["summary"]["limit_exceeded"]["temperature_c"] is False
    assert "true_temperature_c" in result["series"]
    assert "observed_temperature_c" in result["series"]
    assert result["metadata"]["deterministic"] is True
    assert result["metadata"]["plant_id"] == plant_id


def test_run_with_faults_reports_events_and_extrema(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)
    response = client.post(
        RUN_PATH,
        json={
            "plant_id": plant_id,
            "scenario": _scenario(
                duration_s=600.0,
                label="cooling loss",
                faults=[{"type": "cooling_loss", "start_s": 0.0}],
            ),
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]["result"]
    assert result["summary"]["limit_exceeded"]["temperature_c"] is True
    assert result["summary"]["pump_stopped"] is True
    kinds = {event["kind"] for event in result["events"]}
    assert {"fault_applied", "limit_exceeded", "shutdown"} <= kinds
    assert result["extrema"]["true_temperature_c"]["max"]["value"] > 150.0


# --------------------------------------------------------------------------
# auth + ownership
# --------------------------------------------------------------------------


def test_run_requires_authentication(client):
    response = client.post(RUN_PATH, json={"plant_id": "anything", "scenario": _scenario()})
    assert response.status_code == 401
    assert response.json()["success"] is False


def test_unknown_plant_returns_404(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    response = client.post(
        RUN_PATH, json={"plant_id": "does-not-exist", "scenario": _scenario()}
    )
    assert response.status_code == 404


def test_cannot_simulate_another_users_plant(build_client):
    owner = _authed_client(build_client, "owner@example.com")
    plant_id = _create_plant(owner)

    intruder = _authed_client(build_client, "intruder@example.com")
    response = intruder.post(
        RUN_PATH, json={"plant_id": plant_id, "scenario": _scenario()}
    )
    assert response.status_code == 404
    assert response.json()["success"] is False


# --------------------------------------------------------------------------
# validation + budgets
# --------------------------------------------------------------------------


def test_schema_rejects_invalid_scenario_values(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)

    for scenario in (
        _scenario(duration_s=0.0),
        _scenario(time_step_s=0.0),
        _scenario(faults=[{"type": "feed_increase", "start_s": 1.0}]),  # missing factor
        _scenario(faults=[{"type": "valve_stuck", "start_s": 1.0}]),  # missing target_pct
        _scenario(faults=[{"type": "cooling_loss", "start_s": 99999.0}]),  # beyond duration
    ):
        response = client.post(RUN_PATH, json={"plant_id": plant_id, "scenario": scenario})
        assert response.status_code == 422, scenario
        assert response.json()["success"] is False


def test_unknown_fields_are_rejected(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)
    response = client.post(
        RUN_PATH,
        json={"plant_id": plant_id, "scenario": _scenario(), "owner_id": "attacker"},
    )
    assert response.status_code == 422


def test_max_duration_budget_is_enforced(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)
    response = client.post(
        RUN_PATH,
        json={"plant_id": plant_id, "scenario": _scenario(duration_s=999999.0, time_step_s=1.0)},
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    fields = {detail["field"] for detail in error["details"]}
    assert "duration_s" in fields


def test_max_sample_budget_is_enforced(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)
    response = client.post(
        RUN_PATH,
        json={"plant_id": plant_id, "scenario": _scenario(duration_s=3600.0, time_step_s=0.05)},
    )
    assert response.status_code == 422
    fields = {detail["field"] for detail in response.json()["error"]["details"]}
    assert "time_step_s" in fields


def test_budget_errors_do_not_echo_submitted_values(client):
    client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(client)
    response = client.post(
        RUN_PATH,
        json={"plant_id": plant_id, "scenario": _scenario(duration_s=987654.0, time_step_s=1.0)},
    )
    assert response.status_code == 422
    assert "987654" not in response.text


# --------------------------------------------------------------------------
# rate limiting
# --------------------------------------------------------------------------


def test_simulation_rate_limit_returns_429(build_client, settings_factory):
    limited = build_client(settings_factory(SIM_RATE_LIMIT_RUNS=2, SIM_RATE_LIMIT_WINDOW_SECONDS=60))
    limited.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    plant_id = _create_plant(limited)
    body = {"plant_id": plant_id, "scenario": _scenario()}

    assert limited.post(RUN_PATH, json=body).status_code == 200
    assert limited.post(RUN_PATH, json=body).status_code == 200
    third = limited.post(RUN_PATH, json=body)
    assert third.status_code == 429
    assert third.headers.get("Retry-After") is not None
    assert third.json()["error"]["code"] == "RATE_LIMITED"
