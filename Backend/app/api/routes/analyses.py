"""Authenticated analysis endpoints (Part 9).

    POST /api/v1/analyses/run                     one autonomous analysis (goal → events → document)
    GET  /api/v1/analyses                         paginated history for the session user
    GET  /api/v1/analyses/{analysis_id}           one stored analysis (metadata + counts)
    GET  /api/v1/analyses/{analysis_id}/events    real pipeline events (?after_seq= cursor)
    GET  /api/v1/analyses/{analysis_id}/result    the stored evidence document
    GET  /api/v1/analyses/{analysis_id}/failures/{failure_id}   one failure's full evidence
    POST /api/v1/analyses/{analysis_id}/reverify  re-run the failing cases under mitigations
    GET  /api/v1/analyses/{analysis_id}/report    interactive-report payload (tabs read this)
    GET  /api/v1/analyses/{analysis_id}/report.pdf  the same report as a multi-page PDF

Security posture:
- every id is resolved through ``get_owned_or_404``: another user's analysis,
  failure, scenario, history item, report or reverification is a **404** (rule 5),
- creation is budgeted per authenticated user (rule 8) and a repeated click
  cannot run two analyses at once on one plant (409),
- goal text is sanitized before storage and never echoed raw (rules 6/7),
- the reverify mitigation set is allowlisted and bounded before any simulation,
- responses follow the shared envelope and never leak owner ids or internals.
"""

from __future__ import annotations

import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analyses.constants import (
    ANALYSIS_DISCLAIMER,
    NO_UNSAFE_DETECTED_NOTE,
    SAFEGUARD_LANGUAGE_NOTE,
    UNSAFE_DETECTED_NOTE,
)
from app.analyses.events import EventRecorder
from app.analyses.pipeline import (
    MITIGATION_BOUNDS,
    apply_mitigations_to_case,
    bounded_series,
    build_reverify_document,
    failure_detail,
    locate_failure,
)
from app.analyses.pdf import render_report_pdf
from app.analyses.service import AnalysisService, mark_failed_status
from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.rate_limit import analysis_rate_limit
from app.core.responses import error_response, success_response
from app.database import get_db
from app.models import Analysis, AnalysisEvent, Plant, User
from app.schemas.analysis import AnalysisRunRequest, ReverifyRequest
from app.search import SearchVariable, make_case
from app.search.variables import spec_for

logger = logging.getLogger("safeflux.analyses")

router = APIRouter(prefix="/analyses")

#: History page bounds (rule 25: no endless page).
MAX_PAGE_SIZE = 50


def _service(request: Request) -> AnalysisService:
    service = getattr(request.app.state, "analysis_service", None)
    if service is None:
        service = AnalysisService()
        request.app.state.analysis_service = service
    return service


def _owned_analysis(db: Session, analysis_id: str, user: User) -> Analysis:
    return get_owned_or_404(db, Analysis, analysis_id, user)


@router.post(
    "/run",
    dependencies=[Depends(analysis_rate_limit)],
    summary="Run one autonomous analysis over one owned plant",
)
def run_analysis_endpoint(
    payload: AnalysisRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plant = get_owned_or_404(db, Plant, payload.plant_id, user)
    service = _service(request)

    from app.ai.guards import DuplicateRunError

    try:
        analysis_id = service.run(
            db=db,
            user=user,
            plant=plant,
            settings=request.app.state.settings,
            goal=payload.goal,
        )
    except DuplicateRunError:
        return error_response(
            409,
            "CONFLICT",
            "An analysis for this plant is already running. Wait for it to finish.",
        )
    except Exception:
        # The service marked the row failed *inside* the same transaction that
        # the exception rolled back; re-record the real failure on a fresh
        # transaction so the history shows the truth (rules 9/12).
        db.rollback()
        failed_id = getattr(service, "last_failed_id", None)
        if failed_id:
            mark_failed_status(db, failed_id, "failed", error="The analysis run raised an error.")
        logger.exception("Analysis run failed")
        return error_response(500, "INTERNAL_ERROR", "The analysis could not be completed.")

    analysis = db.get(Analysis, analysis_id)
    db.refresh(analysis)
    return success_response(_analysis_out(analysis))


@router.get("", summary="Paginated analysis history for the session user")
def list_analyses_endpoint(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=10, ge=1, le=MAX_PAGE_SIZE),
    kind: str | None = Query(default=None, pattern="^(auto|counterfactual|reverify)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(Analysis).where(Analysis.owner_id == user.id)
    if kind:
        stmt = stmt.where(Analysis.kind == kind)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = db.execute(
        stmt.order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return success_response(
        {
            "items": [_history_out(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "pages": max(1, math.ceil(int(total) / page_size)),
        }
    )


@router.get("/{analysis_id}", summary="One stored analysis (metadata and headline counts)")
def get_analysis_endpoint(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    return success_response(_analysis_out(analysis))


@router.get("/{analysis_id}/events", summary="The real pipeline events, newest after a cursor")
def get_events_endpoint(
    analysis_id: str,
    after_seq: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    stmt = (
        select(AnalysisEvent)
        .where(AnalysisEvent.analysis_id == analysis.id)
        .where(AnalysisEvent.seq > after_seq)
        .order_by(AnalysisEvent.seq.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return success_response(
        {
            "status": analysis.status,
            "events": [row.to_dict() for row in rows],
            "last_seq": rows[-1].seq if rows else after_seq,
        }
    )


@router.get("/{analysis_id}/result", summary="The stored evidence document of a completed analysis")
def get_result_endpoint(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    if analysis.result is None:
        return error_response(
            409,
            "NOT_READY",
            "This analysis has no stored result yet.",
        )
    return success_response({"status": analysis.status, "result": analysis.result})


@router.get("/{analysis_id}/failures/{failure_id}", summary="One failure's full evidence page")
def get_failure_endpoint(
    analysis_id: str,
    failure_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    if analysis.result is None:
        return error_response(409, "NOT_READY", "This analysis has no stored result yet.")
    failure = locate_failure(analysis.result, failure_id)
    if failure is None:
        return error_response(404, "NOT_FOUND", "That failure is not part of this analysis.")
    from app.safety import assess_scenario
    from app.search.evaluate import ScenarioEvaluator
    from app.search.budgets import SearchBudget
    from app.search import resolve_limits, SearchMode, SearchSpec
    from app.search.spec import ScenarioPlan

    profile = _profile_of(analysis, db)
    settings = _settings_of(db)
    spec = SearchSpec(
        mode=SearchMode.SWEEP,
        plan=ScenarioPlan(duration_s=600.0, time_step_s=1.0, start_s=0.0, label="failure-detail"),
        axes=(),
        refine=False,
    )
    evaluator = ScenarioEvaluator(
        profile=profile,
        spec=spec,
        thresholds=_thresholds_of(profile, settings),
        limits=_sim_limits_of(settings),
        budget=SearchBudget(limits=resolve_limits(settings)),
    )
    values = failure.get("values") or {}
    mapping = {SearchVariable(k): float(v) for k, v in values.items()}
    case = make_case(mapping, label="failure-detail")
    _assessment, result = assess_scenario(
        evaluator.build_input(case), evaluator.thresholds, scenario_id="failure-detail"
    )
    from app.safety.safeguards import evaluate_safeguards

    timings = [
        timing.to_dict()
        for timing in evaluate_safeguards(result, evaluator.thresholds, profile.safeguards)
    ]
    detail = failure_detail(
        analysis_id=analysis.id,
        failure=failure,
        original=analysis.result,
        series=bounded_series(result),
        safeguards=timings,
    )
    return success_response(detail)


@router.post(
    "/{analysis_id}/reverify",
    dependencies=[Depends(analysis_rate_limit)],
    summary="Re-run the affected failing scenarios under engineer mitigations",
)
def reverify_endpoint(
    analysis_id: str,
    payload: ReverifyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    if analysis.result is None:
        return error_response(409, "NOT_READY", "This analysis has no stored result yet.")
    parent_result = analysis.result or {}
    failures = parent_result.get("failures") or []
    if not failures:
        return error_response(
            422,
            "NOTHING_TO_VERIFY",
            "The parent analysis found no failing scenarios, so there is nothing to re-verify.",
        )
    for key in payload.mitigations:
        if key not in MITIGATION_BOUNDS:
            return error_response(
                422,
                "VALIDATION_ERROR",
                f"Unknown mitigation '{key}'.",
            )

    from app.safety import assess_scenario
    from app.search.budgets import SearchBudget
    from app.search.evaluate import ScenarioEvaluator
    from app.search import resolve_limits, SearchMode, SearchSpec
    from app.search.spec import ScenarioPlan

    profile = _profile_of(analysis, db)
    settings = _settings_of(db)
    spec = SearchSpec(
        mode=SearchMode.SWEEP,
        plan=ScenarioPlan(duration_s=600.0, time_step_s=1.0, start_s=0.0, label="reverify"),
        axes=(),
        refine=False,
    )
    evaluator = ScenarioEvaluator(
        profile=profile,
        spec=spec,
        thresholds=_thresholds_of(profile, settings),
        limits=_sim_limits_of(settings),
        budget=SearchBudget(limits=resolve_limits(settings)),
    )

    after_rows: list[dict] = []
    for failure in failures:
        base_values = dict(failure.get("values") or {})
        try:
            mitigated = apply_mitigations_to_case(base_values, payload.mitigations)
        except ValueError as exc:
            return error_response(422, "VALIDATION_ERROR", str(exc))
        mapping = {SearchVariable(k): float(v) for k, v in mitigated.items()}
        case = make_case(mapping, label=f"reverify: {failure.get('label') or ''}"[:120])
        before_outcome = evaluator.evaluate(
            make_case({SearchVariable(k): float(v) for k, v in base_values.items()}, label="before")
        )
        after_outcome = evaluator.evaluate(case)
        after_rows.append(
            {
                "failure_id": failure.get("key"),
                "case_label": failure.get("label"),
                "status_before": before_outcome.status.value,
                "status_after": after_outcome.status.value,
                "peaks_before": dict(before_outcome.peaks),
                "peaks_after": dict(after_outcome.peaks),
                "improved": int(after_outcome.rank) < int(before_outcome.rank),
            }
        )

    document = build_reverify_document(
        parent=analysis,
        mitigations=payload.mitigations,
        after_rows=after_rows,
    )
    from app.models import Analysis as _Analysis  # local alias for clarity

    child_id = f"an-{__import__('uuid').uuid4().hex[:12]}"
    child = _Analysis(
        id=child_id,
        owner_id=str(user.id),
        plant_id=str(analysis.plant_id),
        kind="reverify",
        status="complete",
        goal=(payload.goal or "")[:2000],
        parent_id=analysis.id,
        request={"mitigations": dict(payload.mitigations), "parent_id": analysis.id},
        result=document,
        counts={
            "scenarios": len(after_rows),
            "failing": document["comparison"]["failing_after"],
            "headline": "reverify",
            "disclaimer": ANALYSIS_DISCLAIMER,
        },
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return success_response(_history_out(child) | {"result": document})


@router.get("/{analysis_id}/report", summary="Interactive-report payload (tabs read this)")
def get_report_endpoint(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    analysis = _owned_analysis(db, analysis_id, user)
    if analysis.result is None:
        return error_response(409, "NOT_READY", "This analysis has no stored result yet.")
    result = analysis.result
    return success_response(
        {
            "analysis_id": analysis.id,
            "status": analysis.status,
            "kind": analysis.kind,
            "goal": analysis.goal,
            "created_at": analysis.created_at.isoformat(),
            "tabs": {
                "overview": {
                    "interpreted_change": result.get("interpreted_change"),
                    "counts": (result.get("original") or {}).get("counts"),
                    "status": (result.get("original") or {}).get("status"),
                    "notes": result.get("notes"),
                },
                "scenarios": {
                    "cases": (result.get("original") or {}).get("cases"),
                    "boundaries": (result.get("original") or {}).get("boundaries"),
                    "mode": (result.get("original") or {}).get("mode"),
                },
                "failures": {
                    "failures": result.get("failures"),
                },
                "counterfactuals": {
                    "rows": result.get("counterfactuals"),
                },
                "safeguards": {
                    "timings": (result.get("safeguards") or {}).get("timings"),
                    "note": (result.get("safeguards") or {}).get("note"),
                },
                "evidence": {
                    "notes": result.get("notes"),
                    "versions": result.get("versions"),
                    "disclaimer": ANALYSIS_DISCLAIMER,
                    "ai_explanation": result.get("ai_explanation"),
                },
            },
        }
    )


@router.get("/{analysis_id}/report.pdf", summary="Download the report as a multi-page PDF")
def get_report_pdf_endpoint(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    analysis = _owned_analysis(db, analysis_id, user)
    if analysis.result is None:
        raise HTTPException(status_code=409, detail="This analysis has no stored result yet.")
    data = render_report_pdf(analysis.result)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="safeflux-report-{analysis.id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# --------------------------------------------------------------------- shaping


def _analysis_out(analysis: Analysis) -> dict:
    return {
        "id": analysis.id,
        "plant_id": analysis.plant_id,
        "kind": analysis.kind,
        "status": analysis.status,
        "goal": analysis.goal,
        "parent_id": analysis.parent_id,
        "counts": analysis.counts,
        "error": analysis.error,
        "created_at": analysis.created_at.isoformat(),
        "finished_at": analysis.finished_at.isoformat() if analysis.finished_at else None,
        "has_result": analysis.result is not None,
        "disclaimer": ANALYSIS_DISCLAIMER,
    }


def _history_out(row: Analysis) -> dict:
    return {
        "id": row.id,
        "plant_id": row.plant_id,
        "kind": row.kind,
        "status": row.status,
        "goal": row.goal,
        "parent_id": row.parent_id,
        "counts": row.counts,
        "created_at": row.created_at.isoformat(),
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "disclaimer": ANALYSIS_DISCLAIMER,
    }


# The helper trio below re-derives the evaluation context for the failure page
# and reverify; both call sites need the same three objects.


def _profile_of(analysis: Analysis, db: Session):
    from app.search import PlantProfile

    plant = db.get(Plant, analysis.plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="The plant for this analysis was not found.")
    return PlantProfile.from_plant(plant)


def _settings_of(db: Session):
    from app.core.config import get_settings

    return get_settings()


def _thresholds_of(profile, settings):
    from app.safety import SafetyThresholds

    return SafetyThresholds(
        max_temperature_c=profile.safety_limits.max_temperature_c,
        max_pressure_bar=profile.safety_limits.max_pressure_bar,
        max_level_pct=profile.safety_limits.max_level_pct,
        near_limit_fraction=getattr(settings, "SAFETY_NEAR_LIMIT_FRACTION", 0.9),
    )


def _sim_limits_of(settings):
    from app.simulator import SimulationLimits

    return SimulationLimits(
        max_duration_s=getattr(settings, "SIM_MAX_DURATION_S", 3600.0),
        min_time_step_s=getattr(settings, "SIM_MIN_TIME_STEP_S", 0.05),
        max_samples=getattr(settings, "SIM_MAX_SAMPLES", 20000),
    )
