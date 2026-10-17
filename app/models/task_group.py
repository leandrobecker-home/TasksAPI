"""The ``TaskGroup`` table (RT03, RN01)."""

import unicodedata
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event
from sqlmodel import Field, SQLModel

from app.models.base import utc_now

NAME_MAX_LENGTH = 100
DESCRIPTION_MAX_LENGTH = 500


def normalize_name(name: str) -> str:
    """Return the form of ``name`` used to detect duplicates (RN01).

    Surrounding spaces are dropped and the text is case-folded, so ``Ação`` and
    ``AÇÃO`` collide. SQLite's ``lower()`` only handles ASCII, which is why this
    is done in Python and stored in its own column.
    """
    composed = unicodedata.normalize("NFC", name.strip())
    return unicodedata.normalize("NFC", composed.casefold())


class TaskGroup(SQLModel, table=True):
    """Groups tasks; every task belongs to exactly one group."""

    __tablename__ = "task_groups"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=NAME_MAX_LENGTH)
    # Derived from ``name`` on every insert and update; never set by hand.
    normalized_name: str = Field(default="", index=True, unique=True)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX_LENGTH)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


@event.listens_for(TaskGroup, "before_insert")
def _derive_normalized_name_on_insert(
    _mapper: Any, _connection: Any, group: TaskGroup
) -> None:
    group.normalized_name = normalize_name(group.name)
    # A group that was never changed has been "updated" exactly when created.
    group.updated_at = group.created_at


@event.listens_for(TaskGroup, "before_update")
def _refresh_derived_fields_on_update(
    _mapper: Any, _connection: Any, group: TaskGroup
) -> None:
    group.normalized_name = normalize_name(group.name)
    group.updated_at = utc_now()
