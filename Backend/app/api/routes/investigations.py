"""Authenticated AI investigation endpoints (Part 8).

    GET  /api/v1/investigations/capabilities  provider, tools, bounds, allowlist
    POST /api/v1/investigations/run           one bounded investigation

Security posture:
- requires a verified session; the plant is loaded with ``get_owned_or_404``, so
  another user's plant returns **404** and can never be investigated (rule 5),
- budgeted per authenticated **user** (not per IP), because this is the only
  endpoint that can spend provider money and tokens,
- a repeated click cannot start a second run: the in-flight guard answers **409**
  for the same ``(user, plant)`` while a run is executing,
- the provider is optional configuration: with no key the endpoint answers a clear
  ``not_configured`` document instead of failing, and Parts 1–7 keep working,
- everything the model does goes through the allowlisted tool layer, which
  re-validates arguments, ownership and cost by itself,
- logging is allowlisted (provider, model, analysis id, latency, error category) —
  never a key, a token, the prompt or the engineer's text.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.ai import (
    AGENT_VERSION,
    PROVIDER_NAME,
    TOOL_NAMES,
    AgentLimits,
    DuplicateRunError,
    InvestigationService,
    tool_catalog,
)
from app.ai.deps import get_ai_service
from app.ai.security import log_event
from app.ai.service import prepare_goal
from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.rate_limit import ai_rate_limit
from app.core.responses import error_response, success_response
from app.database import get_db
from app.models import Plant, User
from app.schemas import InvestigationRunRequest
from app.search import capabilities as search_capabilities
from app.search import versions as search_versions

logger = logging.getLogger("safeflux.investigations")

router = APIRouter(prefix="/investigations")


@router.get(
    "/capabilities",
    summary="Describe the AI investigation: provider state, tools, allowlist and bounds",
)
def investigation_capabilities(
    request: Request,
    user: User = Depends(get_current_user),
    service: InvestigationService = Depends(get_ai_service),
) -> dict:
    """Read-only description of what an investigation may do.

    ``configured`` reports only whether the three provider variables are present —
    never their values — so the UI can explain the state without a key ever
    reaching the browser.
    """
    settings = request.app.state.settings
    limits = AgentLimits.from_settings(settings)
    model_id = (getattr(settings, "NEBIUS_MODEL", None) or "") if settings.ai_configured else ""
    return success_response(
        {
            "provider": PROVIDER_NAME,
            "configured": bool(settings.ai_configured),
            "model_id": model_id,
            "tools": tool_catalog(),
            "tool_names": list(TOOL_NAMES),
            "budgets": limits.to_dict(),
            "variables": search_capabilities()["variables"],
            "versions": {**search_versions(), "agent_version": AGENT_VERSION},
            "ai_never": [
                "creates process values",
                "sets or relaxes safety limits",
                "produces safety verdicts",
                "executes shell, Python, SQL or generated code",
                "reads files or secrets",
                "changes permissions or budgets",
                "controls real equipment",
            ],
        }
    )


@router.post(
    "/run",
    dependencies=[Depends(ai_rate_limit)],
    summary="Run one bounded AI-assisted investigation over one owned plant",
)
def run_investigation_endpoint(
    payload: InvestigationRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: InvestigationService = Depends(get_ai_service),
) -> dict:
    # Ownership first: nothing is planned, simulated or sent to a provider for a
    # plant the caller does not own (404, never 403).
    plant = get_owned_or_404(db, Plant, payload.plant_id, user)

    goal = prepare_goal(payload.goal)
    try:
        with service.guard.claim(str(user.id), str(plant.id)):
            result = service.run(
                db=db,
                user=user,
                plant=plant,
                settings=request.app.state.settings,
                goal=goal,
                telemetry=getattr(request.app.state, "telemetry", None),
            )
    except DuplicateRunError:
        log_event(
            logger,
            "ai.duplicate_run",
            plant_id=str(plant.id),
            user_id=str(user.id),
            status="conflict",
        )
        return error_response(
            409,
            "CONFLICT",
            "An investigation for this plant is already running. Wait for it to finish.",
        )

    log_event(
        logger,
        "ai.run",
        provider=result.get("provider"),
        model_id=result.get("model_id"),
        plant_id=str(plant.id),
        user_id=str(user.id),
        status=result.get("status"),
        stop_reason=(result.get("budget") or {}).get("stop_reason"),
        model_calls=(result.get("budget") or {}).get("model_calls_used"),
        simulations=(result.get("budget") or {}).get("simulations_used"),
        tokens=(result.get("budget") or {}).get("tokens_used"),
        duration_s=(result.get("budget") or {}).get("elapsed_s"),
        scenario_id=result.get("analysis_id"),
    )
    return success_response(result)
