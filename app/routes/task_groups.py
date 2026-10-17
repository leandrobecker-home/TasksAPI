"""Task group endpoints (RF01-RF05), served under ``/api/v1``."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.models import TaskGroup
from app.routes.dependencies import SessionDep
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
