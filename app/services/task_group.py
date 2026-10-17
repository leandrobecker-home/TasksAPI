"""Business rules for task groups (RN01, RN03, RN08)."""

from collections.abc import Sequence
from uuid import UUID

from sqlmodel import Session

from app.errors import ConflictError, NotFoundError
from app.models import TaskGroup
from app.repositories.task import TaskRepository
from app.repositories.task_group import GROUP_HAS_TASKS_DETAIL, TaskGroupRepository
from app.schemas.common import Pagination
from app.schemas.task_group import TaskGroupCreate, TaskGroupUpdate


class TaskGroupService:
    """Creates, reads, updates and deletes task groups.

    Every operation that changes data is committed here, so each call is one
    transaction. Name uniqueness (RN01) is enforced by the repository, which
    turns a violation of the database's unique index into a ``ConflictError``.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._groups = TaskGroupRepository(session)
        self._tasks = TaskRepository(session)

    def create(self, data: TaskGroupCreate) -> TaskGroup:
        """Create a group; ``ConflictError`` if the name is already taken."""
        group = self._groups.add(
            TaskGroup(name=data.name, description=data.description)
        )
        return self._commit(group)

    def get(self, group_id: UUID) -> TaskGroup:
        """Return a group; ``NotFoundError`` if it does not exist."""
        group = self._groups.get(group_id)
        if group is None:
            raise NotFoundError(f"Task group {group_id} not found.")
        return group

    def list(
        self, *, search: str | None, pagination: Pagination
    ) -> tuple[Sequence[TaskGroup], int]:
        """Return one page of groups and the total number of matches."""
        return self._groups.list_page(
            search=search, offset=pagination.offset, limit=pagination.limit
        )

    def update(self, group_id: UUID, data: TaskGroupUpdate) -> TaskGroup:
        """Change only the fields the client sent.

        ``NotFoundError`` if the group does not exist; ``ConflictError`` if the
        new name belongs to another group. Keeping the group's own name, even
        with different letter case, is not a conflict.
        """
        group = self.get(group_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return group
        for field, value in changes.items():
            setattr(group, field, value)
        self._groups.save(group)
        return self._commit(group)

    def delete(self, group_id: UUID) -> None:
        """Delete a group.

        ``NotFoundError`` if it does not exist; ``ConflictError`` if it still has
        tasks, which must be deleted or moved first (RN03).
        """
        group = self.get(group_id)
        if self._tasks.count_for_group(group_id) > 0:
            raise ConflictError(GROUP_HAS_TASKS_DETAIL)
        self._groups.delete(group)
        self._session.commit()

    def _commit(self, group: TaskGroup) -> TaskGroup:
        self._session.commit()
        self._session.refresh(group)
        return group
