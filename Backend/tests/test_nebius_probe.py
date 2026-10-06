"""The Part 8 operator probe, against a local fake catalogue (rules 22/23).

The probe is the one-command path for the real inference, so it is tested the way
it will run: the real ``NebiusProvider`` making real HTTP calls to an
OpenAI-compatible server on loopback, a real database, and the real simulator,
safety engine and search engine behind the tools. Only the *provider's responses*
are scripted — which is exactly what the live account will supply.

The fake server never sees a real secret and every test asserts the key cannot
appear in what the probe prints.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts import nebius_probe
from tests.ai_fakes import conclusion, decision

PASSWORD = "correct-horse-battery-staple"
SIGNUP_PATH = "/api/v1/auth/signup"
PLANTS_PATH = "/api/v1/plants"
FAKE_KEY = "probe-test-key-not-a-real-credential"

#: The catalogue the fake account "has": two Nemotron ids and one that is not.
CATALOGUE = [
    {"id": "nvidia/nemotron-3-nano-30b-a3b"},
    {"id": "nvidia/nemotron-3-super-120b-a12b"},
    {"id": "openai/gpt-oss-120b"},
]

MODEL_ID = "nvidia/nemotron-3-nano-30b-a3b"


class _FakeTokenFactory(BaseHTTPRequestHandler):
    """A minimal OpenAI-compatible server: ``/v1/models`` and chat completions."""

    replies: list[str] = []

    def log_message(self, *args):  # noqa: D102 - silence the default stderr spam
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.endswith("/models"):
            self._send(200, {"object": "list", "data": CATALOGUE})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if not self.path.endswith("/chat/completions"):
            self._send(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        text = type(self).replies.pop(0) if type(self).replies else "OK"
        self._send(
            200,
            {
                "model": MODEL_ID,
                "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 30},
            },
        )


@pytest.fixture
def fake_provider(monkeypatch):
    """Serve the fake catalogue on loopback and point settings at it.

    ``http://`` on a loopback host is the only non-https URL the provider accepts,
    so this also proves that rule rather than bypassing it.
    """
    _FakeTokenFactory.replies = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeTokenFactory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("NEBIUS_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setenv("NEBIUS_MODEL", MODEL_ID)
    try:
        yield _FakeTokenFactory
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


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
            "trip_delay_s": 30,
        },
    }


def _owned_plant(client, email: str) -> None:
    response = client.post(
        SIGNUP_PATH, json={"fullName": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    assert response.status_code == 201, response.text
    created = client.post(PLANTS_PATH, json=_plant_payload())
    assert created.status_code == 201, created.text


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def test_models_lists_only_the_nemotron_family(fake_provider, capsys):
    assert nebius_probe.main(["models"]) == 0
    out = capsys.readouterr().out

    assert "nvidia/nemotron-3-nano-30b-a3b" in out
    assert "nvidia/nemotron-3-super-120b-a12b" in out
    assert "openai/gpt-oss-120b" not in out  # not a candidate for this project
    assert FAKE_KEY not in out


def test_models_without_configuration_explains_instead_of_calling_out(capsys):
    # No NEBIUS_* in the environment: the probe must refuse before any request.
    assert nebius_probe.main(["models"]) == 2
    assert "not configured" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def test_check_reports_the_model_and_never_the_key(fake_provider, capsys):
    fake_provider.replies = ["OK"]
    assert nebius_probe.main(["check"]) == 0
    out = capsys.readouterr().out

    assert f"model={MODEL_ID}" in out
    assert "latency_ms=" in out
    assert FAKE_KEY not in out
    assert "Authorization" not in out


def test_check_without_a_model_is_a_clear_failure(monkeypatch, capsys):
    monkeypatch.setenv("NEBIUS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
    monkeypatch.delenv("NEBIUS_MODEL", raising=False)
    assert nebius_probe.main(["check"]) == 2
    assert "must all be set" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# investigate
# ---------------------------------------------------------------------------


def test_investigate_runs_one_real_round_trip_through_the_provider(build_client, fake_provider, capsys):
    client = build_client()
    _owned_plant(client, "ada@example.com")
    fake_provider.replies = [
        decision(
            "run_scenario_search",
            variables=["cooling_factor"],
            arguments={"variable": "cooling_factor", "steps": 9, "refine": True, "duration_s": 600},
        ),
        decision("check_safeguards", arguments={"delay_s": 120}),
        decision("conclude", focus="cooling boundary"),
        conclusion(headline="Cooling boundary found"),
    ]

    assert nebius_probe.main(["investigate", "--email", "ada@example.com"]) == 0
    out = capsys.readouterr().out

    assert "status=complete" in out
    assert f"model={MODEL_ID}" in out
    assert "focus=cooling boundary" in out
    assert "run_scenario_search" in out and "check_safeguards" in out
    assert "headline: Cooling boundary found" in out
    assert FAKE_KEY not in out
    assert "Bearer" not in out


def test_investigate_refuses_an_account_that_does_not_exist(fake_provider, capsys):
    assert nebius_probe.main(["investigate", "--email", "nobody@example.com"]) == 2
    assert "no account with email" in capsys.readouterr().err


def test_investigate_reports_when_no_provider_is_configured(build_client, capsys):
    client = build_client()
    _owned_plant(client, "ada@example.com")

    assert nebius_probe.main(["investigate", "--email", "ada@example.com"]) == 1
    out = capsys.readouterr().out

    assert "status=not_configured" in out
    assert "the model was not contacted" in out
