"""Search endpoint coverage (Part 7, rule 23).

HTTP-level tests over the *real* simulator and safety engine (no fake runner
here): the point is that an unsafe region seeded into a plant is discovered
automatically, and that the endpoint refuses anything that would grow the search
beyond its configured bounds.

Covers: capabilities, a coarse sweep that finds the seeded unsafe region,
boundary refinement, repeatability, sensitivity, limited combinations, auth,
object-level ownership (IDOR), schema validation, malicious values, the
value-no-echo guarantee, oversized-search rejection and the per-IP rate limit.
"""

from __future__ import annotations

import uuid

SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"
CAPABILITIES_PATH = "/api/v1/searches/capabilities"
RUN_PATH = "/api/v1/searches/run"

PASSWORD = "correct-horse-battery-staple"

#: The allowlist as the client sees it. A variable outside this set must never
#: become searchable, so the exact set is asserted rather than just "non-empty".
EXPECTED_VARIABLES = {
    "cooling_factor",
    "feed_factor",
    "outlet_factor",
    "valve_target_pct",
    "pump_factor",
    "shutdown_delay_s",
    "temperature_sensor_bias_c",
}


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


def _cooling_axis(**overrides) -> dict:
    """A full-range cooling sweep: the seeded unsafe region is at low cooling."""
    axis = {"variable": "cooling_factor", "minimum": 0.0, "maximum": 1.0, "steps": 9}
    axis.update(overrides)
    return axis


def _run_body(plant_id: str, **overrides) -> dict:
    body = {
        "plant_id": plant_id,
        "mode": "sweep",
        "plan": {"duration_s": 600.0, "time_step_s": 1.0, "label": "seeded search"},
        "axes": [_cooling_axis()],
        "refine": False,
    }
    body.update(overrides)
    return body


def _error_fields(response) -> list[str]:
    details = response.json()["error"].get("details") or []
    return [detail["field"] for detail in details]


# --------------------------------------------------------------------------
# capabilities
# --------------------------------------------------------------------------


def test_capabilities_requires_authentication(client):
    response = client.get(CAPABILITIES_PATH)
    assert response.status_code == 401, response.text
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_capabilities_publishes_the_allowlist_and_effective_budgets(build_client):
    client = _authed_client(build_client, "ada@example.com")
    response = client.get(CAPABILITIES_PATH)
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    variables = {spec["variable"] for spec in data["variables"]}
    assert variables == EXPECTED_VARIABLES
    for spec in data["variables"]:
        assert spec["minimum"] <= spec["default"] <= spec["maximum"]
        assert spec["direction"] in {"increasing", "decreasing", "neutral"}

    assert set(data["modes"]) == {"sweep", "sensitivity", "combinations"}
    limits = data["limits"]
    assert 1 <= limits["max_scenarios"] <= 2000
    assert 1 <= limits["max_combinations"] <= 200
    assert limits["timeout_s"] > 0

    versions = data["versions"]
    assert versions["deterministic"] is True
    assert versions["ai_involved"] is False


# --------------------------------------------------------------------------
# the seeded unsafe region is found without being told where it is
# --------------------------------------------------------------------------


def test_sweep_discovers_the_seeded_unsafe_region(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(RUN_PATH, json=_run_body(plant_id))
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["mode"] == "sweep"
    assert result["status"] == "complete"
    assert result["truncated"] is False
    # Nine distinct coarse points, no refinement: the count must be exact.
    assert result["counts"]["scenarios"] == 9
    assert result["counts"]["evaluations"] == 9
    # The seeded danger (cooling loss at the low end) must be found, and the
    # safe end must survive — one without the other means the search is not
    # actually discriminating.
    assert result["counts"]["safe"] >= 1
    assert result["counts"]["violation"] + result["counts"]["safeguard_activated"] >= 1
    assert result["counts"]["failing"] == len(result["failures"]) or result["counts"]["failing"] > 0

    failing = result["failures"]
    assert failing, "the seeded unsafe region was not reported as a failure"
    assert result["counts"]["failing"] == len(failing)
    assert failing[0]["status"] in {"violation", "safeguard_activated"}
    assert failing[0]["values"]["cooling_factor"] == 0.0

    # Evidence a reviewer can re-run: trace of every evaluated case plus the
    # configuration/version block.
    assert len(result["trace"]) == 9
    config = result["config"]
    assert config["versions"]["deterministic"] is True
    assert config["versions"]["ai_involved"] is False
    assert config["spec"]["mode"] == "sweep"
    assert config["limits"]["max_scenarios"] >= 9
    assert result["budget"]["max_scenarios"] >= 9
    assert result["budget"]["exceeded"] is None
    assert result["notes"]


def test_refinement_bisects_the_boundary_between_safe_and_unsafe(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(RUN_PATH, json=_run_body(plant_id, refine=True))
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["counts"]["boundary_candidates"] == 1
    boundary = result["boundaries"][0]
    assert boundary["variable"] == "cooling_factor"
    assert boundary["last_safe"] is not None
    assert boundary["first_unsafe"] is not None
    # cooling_factor's risk direction is decreasing (low cooling is dangerous),
    # so the last safe point sits *above* the first unsafe one.
    assert boundary["last_safe"] > boundary["first_unsafe"]
    assert boundary["monotonicity"] == "decreasing"
    assert boundary["method"] == "bisection"
    assert boundary["refined"] is True
    assert boundary["uncertainty"] is not None
    assert boundary["uncertainty"] > 0
    # Refinement is extra work, still inside the same budget.
    assert result["counts"]["evaluations"] > 9
    assert result["budget"]["scenarios_used"] == result["counts"]["evaluations"]


def test_run_is_reproducible(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    body = _run_body(plant_id, refine=True)
    first = client.post(RUN_PATH, json=body)
    second = client.post(RUN_PATH, json=body)
    assert first.status_code == 200, first.text
    assert second.status_code == 200

    first_data = first.json()["data"]
    second_data = second.json()["data"]
    # The only thing allowed to differ between two identical searches is how
    # long the machine took: every number that describes the *search* must be
    # byte-identical, because a result is evidence.
    assert first_data["budget"].pop("elapsed_s") >= 0
    assert second_data["budget"].pop("elapsed_s") >= 0
    assert first_data == second_data
    assert first_data["counts"]["scenarios"] > 0
    assert first_data["trace"]


def test_sensitivity_mode_ranks_variables_without_axes(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH,
        json=_run_body(
            plant_id,
            mode="sensitivity",
            axes=[],
            plan={"duration_s": 300.0, "time_step_s": 1.0, "label": "sensitivity"},
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["mode"] == "sensitivity"
    assert result["boundaries"] == []
    rows = result["sensitivity"]
    assert rows, "sensitivity must rank at least one variable"
    variables = [row["variable"] for row in rows]
    assert len(variables) == len(set(variables))
    for row in rows:
        assert row["influence"] in {"none", "moderate", "high", "critical"}
        assert row["low_value"] <= row["high_value"]
    # A sensor variable only changes what the plant observes, and the result
    # says so instead of implying a physical effect.
    assert result["counts"]["observation_only"] >= 1
    assert any("sensor" in note.lower() for note in result["notes"])


def test_combinations_mode_runs_a_bounded_grid(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH,
        json=_run_body(
            plant_id,
            mode="combinations",
            axes=[
                _cooling_axis(steps=3),
                {"variable": "feed_factor", "minimum": 1.0, "maximum": 3.0, "steps": 3},
            ],
            plan={"duration_s": 300.0, "time_step_s": 1.0, "label": "grid"},
        ),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]

    assert result["mode"] == "combinations"
    assert result["counts"]["scenarios"] == 9
    assert len(result["cases"]) == 9
    keys = [case["key"] for case in result["cases"]]
    assert len(keys) == len(set(keys))
    assert result["counts"]["boundary_candidates"] == 0
    combination = result["config"]["combination"]
    assert combination["grid_size"] == 9
    assert combination["evaluated"] == 9
    assert combination["skipped"] == 0
    assert combination["truncated"] is False
    assert combination["worst"]["key"] in keys


# --------------------------------------------------------------------------
# authentication and object-level ownership
# --------------------------------------------------------------------------


def test_run_requires_authentication(client):
    response = client.post(RUN_PATH, json=_run_body(str(uuid.uuid4())))
    assert response.status_code == 401, response.text
    assert response.json()["success"] is False


def test_unknown_plant_is_not_found(build_client):
    client = _authed_client(build_client, "ada@example.com")
    response = client.post(RUN_PATH, json=_run_body(str(uuid.uuid4())))
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_another_users_plant_is_not_found(build_client):
    owner = _authed_client(build_client, "owner@example.com")
    plant_id = _create_plant(owner)

    attacker = _authed_client(build_client, "attacker@example.com")
    response = attacker.post(RUN_PATH, json=_run_body(plant_id))

    # 404 (not 403): the attacker must not learn that the plant exists.
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_missing_plant_id_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    body = _run_body(str(uuid.uuid4()))
    del body["plant_id"]
    response = client.post(RUN_PATH, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------
# schema validation: invalid and malicious values
# --------------------------------------------------------------------------


def test_unknown_variable_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH, json=_run_body(plant_id, axes=[_cooling_axis(variable="__import__")])
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert any("axes" in field for field in _error_fields(response))


def test_unknown_field_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    body = _run_body(plant_id)
    body["shell_command"] = "rm -rf /"
    response = client.post(RUN_PATH, json=body)
    assert response.status_code == 422, response.text
    # Reported against the body rather than by the submitted key name, so the
    # response never reflects arbitrary client text.
    assert _error_fields(response) == ["body"]
    assert "shell_command" not in response.text
    assert "rm -rf" not in response.text


def test_axis_outside_the_allowlisted_bounds_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH, json=_run_body(plant_id, axes=[_cooling_axis(minimum=-0.5)])
    )
    assert response.status_code == 422, response.text
    assert any("axes" in field for field in _error_fields(response))


def test_collapsed_axis_range_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH,
        json=_run_body(plant_id, axes=[_cooling_axis(minimum=0.5, maximum=0.5)]),
    )
    assert response.status_code == 422, response.text
    assert any("axes" in field for field in _error_fields(response))


def test_mode_and_axis_mismatch_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    # A sweep with two axes, and a sensitivity pass with one, are both refused
    # before any compute happens.
    two_axes = client.post(
        RUN_PATH,
        json=_run_body(
            plant_id,
            axes=[
                _cooling_axis(),
                {"variable": "feed_factor", "minimum": 1.0, "maximum": 3.0},
            ],
        ),
    )
    assert two_axes.status_code == 422, two_axes.text

    sensitivity = client.post(
        RUN_PATH, json=_run_body(plant_id, mode="sensitivity", axes=[_cooling_axis()])
    )
    assert sensitivity.status_code == 422, sensitivity.text

    duplicate = client.post(
        RUN_PATH,
        json=_run_body(
            plant_id,
            mode="combinations",
            axes=[_cooling_axis(), _cooling_axis()],
        ),
    )
    assert duplicate.status_code == 422, duplicate.text


def test_invalid_plan_values_are_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    for override in (
        {"duration_s": 0.0},
        {"duration_s": -60.0},
        {"time_step_s": 0.0},
        {"start_s": -1.0},
    ):
        plan = {"duration_s": 300.0, "time_step_s": 1.0, "label": "bad plan"}
        plan.update(override)
        response = client.post(RUN_PATH, json=_run_body(plant_id, plan=plan))
        assert response.status_code == 422, (override, response.text)
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_per_request_budget_above_the_configured_maximum_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    response = client.post(RUN_PATH, json=_run_body(plant_id, max_scenarios=5000))
    assert response.status_code == 422, response.text
    assert "max_scenarios" in _error_fields(response)

    response = client.post(RUN_PATH, json=_run_body(plant_id, timeout_s=300.0))
    assert response.status_code == 422, response.text
    assert "timeout_s" in _error_fields(response)


def test_search_larger_than_the_scenario_budget_is_rejected(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    # Nine points requested, three allowed: a rejection, never a silent clamp.
    response = client.post(RUN_PATH, json=_run_body(plant_id, max_scenarios=3))
    assert response.status_code == 422, response.text
    assert "steps" in _error_fields(response)


def test_refinement_deeper_than_configured_is_rejected(build_client, settings_factory):
    client = build_client(settings_factory(SEARCH_MAX_REFINEMENT_DEPTH=1))
    signup = client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    assert signup.status_code == 201, signup.text
    plant_id = _create_plant(client)

    response = client.post(
        RUN_PATH, json=_run_body(plant_id, refine=True, refinement_depth=6)
    )
    assert response.status_code == 422, response.text
    assert "refinement_depth" in _error_fields(response)


def test_submitted_values_are_never_echoed(build_client):
    client = _authed_client(build_client, "ada@example.com")
    plant_id = _create_plant(client)

    marker = "MARKER_5f1c_eval_exec"
    body = _run_body(plant_id, axes=[_cooling_axis(variable=marker)])
    body[marker] = marker
    response = client.post(RUN_PATH, json=body)

    assert response.status_code == 422, response.text
    # Neither the malicious variable name nor the extra field's value may come
    # back in the response body (rule 6 / safe API contract).
    assert marker not in response.text


# --------------------------------------------------------------------------
# rate limiting
# --------------------------------------------------------------------------


def test_search_rate_limit_returns_429(build_client, settings_factory):
    client = build_client(
        settings_factory(SEARCH_RATE_LIMIT_RUNS=2, SEARCH_RATE_LIMIT_WINDOW_SECONDS=60)
    )
    signup = client.post(
        SIGNUP_PATH,
        json={"fullName": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD},
    )
    assert signup.status_code == 201, signup.text
    plant_id = _create_plant(client)

    body = _run_body(
        plant_id, plan={"duration_s": 120.0, "time_step_s": 2.0, "label": "small"}
    )
    assert client.post(RUN_PATH, json=body).status_code == 200
    assert client.post(RUN_PATH, json=body).status_code == 200

    limited = client.post(RUN_PATH, json=body)
    assert limited.status_code == 429, limited.text
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert "Retry-After" in limited.headers
