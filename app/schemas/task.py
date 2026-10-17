"""Request and response schemas of the task endpoints (RF06-RF13)."""

import re
from datetime import date, datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import TaskPriority, TaskStatus
from app.models.task import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH
from app.schemas.base import InputModel

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _require_iso_date(value: Any) -> Any:
    """Accept only ``YYYY-MM-DD`` text (or a plain date), never a timestamp."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        return value
    raise ValueError("must be a date in the format YYYY-MM-DD")


DueDate = Annotated[date | None, BeforeValidator(_require_iso_date)]


class TaskCreate(InputModel):
    """Body of ``POST /task-groups/{group_id}/tasks``.

    The group comes from the path, so the body has no ``task_group_id``.
    """

    title: str = Field(min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: DueDate = None


class TaskUpdate(InputModel):
    """Body of ``PATCH /tasks/{id}``: only the fields sent are changed.

    ``description`` and ``due_date`` may be ``null`` to clear them; the other
    fields are required values and may not be ``null``. ``task_group_id`` moves
    the task to another group.
    """

    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: DueDate = None
    task_group_id: UUID | None = None

    @field_validator("title", "status", "priority", "task_group_id")
    @classmethod
    def _cannot_be_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("cannot be null")
        return value


class TaskRead(BaseModel):
    """A task as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_group_id: UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
