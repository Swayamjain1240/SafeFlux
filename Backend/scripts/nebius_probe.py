"""Operator probe for the Part 8 Nebius step.

Three jobs, in the order the real inference needs them:

    models        list the Nemotron-family ids this *account* can actually call,
                  so NEBIUS_MODEL is resolved from the catalogue, never guessed
    check         one tiny real completion, proving key + base URL + model work
    investigate   one controlled investigation for an owned plant, summarising
                  the evidence the deterministic layers produced

Security properties:

- the key is read only from validated Settings (``Backend/.env``), is passed only
  in the ``Authorization`` header, and is never printed, logged or returned,
- the model is never executed against anything but the allowlisted tool layer:
  an investigation runs the same ``InvestigationService`` the API endpoint runs,
  with ownership resolved from the database, not from a flag,
- no shell, no eval, no arbitrary code — this file only speaks HTTP to the
  configured provider and calls app code.

Run from ``Backend/`` (so ``.env`` and the ``app`` package resolve):

    python -m scripts.nebius_probe models
    python -m scripts.nebius_probe check
    python -m scripts.nebius_probe investigate --email you@example.com
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

from app.ai.provider import ProviderConfig, ProviderError, build_provider, validate_base_url
from app.core.config import get_settings

#: The only family this project is allowed to pick a model id from.
_MODEL_FILTER = "nemotron"


def _api_key(settings: Any) -> str | None:
    """Unwrap the SecretStr once, here, and never print it."""
    raw = getattr(settings, "NEBIUS_API_KEY", None)
    return raw.get_secret_value() if hasattr(raw, "get_secret_value") else None


def _catalogue_url(base_url: str | None) -> str | None:
    validated = validate_base_url(base_url)
    return f"{validated.rstrip('/')}/models" if validated else None


def cmd_models(_args: argparse.Namespace) -> int:
    """List the catalogue and print the Nemotron-family candidates."""
    settings = get_settings()
    url = _catalogue_url(getattr(settings, "NEBIUS_BASE_URL", None))
    key = _api_key(settings)
    if not url or not key:
        print(
            "not configured: set NEBIUS_API_KEY and NEBIUS_BASE_URL in Backend/.env",
            file=sys.stderr,
        )
        return 2
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        print(f"catalogue request failed: {type(exc).__name__}", file=sys.stderr)
        return 2
    if response.status_code != 200:
        # Status only: the body may echo request context, so it is never printed.
        print(f"catalogue request failed: HTTP {response.status_code}", file=sys.stderr)
        return 2

    entries = response.json().get("data") if isinstance(response.json(), dict) else None
    ids = sorted(
        str(item.get("id"))
        for item in (entries or [])
        if isinstance(item, dict) and item.get("id")
    )
    family = [model_id for model_id in ids if _MODEL_FILTER in model_id.lower()]
    if family:
        print(f"Nemotron-family models available to this account ({len(family)}):")
        for model_id in family:
            print(f"  {model_id}")
        print("Pick one, put it in NEBIUS_MODEL, then run: python -m scripts.nebius_probe check")
    else:
        print(f"No '{_MODEL_FILTER}' model found in this account's catalogue.")
        print("All visible model ids:")
        for model_id in ids:
            print(f"  {model_id}")
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    """One tiny real completion with the configured model."""
    config = ProviderConfig.from_settings(get_settings())
    if not config.configured:
        print(
            "not configured: NEBIUS_API_KEY, NEBIUS_BASE_URL and NEBIUS_MODEL must all be set",
            file=sys.stderr,
        )
        return 2
    try:
        response = build_provider(config).complete(
            system="You are a connectivity probe. Answer with exactly: OK",
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            max_output_tokens=8,
        )
    except ProviderError as exc:
        # to_dict() is the log-safe vocabulary; the key is never in it.
        print(f"provider error: {exc.to_dict()}", file=sys.stderr)
        return 2
    print(
        f"model={response.model} latency_ms={response.latency_ms} "
        f"attempts={response.attempts} tokens={response.tokens}"
    )
    print(f"excerpt={response.text[:80]!r}")
    return 0


def cmd_investigate(args: argparse.Namespace) -> int:
    """One controlled investigation for a plant the named account owns."""
    from app.ai.service import InvestigationService, prepare_goal
    from app.database import get_session_factory
    from app.models import Plant, User

    session_factory = get_session_factory()
    with session_factory() as db:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            print(f"no account with email {args.email}", file=sys.stderr)
            return 2
        query = db.query(Plant).filter(Plant.owner_id == str(user.id))
        if args.plant_id:
            query = query.filter(Plant.id == args.plant_id)
        plant = query.first()
        if plant is None:
            print("no plant owned by that account", file=sys.stderr)
            return 2

        result = InvestigationService().run(
            db=db,
            user=user,
            plant=plant,
            settings=get_settings(),
            goal=prepare_goal(args.goal),
        )
    return _print_investigation(result, as_json=args.json)


def _print_investigation(result: dict[str, Any], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("status") == "complete" else 1

    budget = result.get("budget") or {}
    print(
        f"analysis_id={result.get('analysis_id')} status={result.get('status')} "
        f"model={result.get('model_id') or '(none)'}"
    )
    if result.get("focus"):
        print(f"focus={result.get('focus')}")
    print(
        "steps={steps_used}/{max_steps} model_calls={model_calls_used}/{max_model_calls} "
        "simulations={simulations_used}/{max_simulations} tokens={tokens_used}/{max_tokens}".format(
            **{**{key: "?" for key in (
                "steps_used", "max_steps", "model_calls_used", "max_model_calls",
                "simulations_used", "max_simulations", "tokens_used", "max_tokens",
            )}, **budget}
        )
    )
    evidence = [row for row in result.get("evidence") or [] if isinstance(row, dict)]
    tools = sorted({str(row.get("tool")) for row in evidence if row.get("tool")})
    print(f"evidence={len(evidence)} tools={tools}")
    print(
        f"failures={len(result.get('failures') or [])} "
        f"boundaries={len(result.get('boundaries') or [])}"
    )
    for note in result.get("notes") or []:
        print(f"note: {note}")
    explanation = result.get("explanation") or {}
    if isinstance(explanation, dict) and explanation.get("headline"):
        print(f"headline: {explanation.get('headline')}")
    if not result.get("ai_involved"):
        print("the model was not contacted (provider not configured, or the run stopped early)")
    return 0 if result.get("status") == "complete" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nebius_probe",
        description="Resolve the account's Nemotron model, verify it, then run one investigation.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("models", help="list Nemotron-family models this account can call")
    commands.add_parser("check", help="one tiny real completion with the configured model")
    investigate = commands.add_parser(
        "investigate", help="one controlled investigation for an owned plant"
    )
    investigate.add_argument("--email", required=True, help="the account that owns the plant")
    investigate.add_argument("--plant-id", default=None, help="optional plant id (else first owned)")
    investigate.add_argument("--goal", default=None, help="optional engineering-change text")
    investigate.add_argument("--json", action="store_true", help="print the full result document")
    args = parser.parse_args(argv)
    return {"models": cmd_models, "check": cmd_check, "investigate": cmd_investigate}[
        args.command
    ](args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
