"""Enumerations used by the table models and the API contract."""

from enum import StrEnum


class TaskStatus(StrEnum):
    """Where a task is in its life cycle."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskPriority(StrEnum):
    """How important a task is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
