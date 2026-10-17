"""SQLModel table definitions.

Importing this package registers every table on ``SQLModel.metadata``.
"""

from app.models.task_group import TaskGroup

__all__ = ["TaskGroup"]
