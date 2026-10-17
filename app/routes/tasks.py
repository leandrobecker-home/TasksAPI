"""Task endpoints (RF06-RF13), served under ``/api/v1``.

Tasks are created and listed through their group, and read, changed and deleted
directly by id, so there are two routers.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.models import Task
from app.routes.dependencies import PaginationDep, SessionDep
from app.schemas.common import Page, build_page
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task import TaskService

group_tasks_router = APIRouter(prefix="/task-groups/{group_id}/tasks", tags=["tasks"])
router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(session)


ServiceDep = Annotated[TaskService, Depends(get_task_service)]


@group_tasks_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskRead,
    summary="Create a task in a group",
)
def create_task(
    group_id: UUID,
    data: TaskCreate,
    request: Request,
    response: Response,
    service: ServiceDep,
) -> Task:
    """Create a task in the group. A task cannot exist outside a group."""
    task = service.create(group_id, data)
    api_prefix = request.url.path.partition("/task-groups/")[0]
    response.headers["Location"] = f"{api_prefix}/tasks/{task.id}"
    return task


@group_tasks_router.get(
    "",
    response_model=Page[TaskRead],
    summary="List the tasks of a group",
)
def list_group_tasks(
    group_id: UUID, pagination: PaginationDep, service: ServiceDep
) -> Page[TaskRead]:
    """List the tasks of a group, newest first, one page at a time."""
    tasks, total = service.list_for_group(group_id, pagination)
    items = [TaskRead.model_validate(task) for task in tasks]
    return build_page(items, pagination, total)


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get a task",
)
def get_task(task_id: UUID, service: ServiceDep) -> Task:
    """Return one task, or 404 if it does not exist."""
    return service.get(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    summary="Update a task",
)
def update_task(task_id: UUID, data: TaskUpdate, service: ServiceDep) -> Task:
    """Change only the fields sent; the others keep their values.

    Setting ``task_group_id`` moves the task to another group.
    """
    return service.update(task_id, data)
