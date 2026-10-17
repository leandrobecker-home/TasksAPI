"""Translation of errors into RFC 9457 Problem Details responses (RT14)."""

import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.errors import DomainError
from app.schemas.problem import PROBLEM_MEDIA_TYPE, ProblemDetails

logger = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "An unexpected error occurred."

VALIDATION_TITLE = "Validation Error"
MALFORMED_JSON_TITLE = "Bad Request"
MALFORMED_JSON_DETAIL = "Malformed JSON in the request body."

# Errors in these request parts are the client sending a bad resource (422);
# anything else, such as query parameters, is a bad request (400).
UNPROCESSABLE_SOURCES = frozenset({"body", "path"})


def _location(loc: Sequence[int | str]) -> str:
    """Render where an error happened, e.g. ``title`` for ``("body", "title")``."""
    source, *rest = loc
    return ".".join(str(part) for part in rest) or str(source)


def describe_validation_errors(errors: Sequence[Mapping[str, Any]]) -> str:
    """Summarise validation errors as ``field: message`` pairs."""
    return "; ".join(f"{_location(error['loc'])}: {error['msg']}" for error in errors)


def _http_title(status_code: int) -> str:
    """Return the standard reason phrase, e.g. ``Not Found`` for 404."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _http_detail(request: Request, status_code: int, detail: str) -> str:
    """Make the router's bare 404 and 405 messages more informative."""
    if status_code == HTTPStatus.NOT_FOUND and detail == HTTPStatus.NOT_FOUND.phrase:
        return "No endpoint matches this path."
    if (
        status_code == HTTPStatus.METHOD_NOT_ALLOWED
        and detail == HTTPStatus.METHOD_NOT_ALLOWED.phrase
    ):
        return f"Method {request.method} is not allowed on this path."
    return detail


def _is_malformed_json(errors: Sequence[Mapping[str, Any]]) -> bool:
    return any(error["type"] == "json_invalid" for error in errors)


def validation_status(errors: Sequence[Mapping[str, Any]]) -> int:
    """Pick the HTTP status for a failed request validation (RT14).

    An invalid body or path parameter is ``422`` and an invalid query
    parameter is ``400``; when both kinds are present, the body or path wins.
    Malformed JSON is handled before this, as a plain ``400``.
    """
    if any(error["loc"][0] in UNPROCESSABLE_SOURCES for error in errors):
        return 422
    return 400


def problem_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build a ``application/problem+json`` response for ``request``.

    ``instance`` is the request path only, so query values never leak into
    error bodies.
    """
    problem = ProblemDetails(
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
    )
    return JSONResponse(
        problem.model_dump(),
        status_code=status_code,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Install the handlers that turn exceptions into Problem Details."""

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return problem_response(
            request,
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if _is_malformed_json(errors):
            return problem_response(
                request,
                status_code=400,
                title=MALFORMED_JSON_TITLE,
                detail=MALFORMED_JSON_DETAIL,
            )
        return problem_response(
            request,
            status_code=validation_status(errors),
            title=VALIDATION_TITLE,
            detail=describe_validation_errors(errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return problem_response(
            request,
            status_code=exc.status_code,
            title=_http_title(exc.status_code),
            detail=_http_detail(request, exc.status_code, str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The traceback goes to the log only; the client never sees internals.
        logger.error(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return problem_response(
            request,
            status_code=500,
            title=_http_title(500),
            detail=INTERNAL_ERROR_DETAIL,
        )
