"""Translation of errors into RFC 9457 Problem Details responses (RT14)."""

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import DomainError
from app.schemas.problem import PROBLEM_MEDIA_TYPE, ProblemDetails


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
