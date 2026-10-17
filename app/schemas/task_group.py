"""Request and response schemas of the task group endpoints (RF01-RF05)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task_group import DESCRIPTION_MAX_LENGTH, NAME_MAX_LENGTH
from app.schemas.base import InputModel


class TaskGroupCreate(InputModel):
    """Body of ``POST /task-groups``."""

    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)


class TaskGroupUpdate(InputModel):
    """Body of ``PATCH /task-groups/{id}``: only the fields sent are changed.

    ``description`` may be ``null`` to clear it; ``name`` may not.
    """

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)

    @field_validator("name")
    @classmethod
    def _name_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class TaskGroupRead(BaseModel):
    """A task group as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
