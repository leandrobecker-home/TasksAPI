"""Translation of errors into RFC 9457 Problem Details responses (RT14)."""

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import DomainError
from app.schemas.problem import PROBLEM_MEDIA_TYPE, ProblemDetails

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
