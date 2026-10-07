"""Analysis endpoint coverage (Part 9, rule 23).

HTTP-level tests over the *real* simulator and safety engine — no fake runner,
no fake events. The suite walks the task's full path (create → receive events →
detect the seeded failure → view failure → counterfactuals → safeguards →
reverify → history → report) and then proves the security posture: object-level
404s across every resource (rule 5), the 409 duplicate guard, the per-user rate
limit, strict schemas and sanitized storage.
"""

from __future__ import annotations

SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"
RUN_PATH = "/api/v1/analyses/run"
LIST_PATH = "/api/v1/analyses"

PASSWORD = "correct-horse-battery-staple"

GOAL = "Increase production throughput by 30%"


def _plant_payload(**overrides) -> dict:
    """The seeded plant: low cooling with a long trip delay is unsafe."""
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


def _run_analysis(client, plant_id: str, goal: str = GOAL):
    response = client.post(RUN_PATH, json={"plant_id": plant_id, "goal": goal})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _calm_plant_payload(**overrides) -> dict:
    """A plant whose every sweep corner stays inside the limits (probe-verified)."""
    payload = _plant_payload(
        config={
            "feed_flow_lpm": 60.0,
            "cooling_pct": 100.0,
            "valve_position_pct": 50.0,
            "heater_power_pct": 0.0,
            "shutdown_delay_s": 5,
        },
        state={
            "pump_running": False,
            "temperature_c": 40.0,
            "pressure_bar": 1.5,
            "level_pct": 40.0,
        },
    )
    payload.update(overrides)
    return payload


def test_run_requires_authentication(client):
    response = client.post(RUN_PATH, json={"plant_id": "x", "goal": "y"})
    assert response.status_code == 401, response.text
    assert response.json()["success"] is False


def test_run_rejects_unknown_fields(client, build_client):
    c = _authed_client(build_client, "strict9@example.com")
    response = c.post(
        RUN_PATH,
        json={"plant_id": "x", "goal": "y", "surprise": True},
    )
    assert response.status_code == 422, response.text


def test_run_rejects_other_users_plant(build_client):
    owner = _authed_client(build_client, "owner9@example.com")
    plant_id = _create_plant(owner)
    stranger = _authed_client(build_client, "stranger9@example.com")
    response = stranger.post(RUN_PATH, json={"plant_id": plant_id, "goal": GOAL})
    assert response.status_code == 404, response.text


def test_full_workflow_from_goal_to_report(build_client):
    """The task's whole path, over the real simulator, in one test."""
    c = _authed_client(build_client, "flow9@example.com")
    plant_id = _create_plant(c)

    data = _run_analysis(c, plant_id)
    assert data["status"] == "complete"
    assert data["has_result"] is True
    analysis_id = data["id"]

    # --- events: the real pipeline, in order, with measured elapsed times ---
    events_response = c.get(f"{LIST_PATH}/{analysis_id}/events")
    assert events_response.status_code == 200, events_response.text
    events = events_response.json()["data"]["events"]
    kinds = [event["kind"] for event in events]
    assert "understanding_change" in kinds
    assert "mapping_equipment" in kinds
    assert "planning" in kinds
    assert "running_scenario" in kinds
    assert "observing_result" in kinds
    assert "finding_violation" in kinds
    assert "running_counterfactual" in kinds
    assert "checking_safeguard" in kinds
    seqs = [event["seq"] for event in events]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    elapsed = [event["elapsed_ms"] for event in events]
    assert all(isinstance(value, int) and value >= 0 for value in elapsed)

    # --- the seeded unsafe region was found by the real search --------------
    result_response = c.get(f"{LIST_PATH}/{analysis_id}/result")
    assert result_response.status_code == 200
    result = result_response.json()["data"]["result"]
    failures = result["failures"]
    assert failures, "the seeded unsafe region must be discovered"
    pivot = result["pivot"]
    assert pivot["status"] in ("violation", "safeguard_activated")
    assert pivot["peaks"]["temperature_c"] is not None

    # --- counterfactuals ran real simulations -------------------------------
    counterfactuals = result["counterfactuals"]
    assert counterfactuals, "restore-style comparisons must exist for a pivot"
    for row in counterfactuals:
        assert row["status"] in ("safe", "near_limit", "safeguard_activated", "violation")
        assert row["changes"], "before/after peaks recorded"

    # --- safeguard timing came from a real re-simulation --------------------
    timings = result["safeguards"]["timings"]
    assert timings, "the armed shutdown must be evaluated"
    for timing in timings:
        assert set(timing) >= {"safeguard", "trigger_time_s", "response_time_s", "violation_time_s"}
    assert "not the behaviour of a real plant" in result["safeguards"]["note"]

    # --- failure detail page evidence ---------------------------------------
    failure_id = failures[0]["key"]
    failure_response = c.get(f"{LIST_PATH}/{analysis_id}/failures/{failure_id}")
    assert failure_response.status_code == 200, failure_response.text
    detail = failure_response.json()["data"]
    assert detail["scenario"]["values"]
    assert detail["series"]["time_s"], "trajectories come from the real simulator"
    assert detail["configured_limits"]["max_temperature_c"] == 150.0
    assert detail["first_violation"] is not None
    assert detail["peaks"]["temperature_c"] is not None

    # --- unknown failure id is a 404, not a guess ---------------------------
    missing = c.get(f"{LIST_PATH}/{analysis_id}/failures/does-not-exist")
    assert missing.status_code == 404

    # --- history: paginated, contains the run -------------------------------
    history = c.get(f"{LIST_PATH}?page=1&page_size=10")
    assert history.status_code == 200
    body = history.json()["data"]
    assert body["total"] >= 1
    assert any(item["id"] == analysis_id for item in body["items"])

    # --- report payload and PDF ---------------------------------------------
    report = c.get(f"{LIST_PATH}/{analysis_id}/report")
    assert report.status_code == 200
    tabs = report.json()["data"]["tabs"]
    assert set(tabs) >= {
        "overview",
        "scenarios",
        "failures",
        "counterfactuals",
        "safeguards",
        "evidence",
    }
    pdf = c.get(f"{LIST_PATH}/{analysis_id}/report.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")


def test_no_failure_result_still_completes_with_required_language(build_client):
    """A benign plant finishes cleanly and uses the exact required sentence."""
    c = _authed_client(build_client, "calm9@example.com")
    response = c.post(PLANTS_PATH, json=_calm_plant_payload())
    assert response.status_code == 201, response.text
    plant_id = response.json()["data"]["plant"]["id"]

    data = _run_analysis(c, plant_id)
    assert data["status"] == "complete"
    result = c.get(f"{LIST_PATH}/{data['id']}/result").json()["data"]["result"]
    assert result["failures"] == []
    assert result["pivot"] is None
    assert result["counterfactuals"] == []
    notes = " ".join(result["notes"])
    assert "No unsafe condition was detected within the tested simulation scenarios." in notes


def test_ai_not_configured_note_is_explicit(build_client):
    c = _authed_client(build_client, "noai9@example.com")
    plant_id = _create_plant(c)
    data = _run_analysis(c, plant_id)
    result = c.get(f"{LIST_PATH}/{data['id']}/result").json()["data"]["result"]
    assert result["ai_explanation"] is None
    assert any("No AI provider is configured" in note for note in result["notes"])


def test_duplicate_submission_is_conflicted_not_double_run(build_client):
    """A second concurrent run on the same plant is a 409 (prevent duplicates)."""
    import threading

    c = _authed_client(build_client, "dup9@example.com")
    plant_id = _create_plant(c)

    results: list[int] = []
    start = threading.Barrier(2)

    def worker():
        start.wait()
        response = c.post(RUN_PATH, json={"plant_id": plant_id, "goal": GOAL})
        results.append(response.status_code)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200, 409], results


def test_session_expiry_blocks_analysis(build_client):
    c = _authed_client(build_client, "expired9@example.com")
    plant_id = _create_plant(c)
    c.cookies.clear()
    response = c.post(RUN_PATH, json={"plant_id": plant_id, "goal": GOAL})
    assert response.status_code == 401


def test_reverify_requires_failing_parent(build_client):
    c = _authed_client(build_client, "reverify-calm9@example.com")
    response = c.post(PLANTS_PATH, json=_calm_plant_payload())
    assert response.status_code == 201
    plant_id = response.json()["data"]["plant"]["id"]
    data = _run_analysis(c, plant_id)
    response = c.post(
        f"{LIST_PATH}/{data['id']}/reverify",
        json={"mitigations": {"cooling_factor": 1.0}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NOTHING_TO_VERIFY"


def test_reverify_runs_affected_scenarios_and_stores_comparison(build_client):
    c = _authed_client(build_client, "reverify9@example.com")
    plant_id = _create_plant(c)
    data = _run_analysis(c, plant_id)
    analysis_id = data["id"]

    response = c.post(
        f"{LIST_PATH}/{analysis_id}/reverify",
        json={
            "mitigations": {
                "cooling_capacity_pct": 120.0,
                "shutdown_delay_s": 2.0,
                "operating_target_pct": 40.0,
            }
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    document = body["result"]
    assert document["kind"] == "reverify"
    assert document["parent_id"] == analysis_id
    comparison = document["comparison"]
    assert comparison["scenarios_retested"] >= 1
    assert "failing_before" in comparison and "failing_after" in comparison
    rows = document["rows"]
    assert rows and all("status_before" in row and "status_after" in row for row in rows)
    assert document["verdict"] in (
        "No unsafe condition was detected within the tested simulation scenarios.",
        "Unsafe conditions were detected within the tested simulation scenarios; the "
        "listed failures are the evidence.",
    )
    # The comparison is stored as its own history row (kind=reverify).
    history = c.get(f"{LIST_PATH}?kind=reverify").json()["data"]
    assert any(item["id"] == body["id"] for item in history["items"])


def test_reverify_rejects_unknown_and_out_of_range_mitigations(build_client):
    c = _authed_client(build_client, "reverify-bad9@example.com")
    plant_id = _create_plant(c)
    data = _run_analysis(c, plant_id)
    url = f"{LIST_PATH}/{data['id']}/reverify"
    response = c.post(url, json={"mitigations": {"banana": 1.0}})
    assert response.status_code == 422
    response = c.post(url, json={"mitigations": {"cooling_factor": 99.0}})
    assert response.status_code == 422


# --------------------------------------------------------------------------
# IDOR: every object must 404 across users (rule 5).
# --------------------------------------------------------------------------


def test_idor_every_object_is_invisible_across_users(build_client):
    owner = _authed_client(build_client, "idor-owner9@example.com")
    plant_id = _create_plant(owner)
    data = _run_analysis(owner, plant_id)
    analysis_id = data["id"]

    result = owner.get(f"{LIST_PATH}/{analysis_id}/result").json()["data"]["result"]
    failure_id = result["failures"][0]["key"] if result["failures"] else "none"
    # A reverify row owned by the same user.
    reverify = owner.post(
        f"{LIST_PATH}/{analysis_id}/reverify",
        json={"mitigations": {"cooling_factor": 1.0}},
    )
    assert reverify.status_code == 200, reverify.text
    reverify_id = reverify.json()["data"]["id"]

    stranger = _authed_client(build_client, "idor-stranger9@example.com")
    for path in (
        f"{LIST_PATH}/{analysis_id}",
        f"{LIST_PATH}/{analysis_id}/events",
        f"{LIST_PATH}/{analysis_id}/result",
        f"{LIST_PATH}/{analysis_id}/failures/{failure_id}",
        f"{LIST_PATH}/{analysis_id}/report",
        f"{LIST_PATH}/{analysis_id}/report.pdf",
        f"{LIST_PATH}/{reverify_id}",
    ):
        response = stranger.get(path)
        assert response.status_code == 404, (path, response.status_code)
    response = stranger.post(
        f"{LIST_PATH}/{analysis_id}/reverify", json={"mitigations": {"cooling_factor": 1.0}}
    )
    assert response.status_code == 404


def test_history_is_scoped_to_owner_only(build_client):
    a = _authed_client(build_client, "hist-a9@example.com")
    b = _authed_client(build_client, "hist-b9@example.com")
    plant_a = _create_plant(a)
    _run_analysis(a, plant_a)
    rows_a = a.get(LIST_PATH).json()["data"]["items"]
    assert rows_a
    rows_b = b.get(LIST_PATH).json()["data"]["items"]
    assert rows_b == []
    assert all(item["id"] not in {row["id"] for row in rows_a} for row in rows_b)


# --------------------------------------------------------------------------
# Rate limit (rule 8) and sanitization (rules 6/7).
# --------------------------------------------------------------------------


def test_analysis_rate_limit_is_per_user(build_client):
    from app.core.config import get_settings

    c1 = _authed_client(build_client, "rl-a9@example.com")
    c2 = _authed_client(build_client, "rl-b9@example.com")
    plant1 = _create_plant(c1)
    plant2 = _create_plant(c2)
    limit = get_settings().ANALYSIS_RATE_LIMIT_RUNS
    statuses: list[int] = []
    for _ in range(limit + 2):
        response = c1.post(RUN_PATH, json={"plant_id": plant1, "goal": GOAL})
        statuses.append(response.status_code)
    assert 429 in statuses
    # The other user's budget is untouched.
    response = c2.post(RUN_PATH, json={"plant_id": plant2, "goal": GOAL})
    assert response.status_code == 200, response.text


def test_goal_is_sanitized_before_storage(build_client):
    c = _authed_client(build_client, "san9@example.com")
    plant_id = _create_plant(c)
    response = c.post(
        RUN_PATH,
        json={"plant_id": plant_id, "goal": "  increase   throughput\n\nby 30%  "},
    )
    assert response.status_code == 200
    stored = response.json()["data"]["goal"]
    assert stored == stored.strip()
    assert "\n" not in stored
    assert "increase throughput by 30%" in stored.lower()
