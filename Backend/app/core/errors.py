"""Global exception handling with production-safe error responses.

Never leaks stack traces, SQL, filesystem paths or secrets
(SAFEFLUX_MASTER.md §17).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import FieldError, error_payload, error_response

logger = logging.getLogger("safeflux.error")

_HTTP_ERROR_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

_HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "The request could not be processed.",
    401: "Authentication is required.",
    403: "You do not have access to this resource.",
    404: "The requested resource was not found.",
    405: "That method is not allowed for this resource.",
    408: "The request timed out.",
    409: "The request conflicts with the current state.",
    413: "The request payload is too large.",
    415: "The request content type is not supported.",
    422: "One or more input fields are invalid.",
    429: "Too many requests. Please slow down and try again.",
    500: "An unexpected error occurred. Please try again later.",
    503: "The service is temporarily unavailable.",
}

_MAX_SAFE_DETAIL_LENGTH = 300


def _sanitize(message: str, limit: int = _MAX_SAFE_DETAIL_LENGTH) -> str:
    """Single-line, length-capped message safe to return to clients."""
    return " ".join(str(message).split())[:limit]


def _http_status_payload(status_code: int, detail: object) -> dict:
    code = _HTTP_ERROR_CODES.get(status_code, "HTTP_ERROR")
    message = _HTTP_ERROR_MESSAGES.get(status_code, "The request could not be processed.")

    # 4xx details are written by our own code and are safe to surface;
    # 5xx details are never surfaced.
    if status_code < 500 and isinstance(detail, str) and detail:
        message = _sanitize(detail)

    return error_payload(code, message)


async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    status_code = exc.status_code
    if status_code >= 500:
        logger.error(
            "HTTP %s on %s %s", status_code, request.method, request.url.path
        )
    return JSONResponse(
        status_code=status_code,
        content=_http_status_payload(status_code, exc.detail),
        headers=getattr(exc, "headers", None),
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details: list[FieldError] = []
    for err in exc.errors()[:20]:
        location = [str(part) for part in err.get("loc", ()) if part != "body"]
        details.append(
            FieldError(
                field=".".join(location) or "body",
                message=_sanitize(err.get("msg", "Invalid value"), limit=200),
            )
        )
    logger.warning("Validation failure on %s %s", request.method, request.url.path)
    return error_response(422, "VALIDATION_ERROR", _HTTP_ERROR_MESSAGES[422], details)


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler (500). Full traceback goes to logs only."""
    logger.exception(
        "Unhandled error on %s %s", request.method, request.url.path
    )
    return error_response(500, "INTERNAL_ERROR", _HTTP_ERROR_MESSAGES[500])


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
