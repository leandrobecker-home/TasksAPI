"""SQLModel table definitions.

Importing this package registers every table on ``SQLModel.metadata``.
"""

from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.models.task_group import TaskGroup

__all__ = ["Task", "TaskGroup", "TaskPriority", "TaskStatus"]
