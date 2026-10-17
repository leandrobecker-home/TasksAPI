"""Unit tests for the Task service: RN02 and RN04 to RN07."""

from datetime import date
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from app.errors import InvalidReferenceError, NotFoundError
from app.models import Task, TaskPriority, TaskStatus
from app.repositories.task import TaskRepository
from app.schemas.common import Pagination
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task import TaskService
from app.services.task_group import TaskGroupService
from tests.factories import create_task, create_task_group

STATUSES = list(TaskStatus)


@pytest.fixture
def service(session: Session) -> TaskService:
    return TaskService(session)


def update_data(**fields: Any) -> TaskUpdate:
    """Build an update the way the API does, so only sent fields are tracked."""
    return TaskUpdate.model_validate(fields)


def stored(engine: Engine, task_id: Any) -> Task | None:
    """Read a task through a brand-new session, proving it was committed."""
    with Session(engine) as other_session:
        return other_session.get(Task, task_id)


# --- create (RN02, RN05, RN07) ---------------------------------------------------


def test_create_saves_the_task_in_the_group_with_the_defaults(
    service: TaskService, session: Session, engine: Engine
) -> None:
    group = create_task_group(session)

    task = service.create(group.id, TaskCreate(title="Write report"))

    saved = stored(engine, task.id)
    assert saved is not None
    assert saved.task_group_id == group.id
    assert saved.title == "Write report"
    assert saved.status is TaskStatus.PENDING
    assert saved.priority is TaskPriority.MEDIUM
    assert saved.completed_at is None
    assert saved.created_at == saved.updated_at


def test_create_keeps_every_value_given(service: TaskService, session: Session) -> None:
    group = create_task_group(session)

    task = service.create(
        group.id,
        TaskCreate(
            title="Write report",
            description="quarterly",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.HIGH,
            due_date=date(2026, 12, 31),
        ),
    )

    assert task.description == "quarterly"
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.priority is TaskPriority.HIGH
    assert task.due_date == date(2026, 12, 31)
    assert task.completed_at is None


def test_create_in_an_unknown_group_is_not_found_and_creates_nothing(
    service: TaskService, session: Session
) -> None:
    missing = uuid4()

    with pytest.raises(NotFoundError) as error:
        service.create(missing, TaskCreate(title="Orphan"))

    assert error.value.status_code == 404
    assert str(missing) in error.value.detail
    assert TaskRepository(session).list_page(group_id=None, offset=0, limit=10)[1] == 0


def test_a_task_created_as_completed_gets_completed_at(
    service: TaskService, session: Session
) -> None:
    group = create_task_group(session)

    task = service.create(
        group.id, TaskCreate(title="Done already", status=TaskStatus.COMPLETED)
    )

    assert task.completed_at == task.created_at


@pytest.mark.parametrize("status", [TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
def test_a_task_created_as_open_has_no_completed_at(
    service: TaskService, session: Session, status: TaskStatus
) -> None:
    group = create_task_group(session)

    assert (
        service.create(group.id, TaskCreate(title="x", status=status)).completed_at
        is None
    )


# --- get ---------------------------------------------------------------------------


def test_get_returns_the_task(service: TaskService, session: Session) -> None:
    task = create_task(session)

    assert service.get(task.id) is task


def test_get_of_an_unknown_id_is_not_found(service: TaskService) -> None:
    missing = uuid4()

    with pytest.raises(NotFoundError) as error:
        service.get(missing)

    assert str(missing) in error.value.detail
    assert "Task group" not in error.value.detail


# --- list_for_group -------------------------------------------------------------------


def test_list_returns_only_the_tasks_of_the_group(
    service: TaskService, session: Session
) -> None:
    work = create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    create_task(session, work, title="Report")
    create_task(session, home, title="Laundry")

    tasks, total = service.list_for_group(work.id, Pagination())

    assert [task.title for task in tasks] == ["Report"]
    assert total == 1


def test_list_paginates(service: TaskService, session: Session) -> None:
    group = create_task_group(session)
    for _ in range(7):
        create_task(session, group)

    tasks, total = service.list_for_group(group.id, Pagination(page=3, page_size=3))

    assert (len(tasks), total) == (1, 7)


def test_list_of_a_group_without_tasks_is_empty(
    service: TaskService, session: Session
) -> None:
    group = create_task_group(session)

    tasks, total = service.list_for_group(group.id, Pagination())

    assert (list(tasks), total) == ([], 0)


def test_list_of_an_unknown_group_is_not_found(service: TaskService) -> None:
    with pytest.raises(NotFoundError):
        service.list_for_group(uuid4(), Pagination())


# --- update: partial changes ----------------------------------------------------------


def test_update_changes_only_the_fields_sent(
    service: TaskService, session: Session
) -> None:
    task = create_task(
        session,
        title="Draft",
        description="original",
        priority=TaskPriority.LOW,
        due_date=date(2026, 1, 1),
    )

    service.update(task.id, update_data(title="Final"))

    assert task.title == "Final"
    assert task.description == "original"
    assert task.priority is TaskPriority.LOW
    assert task.due_date == date(2026, 1, 1)
    assert task.status is TaskStatus.PENDING


def test_update_can_change_every_field_at_once(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)

    service.update(
        task.id,
        update_data(
            title="New",
            description="text",
            status="in_progress",
            priority="high",
            due_date="2027-01-31",
        ),
    )

    assert (task.title, task.description) == ("New", "text")
    assert (task.status, task.priority) == (TaskStatus.IN_PROGRESS, TaskPriority.HIGH)
    assert task.due_date == date(2027, 1, 31)


def test_update_can_clear_the_description_and_the_due_date(
    service: TaskService, session: Session
) -> None:
    task = create_task(session, description="text", due_date=date(2026, 1, 1))

    service.update(task.id, update_data(description=None, due_date=None))

    assert (task.description, task.due_date) == (None, None)


def test_update_is_committed(
    service: TaskService, session: Session, engine: Engine
) -> None:
    task = create_task(session)

    service.update(task.id, update_data(title="Changed"))

    saved = stored(engine, task.id)
    assert saved is not None
    assert saved.title == "Changed"


def test_update_moves_updated_at_forward_and_keeps_created_at(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    created_at, first_updated_at = task.created_at, task.updated_at

    service.update(task.id, update_data(title="Changed"))

    assert task.created_at == created_at
    assert task.updated_at > first_updated_at


def test_an_empty_update_changes_nothing(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    before = task.updated_at

    result = service.update(task.id, update_data())

    assert result is task
    assert task.updated_at == before


def test_update_of_an_unknown_task_is_not_found(service: TaskService) -> None:
    with pytest.raises(NotFoundError):
        service.update(uuid4(), update_data(title="x"))


# --- update: status transitions (RN06, RN07) ------------------------------------------


@pytest.mark.parametrize("target", STATUSES)
@pytest.mark.parametrize("origin", STATUSES)
def test_every_status_transition_is_allowed(
    service: TaskService, session: Session, origin: TaskStatus, target: TaskStatus
) -> None:
    task = service.create(
        create_task_group(session).id, TaskCreate(title="x", status=origin)
    )

    service.update(task.id, update_data(status=target.value))

    assert task.status is target


@pytest.mark.parametrize("target", STATUSES)
@pytest.mark.parametrize("origin", STATUSES)
def test_completed_at_follows_the_status(
    service: TaskService, session: Session, origin: TaskStatus, target: TaskStatus
) -> None:
    task = service.create(
        create_task_group(session).id, TaskCreate(title="x", status=origin)
    )
    original_completed_at = task.completed_at

    service.update(task.id, update_data(status=target.value))

    if target is TaskStatus.COMPLETED and origin is TaskStatus.COMPLETED:
        assert task.completed_at == original_completed_at
    elif target is TaskStatus.COMPLETED:
        assert task.completed_at is not None
    else:
        assert task.completed_at is None


def test_completing_a_task_sets_completed_at_to_now(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    assert task.completed_at is None

    service.update(task.id, update_data(status="completed"))

    assert task.completed_at is not None
    assert task.completed_at > task.created_at


def test_reopening_a_task_clears_completed_at(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    service.update(task.id, update_data(status="completed"))

    service.update(task.id, update_data(status="pending"))

    assert task.completed_at is None


def test_completing_an_already_completed_task_keeps_the_original_time(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    service.update(task.id, update_data(status="completed"))
    first = task.completed_at

    service.update(task.id, update_data(status="completed", title="Renamed"))

    assert task.completed_at == first


def test_changing_other_fields_of_a_completed_task_keeps_completed_at(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)
    service.update(task.id, update_data(status="completed"))
    first = task.completed_at

    service.update(task.id, update_data(priority="high"))

    assert task.completed_at == first
    assert task.status is TaskStatus.COMPLETED


# --- update: moving between groups (RN04) ---------------------------------------------


def test_a_task_can_be_moved_to_another_group(
    service: TaskService, session: Session
) -> None:
    task = create_task(session, title="Movable")
    other = create_task_group(session, name="Other")

    service.update(task.id, update_data(task_group_id=str(other.id)))

    assert task.task_group_id == other.id
    assert task.title == "Movable"


def test_moving_a_task_to_its_own_group_is_harmless(
    service: TaskService, session: Session
) -> None:
    task = create_task(session)

    service.update(task.id, update_data(task_group_id=str(task.task_group_id)))

    assert task.task_group_id is not None


def test_moving_a_task_to_an_unknown_group_is_an_invalid_reference(
    service: TaskService, session: Session
) -> None:
    task = create_task(session, title="Stays")
    original_group = task.task_group_id

    with pytest.raises(InvalidReferenceError) as error:
        service.update(
            task.id, update_data(task_group_id=str(uuid4()), title="Changed")
        )

    assert error.value.status_code == 422
    assert error.value.detail.startswith("task_group_id: ")
    session.refresh(task)
    assert task.task_group_id == original_group
    assert task.title == "Stays"


def test_a_task_moved_out_of_a_group_no_longer_blocks_its_deletion(
    service: TaskService, session: Session
) -> None:
    origin = create_task_group(session, name="Origin")
    destination = create_task_group(session, name="Destination")
    task = create_task(session, origin)
    service.update(task.id, update_data(task_group_id=str(destination.id)))

    TaskGroupService(session).delete(origin.id)

    assert TaskRepository(session).count_for_group(destination.id) == 1


# --- delete ---------------------------------------------------------------------------


def test_delete_removes_the_task(
    service: TaskService, session: Session, engine: Engine
) -> None:
    task = create_task(session)
    task_id = task.id

    service.delete(task_id)

    assert stored(engine, task_id) is None
    with pytest.raises(NotFoundError):
        service.get(task_id)


def test_delete_of_an_unknown_task_is_not_found(service: TaskService) -> None:
    with pytest.raises(NotFoundError):
        service.delete(uuid4())


def test_a_group_can_be_deleted_after_its_last_task_is(
    service: TaskService, session: Session
) -> None:
    group = create_task_group(session)
    task = create_task(session, group)
    group_id = group.id
    service.delete(task.id)

    TaskGroupService(session).delete(group_id)

    with pytest.raises(NotFoundError):
        TaskGroupService(session).get(group_id)
