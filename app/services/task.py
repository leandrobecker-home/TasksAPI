"""Business rules for tasks (RN02, RN04, RN05, RN06, RN07)."""

from collections.abc import Sequence
from uuid import UUID

from sqlmodel import Session

from app.errors import InvalidReferenceError, NotFoundError
from app.models import Task, TaskStatus
from app.models.base import utc_now
from app.repositories.task import TaskRepository
from app.repositories.task_group import TaskGroupRepository
from app.schemas.common import Pagination
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    """Creates, reads, updates and deletes tasks.

    Every operation that changes data is committed here, so each call is one
    transaction. The service owns the status rules: a new task is ``pending``
    unless told otherwise (RN05), any status may follow any other (RN06), and
    ``completed_at`` is set when a task becomes completed and cleared when it
    stops being so, never taken from the client (RN07).
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._groups = TaskGroupRepository(session)
        self._tasks = TaskRepository(session)

    def create(self, group_id: UUID, data: TaskCreate) -> Task:
        """Create a task in a group; ``NotFoundError`` if the group is missing.

        There is no way to create a task outside a group (RN02).
        """
        self._require_group(group_id)
        task = Task(
            task_group_id=group_id,
            title=data.title,
            description=data.description,
            status=data.status,
            priority=data.priority,
            due_date=data.due_date,
        )
        if task.status is TaskStatus.COMPLETED:
            task.completed_at = task.created_at
        self._tasks.add(task)
        return self._commit(task)

    def get(self, task_id: UUID) -> Task:
        """Return a task; ``NotFoundError`` if it does not exist."""
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError(f"Task {task_id} not found.")
        return task

    def list_for_group(
        self, group_id: UUID, pagination: Pagination
    ) -> tuple[Sequence[Task], int]:
        """Return one page of a group's tasks and the total number of them.

        ``NotFoundError`` if the group does not exist, even when the page would
        be empty.
        """
        self._require_group(group_id)
        return self._tasks.list_page(
            group_id=group_id, offset=pagination.offset, limit=pagination.limit
        )

    def update(self, task_id: UUID, data: TaskUpdate) -> Task:
        """Change only the fields the client sent.

        ``NotFoundError`` if the task does not exist. ``InvalidReferenceError``
        if it is being moved to a group that does not exist (RN04); in that case
        nothing changes.
        """
        task = self.get(task_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return task

        new_group_id = changes.get("task_group_id")
        if new_group_id is not None and new_group_id != task.task_group_id:
            self._require_group_to_move_to(new_group_id)

        was_completed = task.status is TaskStatus.COMPLETED
        for field, value in changes.items():
            setattr(task, field, value)
        is_completed = task.status is TaskStatus.COMPLETED
        if is_completed and not was_completed:
            task.completed_at = utc_now()
        elif was_completed and not is_completed:
            task.completed_at = None

        self._tasks.save(task)
        return self._commit(task)

    def delete(self, task_id: UUID) -> None:
        """Delete a task; ``NotFoundError`` if it does not exist."""
        task = self.get(task_id)
        self._tasks.delete(task)
        self._session.commit()

    def _require_group(self, group_id: UUID) -> None:
        if self._groups.get(group_id) is None:
            raise NotFoundError(f"Task group {group_id} not found.")

    def _require_group_to_move_to(self, group_id: UUID) -> None:
        if self._groups.get(group_id) is None:
            raise InvalidReferenceError("task_group_id: the task group does not exist.")

    def _commit(self, task: Task) -> Task:
        self._session.commit()
        self._session.refresh(task)
        return task
