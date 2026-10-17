"""Unit tests for the Task table model (RT03, RN02)."""

from datetime import UTC, date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import Task, TaskGroup, TaskPriority, TaskStatus
from tests.factories import build_task, create_task, create_task_group


def test_table_and_columns(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}

    assert columns == {
        "id",
        "task_group_id",
        "title",
        "description",
        "status",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
        "completed_at",
    }


def test_task_group_id_is_a_required_foreign_key_to_task_groups(engine: Engine) -> None:
    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys("tasks")
    column = next(
        column
        for column in inspector.get_columns("tasks")
        if column["name"] == "task_group_id"
    )

    assert [
        (key["constrained_columns"], key["referred_table"], key["referred_columns"])
        for key in foreign_keys
    ] == [(["task_group_id"], "task_groups", ["id"])]
    assert column["nullable"] is False


# --- the database refuses orphans (RN02) -----------------------------------------


def test_task_with_an_unknown_group_is_rejected_by_the_database(
    session: Session,
) -> None:
    orphan = Task(task_group_id=uuid4(), title="Orphan")
    session.add(orphan)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


def test_task_without_a_group_is_rejected_by_the_database(session: Session) -> None:
    session.add(Task(title="No group"))  # type: ignore[call-arg]

    with pytest.raises(IntegrityError, match="NOT NULL"):
        session.commit()


def test_a_group_with_tasks_cannot_be_deleted(session: Session) -> None:
    task = create_task(session)
    group = session.get(TaskGroup, task.task_group_id)
    assert group is not None

    session.delete(group)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


def test_a_group_can_be_deleted_once_its_tasks_are_gone(session: Session) -> None:
    task = create_task(session)
    group = session.get(TaskGroup, task.task_group_id)
    assert group is not None

    session.delete(task)
    session.commit()
    session.delete(group)
    session.commit()

    assert session.get(TaskGroup, group.id) is None


def test_a_group_without_tasks_can_be_deleted(session: Session) -> None:
    group = create_task_group(session)

    session.delete(group)
    session.commit()

    assert session.get(TaskGroup, group.id) is None


def test_a_task_can_be_moved_to_another_existing_group(session: Session) -> None:
    task = create_task(session)
    other_group = create_task_group(session)

    task.task_group_id = other_group.id
    session.commit()
    session.refresh(task)

    assert task.task_group_id == other_group.id


def test_a_task_cannot_be_moved_to_an_unknown_group(session: Session) -> None:
    task = create_task(session)

    task.task_group_id = uuid4()

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.commit()


# --- defaults and generated fields -----------------------------------------------


def test_a_new_task_gets_the_documented_defaults(session: Session) -> None:
    task = create_task(session)

    assert isinstance(task.id, UUID)
    assert task.status is TaskStatus.PENDING
    assert task.priority is TaskPriority.MEDIUM
    assert task.description is None
    assert task.due_date is None
    assert task.completed_at is None
    assert task.created_at == task.updated_at


def test_all_fields_round_trip(engine: Engine, session: Session) -> None:
    group = create_task_group(session)
    task = create_task(
        session,
        group,
        title="Write report",
        description="quarterly numbers",
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 12, 31),
    )
    task_id = task.id

    with Session(engine) as other_session:
        reloaded = other_session.get(Task, task_id)

    assert reloaded is not None
    assert reloaded.title == "Write report"
    assert reloaded.description == "quarterly numbers"
    assert reloaded.status is TaskStatus.IN_PROGRESS
    assert reloaded.priority is TaskPriority.HIGH
    assert reloaded.due_date == date(2026, 12, 31)


def test_completed_at_round_trips_as_utc(engine: Engine, session: Session) -> None:
    group = create_task_group(session)
    task = create_task(session, group, status=TaskStatus.COMPLETED)
    task.completed_at = task.created_at + timedelta(hours=1)
    session.commit()
    task_id = task.id

    with Session(engine) as other_session:
        reloaded = other_session.get(Task, task_id)

    assert reloaded is not None
    assert reloaded.completed_at is not None
    assert reloaded.completed_at.tzinfo == UTC
    assert reloaded.created_at.tzinfo == UTC


def test_updated_at_changes_on_update_and_created_at_does_not(
    session: Session,
) -> None:
    task = create_task(session)
    created_at = task.created_at
    first_updated_at = task.updated_at

    task.title = "Renamed"
    session.commit()
    session.refresh(task)

    assert task.created_at == created_at
    assert task.updated_at > first_updated_at


# --- enums are stored as their values --------------------------------------------


@pytest.mark.parametrize(
    ("status", "priority"),
    [
        (TaskStatus.PENDING, TaskPriority.LOW),
        (TaskStatus.IN_PROGRESS, TaskPriority.MEDIUM),
        (TaskStatus.COMPLETED, TaskPriority.HIGH),
    ],
)
def test_enums_are_stored_as_lowercase_values(
    session: Session, status: TaskStatus, priority: TaskPriority
) -> None:
    task = create_task(session, status=status, priority=priority)

    stored = session.connection().execute(
        text("SELECT status, priority FROM tasks WHERE id = :id"),
        {"id": task.id.hex},
    )

    assert stored.one() == (status.value, priority.value)


@pytest.mark.parametrize("column", ["status", "priority"])
def test_the_database_rejects_values_outside_the_enum(
    session: Session, column: str
) -> None:
    task = create_task(session)

    with pytest.raises(IntegrityError, match="CHECK"):
        session.connection().execute(
            text(f"UPDATE tasks SET {column} = 'bogus' WHERE id = :id"),
            {"id": task.id.hex},
        )


def test_build_task_does_not_save_anything(session: Session) -> None:
    group = create_task_group(session)

    build_task(group)

    assert (
        session.connection().execute(text("SELECT COUNT(*) FROM tasks")).scalar() == 0
    )
