"""Plant setup coverage (Part 3, rule 23).

Required cases: creation, retrieval, update, invalid ranges, percentage
> 100, negative pressure, unauthenticated request, User A cannot read or
update User B's plant (IDOR), and state/limit consistency.
"""

from __future__ import annotations

import pytest

SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"

PASSWORD = "correct-horse-battery-staple"


def _valid_payload(**overrides) -> dict:
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
            "trip_delay_s": 2,
        },
    }
    payload.update(overrides)
    return payload


def _signup(client, email: str, name: str = "Ada Lovelace"):
    return client.post(
        SIGNUP_PATH,
        json={"fullName": name, "email": email, "password": PASSWORD},
    )


def _authed_client(build_client, email: str):
    """Return a TestClient signed in as a fresh user."""
    client = build_client()
    response = _signup(client, email)
    assert response.status_code == 201, response.text
    return client


# --------------------------------------------------------------------------
# creation / retrieval
# --------------------------------------------------------------------------


def test_create_plant_returns_full_configuration(client):
    _signup(client, "ada@example.com")
    response = client.post(PLANTS_PATH, json=_valid_payload())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True
    plant = body["data"]["plant"]
    assert plant["name"] == "Reactor Train A"
    assert plant["config"]["feed_flow_lpm"] == 120.0
    assert plant["state"]["temperature_c"] == 80.0
    assert plant["safety_limits"]["max_pressure_bar"] == 10.0
    assert plant["safeguards"]["trip_delay_s"] == 2
    # owner_id must never be exposed.
    assert "owner_id" not in plant
    assert "ownerId" not in plant


def test_create_plant_requires_auth(client):
    response = client.post(PLANTS_PATH, json=_valid_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_list_plants_returns_only_own(client):
    _signup(client, "ada@example.com")
    client.post(PLANTS_PATH, json=_valid_payload(name="Plant One"))
    client.post(PLANTS_PATH, json=_valid_payload(name="Plant Two"))

    response = client.get(PLANTS_PATH)
    assert response.status_code == 200
    plants = response.json()["data"]["plants"]
    assert len(plants) == 2
    assert {p["name"] for p in plants} == {"Plant One", "Plant Two"}


def test_list_plants_requires_auth(client):
    assert client.get(PLANTS_PATH).status_code == 401


def test_get_plant_detail_and_state(client):
    _signup(client, "ada@example.com")
    created = client.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]
    plant_id = created["id"]

    detail = client.get(f"{PLANTS_PATH}/{plant_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["plant"]["id"] == plant_id

    state = client.get(f"{PLANTS_PATH}/{plant_id}/state")
    assert state.status_code == 200
    state_body = state.json()["data"]
    assert state_body["plantId"] == plant_id
    assert state_body["state"]["level_pct"] == 45.0


def test_get_missing_plant_returns_404(client):
    _signup(client, "ada@example.com")
    assert client.get(f"{PLANTS_PATH}/does-not-exist").status_code == 404


# --------------------------------------------------------------------------
# update
# --------------------------------------------------------------------------


def test_update_plant_partial_fields(client):
    _signup(client, "ada@example.com")
    plant_id = client.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]["id"]

    response = client.patch(
        f"{PLANTS_PATH}/{plant_id}",
        json={"name": "Renamed", "config": {"feed_flow_lpm": 200.0}},
    )
    # A partial nested block is rejected wholesale (extra="forbid" + required fields).
    assert response.status_code == 422

    response = client.patch(
        f"{PLANTS_PATH}/{plant_id}",
        json={
            "name": "Renamed",
            "config": {
                "feed_flow_lpm": 200.0,
                "cooling_pct": 80.0,
                "valve_position_pct": 60.0,
                "heater_power_pct": 65.0,
                "shutdown_delay_s": 8,
            },
        },
    )
    assert response.status_code == 200, response.text
    plant = response.json()["data"]["plant"]
    assert plant["name"] == "Renamed"
    assert plant["config"]["feed_flow_lpm"] == 200.0
    assert plant["config"]["shutdown_delay_s"] == 8


def test_update_state_above_limits_is_rejected(client):
    _signup(client, "ada@example.com")
    plant_id = client.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]["id"]

    response = client.patch(
        f"{PLANTS_PATH}/{plant_id}",
        json={"state": {"pump_running": True, "temperature_c": 999.0, "pressure_bar": 4.0, "level_pct": 45.0}},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert any(d["field"] == "state.temperature_c" for d in body["error"]["details"])

    # The rejected update must not have persisted.
    detail = client.get(f"{PLANTS_PATH}/{plant_id}").json()["data"]["plant"]
    assert detail["state"]["temperature_c"] == 80.0


def test_delete_plant(client):
    _signup(client, "ada@example.com")
    plant_id = client.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]["id"]

    assert client.delete(f"{PLANTS_PATH}/{plant_id}").status_code == 204
    assert client.get(f"{PLANTS_PATH}/{plant_id}").status_code == 404
    assert client.get(f"{PLANTS_PATH}/{plant_id}/state").status_code == 404


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override",
    [
        pytest.param({"config": {**_valid_payload()["config"], "cooling_pct": 150.0}}, id="cooling>100"),
        pytest.param({"config": {**_valid_payload()["config"], "valve_position_pct": -5.0}}, id="valve<0"),
        pytest.param({"config": {**_valid_payload()["config"], "heater_power_pct": 101.0}}, id="heater>100"),
        pytest.param({"config": {**_valid_payload()["config"], "feed_flow_lpm": -1.0}}, id="flow<0"),
        pytest.param({"config": {**_valid_payload()["config"], "shutdown_delay_s": -1}}, id="delay<0"),
        pytest.param({"state": {**_valid_payload()["state"], "pressure_bar": -1.0}}, id="pressure<0"),
        pytest.param({"state": {**_valid_payload()["state"], "level_pct": 120.0}}, id="level>100"),
        pytest.param({"safety_limits": {**_valid_payload()["safety_limits"], "max_level_pct": 150.0}}, id="maxlevel>100"),
        pytest.param({"safeguards": {**_valid_payload()["safeguards"], "trip_delay_s": -3}}, id="tripdelay<0"),
        pytest.param({"name": ""}, id="empty-name"),
    ],
)
def test_create_plant_rejects_invalid_ranges(client, override):
    _signup(client, "ada@example.com")
    response = client.post(PLANTS_PATH, json=_valid_payload(**override))
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]


def test_create_plant_rejects_initial_state_above_limit(client):
    _signup(client, "ada@example.com")
    payload = _valid_payload(
        state={"pump_running": True, "temperature_c": 500.0, "pressure_bar": 4.0, "level_pct": 45.0}
    )
    response = client.post(PLANTS_PATH, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_plant_rejects_unknown_fields(client):
    _signup(client, "ada@example.com")
    payload = _valid_payload()
    payload["owner_id"] = "attacker-supplied-owner"  # must be ignored/rejected
    response = client.post(PLANTS_PATH, json=payload)
    assert response.status_code == 422


def test_validation_errors_do_not_echo_values(client):
    _signup(client, "ada@example.com")
    secret_marker = "leak-me-please-999"
    payload = _valid_payload(name=secret_marker * 40)  # too long
    response = client.post(PLANTS_PATH, json=payload)
    assert response.status_code == 422
    assert secret_marker not in response.text


# --------------------------------------------------------------------------
# ownership / IDOR
# --------------------------------------------------------------------------


def test_user_cannot_read_other_users_plant(build_client):
    user_a = _authed_client(build_client, "a@example.com")
    user_b = _authed_client(build_client, "b@example.com")

    plant_id = user_a.post(PLANTS_PATH, json=_valid_payload(name="A's plant")).json()["data"]["plant"]["id"]

    # A can read it.
    assert user_a.get(f"{PLANTS_PATH}/{plant_id}").status_code == 200
    # B cannot — 404 (existence not leaked), not 403.
    blocked = user_b.get(f"{PLANTS_PATH}/{plant_id}")
    assert blocked.status_code == 404
    # B's list stays empty.
    assert user_b.get(PLANTS_PATH).json()["data"]["plants"] == []
    # B cannot read the state either.
    assert user_b.get(f"{PLANTS_PATH}/{plant_id}/state").status_code == 404


def test_user_cannot_update_other_users_plant(build_client):
    user_a = _authed_client(build_client, "a@example.com")
    user_b = _authed_client(build_client, "b@example.com")

    plant_id = user_a.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]["id"]

    blocked = user_b.patch(f"{PLANTS_PATH}/{plant_id}", json={"name": "hijack"   })
    assert blocked.status_code == 404
    # A's plant is unchanged.
    assert user_a.get(f"{PLANTS_PATH}/{plant_id}").json()["data"]["plant"]["name"] == "Reactor Train A"


def test_user_cannot_delete_other_users_plant(build_client):
    user_a = _authed_client(build_client, "a@example.com")
    user_b = _authed_client(build_client, "b@example.com")

    plant_id = user_a.post(PLANTS_PATH, json=_valid_payload()).json()["data"]["plant"]["id"]

    assert user_b.delete(f"{PLANTS_PATH}/{plant_id}").status_code == 404
    assert user_a.get(f"{PLANTS_PATH}/{plant_id}").status_code == 200