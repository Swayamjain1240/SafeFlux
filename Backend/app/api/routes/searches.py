"""Authenticated deterministic search endpoints (Part 7).

    POST /api/v1/searches/run           run one bounded search over a plant
    GET  /api/v1/searches/capabilities  allowlisted variables, modes and budgets

Security posture:
- requires a verified session (``get_current_user``) and loads the plant with
  ``get_owned_or_404``, so another user's plant returns 404 and can never be
  searched (rule 5),
- request values only tighten the configured budgets; asking for more is a
  rejection rather than a silent clamp,
- the plan is validated *before* any compute, so an oversized search never starts,
- the endpoint has the tightest per-IP rate-limit bucket in the API, because one
  request runs many simulations (rule 8),
- responses follow the shared envelope and never leak internals or owner ids.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.rate_limit import search_rate_limit
from app.core.responses import FieldError, error_response, success_response
from app.database import get_db
from app.models import Plant, User
from app.schemas import SearchRunRequest
from app.schemas.search import resolve_request_limits
from app.search import (
    PlantProfile,
    SearchMode,
    capabilities,
    resolve_limits,
    run_search,
    versions,
)
from app.simulator import SimulationLimitError

logger = logging.getLogger("safeflux.searches")

router = APIRouter(prefix="/searches")


@router.get(
    "/capabilities",
    summary="List the allowlisted search variables, modes and effective budgets",
)
def search_capabilities(
    request: Request,
    user: User = Depends(get_current_user),
) -> dict:
    """Describe what a search may vary.

    Read-only and allowlist-driven: the UI renders its controls from this instead
    of hard-coding variable names, so a variable cannot become searchable by
    accident in the browser.
    """
    settings = request.app.state.settings
    return success_response(
        {
            "variables": capabilities()["variables"],
            "modes": [mode.value for mode in SearchMode],
            "limits": resolve_limits(settings).to_dict(),
            "versions": versions(),
        }
    )


@router.post(
    "/run",
    dependencies=[Depends(search_rate_limit)],
    summary="Run a bounded deterministic scenario search over one plant",
)
def run_search_endpoint(
    payload: SearchRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # Ownership is enforced before any compute happens (404 on cross-user).
    plant = get_owned_or_404(db, Plant, payload.plant_id, user)

    spec = payload.to_spec()
    settings = request.app.state.settings
    limits, errors = resolve_request_limits(settings, payload, spec)
    if errors:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "One or more input fields are invalid.",
            [FieldError(field=field, message=message) for field, message in errors],
        )

    profile = PlantProfile.from_plant(plant)
    try:
        run = run_search(profile=profile, spec=spec, limits=limits, settings=settings)
    except SimulationLimitError as exc:
        # Defensive: the plan was validated above, so any budget violation that
        # still reaches here is reported the same way rather than as a 500.
        return error_response(
            422,
            "VALIDATION_ERROR",
            "One or more input fields are invalid.",
            [FieldError(field=field, message=message) for field, message in exc.errors],
        )

    logger.info(
        "Search run: plant=%s user=%s mode=%s scenarios=%s status=%s",
        plant.id,
        user.id,
        spec.mode.value,
        run.result.counts.get("scenarios"),
        run.result.status,
    )
    return success_response(run.result.to_dict())
