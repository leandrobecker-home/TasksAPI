"""Health check endpoint (RF14). Served at the root, outside ``/api/v1``."""

from fastapi import APIRouter, Response, status

from app.routes.dependencies import SessionDep
from app.schemas.health import HealthResponse, HealthState
from app.services.health import check_database

router = APIRouter(tags=["operation"])


@router.get(
    "/health",
    summary="Health check",
    response_model=HealthResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "The database is unavailable.",
        }
    },
)
def health(response: Response, session: SessionDep) -> HealthResponse:
    """Report whether the application and its database connection are healthy."""
    database_ok = check_database(session)
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    state: HealthState = "ok" if database_ok else "error"
    return HealthResponse(status=state, database=state)
