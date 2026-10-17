"""Test data factories shared by the whole suite (RT15).

``build_*`` returns an unsaved object; ``create_*`` saves it in the given
session. Every call gets unique defaults, so tests only spell out the values
they actually care about.
"""

from itertools import count
from typing import Any

from sqlmodel import Session

from app.models import TaskGroup

_group_numbers = count(1)


def build_task_group(**overrides: Any) -> TaskGroup:
    """Return an unsaved ``TaskGroup`` with a unique name."""
    values: dict[str, Any] = {"name": f"Group {next(_group_numbers)}"}
    values.update(overrides)
    return TaskGroup(**values)


def create_task_group(session: Session, **overrides: Any) -> TaskGroup:
    """Save a ``TaskGroup`` and return it with its generated fields filled in."""
    group = build_task_group(**overrides)
    session.add(group)
    session.commit()
    session.refresh(group)
    return group
