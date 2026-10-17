"""The ``Task`` table (RT03)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, event
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, SQLModel

from app.models.base import utc_now
from app.models.enums import TaskPriority, TaskStatus

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000


def _enum_column(enum_class: type[StrEnum], name: str) -> Column[Any]:
    """Store an enum as its lowercase value, guarded by a CHECK constraint.

    SQLAlchemy would store the member names (``PENDING``) by default, which
    would not match the values the API exposes (``pending``).
    """
    return Column(
        SQLEnum(
            enum_class,
            name=name,
            native_enum=False,
            create_constraint=True,
            values_callable=lambda members: [member.value for member in members],
            length=20,
        ),
        nullable=False,
    )


class Task(SQLModel, table=True):
    """A unit of work. It always belongs to exactly one task group (RN02)."""

    __tablename__ = "tasks"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_group_id: UUID = Field(foreign_key="task_groups.id")
    title: str = Field(max_length=TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        sa_column=_enum_column(TaskStatus, "task_status"),
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        sa_column=_enum_column(TaskPriority, "task_priority"),
    )
    due_date: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = Field(default=None)


@event.listens_for(Task, "before_insert")
def _align_updated_at_on_insert(_mapper: Any, _connection: Any, task: Task) -> None:
    # A task that was never changed has been "updated" exactly when created.
    task.updated_at = task.created_at


@event.listens_for(Task, "before_update")
def _refresh_updated_at_on_update(_mapper: Any, _connection: Any, task: Task) -> None:
    task.updated_at = utc_now()
