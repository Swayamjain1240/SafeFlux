"""Live simulated telemetry endpoints (Part 5).

Paths are `/api/v1/plants/{plant_id}/telemetry/*`:

- ``GET .../current`` — the latest telemetry frame,
- ``GET .../history`` — recent bounded history,
- ``GET .../stream``  — SSE replay of the stored frames.

Security posture:
- every route requires a verified session and loads the plant with
  ``get_owned_or_404``, so another user's plant returns 404 (rule 5),
- the stream is gated by hard connection limits before it is opened (rule 8),
- query limits are bounded server-side, and responses follow the shared
  envelope and never expose owner ids or internals.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.responses import error_response, success_response
from app.database import get_db
from app.models import Plant, User
from app.schemas import (
    TelemetryCurrentData,
    TelemetryFrameOut,
    TelemetryHistoryData,
)
from app.telemetry import MAX_HISTORY_LIMIT, ConnectionLimitError, TelemetryFrame

router = APIRouter(prefix="/plants", tags=["telemetry"])

_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _frame_out(frame: TelemetryFrame) -> TelemetryFrameOut:
    return TelemetryFrameOut(**frame.to_dict())


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get(
    "/{plant_id}/telemetry/current",
    summary="Latest telemetry frame for a plant",
)
def get_current(
    plant_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_owned_or_404(db, Plant, plant_id, user)
    service = request.app.state.telemetry
    frame = service.current(plant_id)
    data = TelemetryCurrentData(
        plantId=plant_id,
        frame=_frame_out(frame) if frame is not None else None,
    )
    return success_response(data.model_dump())


@router.get(
    "/{plant_id}/telemetry/history",
    summary="Recent bounded telemetry history for a plant",
)
def get_history(
    plant_id: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=MAX_HISTORY_LIMIT),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    get_owned_or_404(db, Plant, plant_id, user)
    settings = request.app.state.settings
    effective_limit = limit or settings.TELEMETRY_HISTORY_DEFAULT_LIMIT
    service = request.app.state.telemetry
    frames = service.history(plant_id, effective_limit)
    data = TelemetryHistoryData(
        plantId=plant_id,
        count=len(frames),
        limit=effective_limit,
        frames=[_frame_out(frame) for frame in frames],
    )
    return success_response(data.model_dump())


@router.get(
    "/{plant_id}/telemetry/stream",
    summary="Server-Sent Events stream of simulated telemetry",
)
def stream_telemetry(
    plant_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_or_404(db, Plant, plant_id, user)
    service = request.app.state.telemetry
    if not service.has_session(plant_id):
        return error_response(
            404,
            "NOT_FOUND",
            "No telemetry is available for this plant yet.",
        )

    # Enforce connection limits before opening the stream so an over-limit
    # client gets a normal envelope instead of a half-open SSE connection.
    try:
        service.acquire(plant_id, user.id)
    except ConnectionLimitError:
        return error_response(
            429,
            "RATE_LIMITED",
            "Too many live telemetry streams. Please close one and retry.",
            headers={"Retry-After": "5"},
        )

    settings = request.app.state.settings
    interval = max(settings.TELEMETRY_REPLAY_INTERVAL_MS / 1000.0, 0.02)

    frames = service.history(plant_id)

    async def event_stream():
        try:
            yield ": connected\n\n"
            for frame in frames:
                yield _sse("telemetry", frame.to_dict())
                if interval:
                    await asyncio.sleep(interval)
            # The MVP replays a finite deterministic trajectory; a client that
            # wants newer frames reconnects (and immediately receives current).
            yield _sse(
                "complete",
                {"plant_id": plant_id, "frames": len(frames)},
            )
        finally:
            # Runs on completion or client disconnect — always frees the slot.
            service.release(plant_id, user.id)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_STREAM_HEADERS)
