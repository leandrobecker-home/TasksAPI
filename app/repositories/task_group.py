"""Data access for task groups (RT02, RT03). The only place that queries them."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.errors import ConflictError
from app.models import TaskGroup
from app.models.task_group import normalize_name

DUPLICATE_NAME_DETAIL = "A task group with this name already exists."
GROUP_HAS_TASKS_DETAIL = "The task group still has tasks; delete or move them first."


class TaskGroupRepository:
    """Reads and writes ``TaskGroup`` rows through one session.

    Writes are flushed, not committed: the caller owns the transaction. A write
    that breaks the unique name rule is reported as a ``ConflictError``, which
    also covers two requests creating the same name at the same time, since the
    database's unique index is the final arbiter (RN01).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, group: TaskGroup) -> TaskGroup:
        """Insert a new group."""
        self._session.add(group)
        self._flush()
        return group

    def save(self, group: TaskGroup) -> TaskGroup:
        """Write the pending changes of an existing group."""
        self._session.add(group)
        self._flush()
        return group

    def delete(self, group: TaskGroup) -> None:
        """Remove a group.

        Raises ``ConflictError`` if tasks still point at it: the database refuses
        the deletion, which backs up the service's own check when a task is
        created in the group at the very same moment (RN03).
        """
        self._session.delete(group)
        try:
            self._session.flush()
        except IntegrityError as error:
            if "foreign key" not in str(error.orig).lower():
                raise
            self._session.rollback()
            raise ConflictError(GROUP_HAS_TASKS_DETAIL) from error

    def get(self, group_id: UUID) -> TaskGroup | None:
        """Return the group with this id, or ``None``."""
        return self._session.get(TaskGroup, group_id)

    def get_by_name(self, name: str) -> TaskGroup | None:
        """Return the group with this name, or ``None``.

        The comparison ignores letter case (accented letters included) and
        surrounding spaces, as the uniqueness rule does (RN01).
        """
        statement = select(TaskGroup).where(
            col(TaskGroup.normalized_name) == normalize_name(name)
        )
        return self._session.exec(statement).first()

    def list_page(
        self, *, search: str | None, offset: int, limit: int
    ) -> tuple[Sequence[TaskGroup], int]:
        """Return one page of groups and the total number of matches.

        ``search`` keeps the groups whose name contains the text, ignoring case
        and surrounding spaces; a blank ``search`` is treated as absent. Groups
        are ordered by name.
        """
        matching = select(TaskGroup)
        if search is not None and search.strip():
            term = normalize_name(search)
            matching = matching.where(
                col(TaskGroup.normalized_name).contains(term, autoescape=True)
            )

        total = self._session.exec(
            select(func.count()).select_from(matching.subquery())
        ).one()
        page = self._session.exec(
            matching.order_by(col(TaskGroup.normalized_name), col(TaskGroup.id))
            .offset(offset)
            .limit(limit)
        ).all()
        return page, total

    def _flush(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as error:
            if "normalized_name" not in str(error.orig):
                raise
            self._session.rollback()
            raise ConflictError(DUPLICATE_NAME_DETAIL) from error
