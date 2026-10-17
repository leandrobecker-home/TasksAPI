"""Data access for tasks (RT02, RT03). The only place that queries them."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.errors import InvalidReferenceError
from app.models import Task

UNKNOWN_GROUP_DETAIL = "The task group does not exist."


class TaskRepository:
    """Reads and writes ``Task`` rows through one session.

    Writes are flushed, not committed: the caller owns the transaction. A write
    that points at a group that does not exist is reported as an
    ``InvalidReferenceError``. The services check the group first; the database's
    foreign key catches the rare case where it disappears in between (RN02).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: Task) -> Task:
        """Insert a new task."""
        self._session.add(task)
        self._flush()
        return task

    def save(self, task: Task) -> Task:
        """Write the pending changes of an existing task."""
        self._session.add(task)
        self._flush()
        return task

    def delete(self, task: Task) -> None:
        """Remove a task."""
        self._session.delete(task)
        self._session.flush()

    def get(self, task_id: UUID) -> Task | None:
        """Return the task with this id, or ``None``."""
        return self._session.get(Task, task_id)

    def list_page(
        self, *, group_id: UUID | None, offset: int, limit: int
    ) -> tuple[Sequence[Task], int]:
        """Return one page of tasks and the total number of matches.

        ``group_id`` limits the listing to one group; ``None`` lists every task.
        The newest tasks come first.
        """
        matching = select(Task)
        if group_id is not None:
            matching = matching.where(col(Task.task_group_id) == group_id)

        total = self._session.exec(
            select(func.count()).select_from(matching.subquery())
        ).one()
        page = self._session.exec(
            matching.order_by(col(Task.created_at).desc(), col(Task.id))
            .offset(offset)
            .limit(limit)
        ).all()
        return page, total

    def count_for_group(self, group_id: UUID) -> int:
        """Return how many tasks belong to a group."""
        return self._session.exec(
            select(func.count())
            .select_from(Task)
            .where(col(Task.task_group_id) == group_id)
        ).one()

    def _flush(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as error:
            if "foreign key" not in str(error.orig).lower():
                raise
            self._session.rollback()
            raise InvalidReferenceError(UNKNOWN_GROUP_DETAIL) from error
