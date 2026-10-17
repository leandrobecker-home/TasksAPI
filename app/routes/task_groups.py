"""Task group endpoints (RF01-RF05), served under ``/api/v1``."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.models import TaskGroup
from app.routes.dependencies import PaginationDep, SessionDep
from app.schemas.common import Page, build_page
from app.schemas.task_group import TaskGroupCreate, TaskGroupRead
from app.services.task_group import TaskGroupService

router = APIRouter(prefix="/task-groups", tags=["task-groups"])


def get_task_group_service(session: SessionDep) -> TaskGroupService:
    return TaskGroupService(session)


ServiceDep = Annotated[TaskGroupService, Depends(get_task_group_service)]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskGroupRead,
    summary="Create a task group",
)
def create_task_group(
    data: TaskGroupCreate,
    request: Request,
    response: Response,
    service: ServiceDep,
) -> TaskGroup:
    """Create a task group. The name must be unique, ignoring letter case."""
    group = service.create(data)
    response.headers["Location"] = f"{request.url.path}/{group.id}"
    return group


@router.get(
    "",
    response_model=Page[TaskGroupRead],
    summary="List task groups",
)
def list_task_groups(
    service: ServiceDep,
    pagination: PaginationDep,
    q: Annotated[
        str | None,
        Query(description="Keep only groups whose name contains this text."),
    ] = None,
) -> Page[TaskGroupRead]:
    """List task groups, ordered by name, one page at a time."""
    groups, total = service.list(search=q, pagination=pagination)
    items = [TaskGroupRead.model_validate(group) for group in groups]
    return build_page(items, pagination, total)


@router.get(
    "/{group_id}",
    response_model=TaskGroupRead,
    summary="Get a task group",
)
def get_task_group(group_id: UUID, service: ServiceDep) -> TaskGroup:
    """Return one task group, or 404 if it does not exist."""
    return service.get(group_id)
