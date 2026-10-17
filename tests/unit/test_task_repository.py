"""Unit tests for the Task repository (RT02, RT03, RN02)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.errors import InvalidReferenceError
from app.models import Task, TaskStatus
from app.repositories.task import UNKNOWN_GROUP_DETAIL, TaskRepository
from tests.factories import build_task, create_task, create_task_group

START = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def repository(session: Session) -> TaskRepository:
    return TaskRepository(session)


def titles(tasks: object) -> list[str]:
    return [task.title for task in tasks]  # type: ignore[attr-defined]


# --- add, get, save and delete -------------------------------------------------------


def test_add_persists_the_task(repository: TaskRepository, session: Session) -> None:
    group = create_task_group(session)

    task = repository.add(build_task(group, title="Write report"))
    session.commit()

    assert repository.get(task.id) is task
    assert task.status is TaskStatus.PENDING


def test_get_returns_none_for_an_unknown_id(repository: TaskRepository) -> None:
    assert repository.get(uuid4()) is None


def test_save_applies_the_changes(repository: TaskRepository, session: Session) -> None:
    task = create_task(session, title="Draft")

    task.title = "Final"
    task.status = TaskStatus.COMPLETED
    repository.save(task)
    session.commit()
    session.refresh(task)

    assert (task.title, task.status) == ("Final", TaskStatus.COMPLETED)


def test_delete_removes_the_task(repository: TaskRepository, session: Session) -> None:
    task = create_task(session)
    task_id = task.id

    repository.delete(task)
    session.commit()

    assert repository.get(task_id) is None


# --- the task group must exist (RN02) -------------------------------------------------


def test_add_to_an_unknown_group_is_an_invalid_reference(
    repository: TaskRepository,
) -> None:
    orphan = Task(task_group_id=uuid4(), title="Orphan")

    with pytest.raises(InvalidReferenceError) as error:
        repository.add(orphan)

    assert error.value.detail == UNKNOWN_GROUP_DETAIL
    assert error.value.status_code == 422


def test_session_stays_usable_after_an_invalid_reference(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    with pytest.raises(InvalidReferenceError):
        repository.add(Task(task_group_id=uuid4(), title="Orphan"))

    repository.add(build_task(group, title="Fine"))
    session.commit()

    assert repository.list_page(group_id=group.id, offset=0, limit=10)[1] == 1


def test_moving_a_task_to_another_group(
    repository: TaskRepository, session: Session
) -> None:
    task = create_task(session)
    other_group = create_task_group(session)

    task.task_group_id = other_group.id
    repository.save(task)
    session.commit()

    assert repository.count_for_group(other_group.id) == 1


def test_moving_a_task_to_an_unknown_group_is_an_invalid_reference(
    repository: TaskRepository, session: Session
) -> None:
    task = create_task(session)

    task.task_group_id = uuid4()

    with pytest.raises(InvalidReferenceError):
        repository.save(task)


def test_other_integrity_errors_are_not_reported_as_invalid_references(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    nameless = build_task(group)
    nameless.title = None  # type: ignore[assignment]

    with pytest.raises(IntegrityError, match="NOT NULL"):
        repository.add(nameless)


# --- list_page ------------------------------------------------------------------------


def test_list_page_of_an_empty_table(repository: TaskRepository) -> None:
    page, total = repository.list_page(group_id=None, offset=0, limit=20)

    assert (list(page), total) == ([], 0)


def test_list_page_returns_only_the_tasks_of_the_given_group(
    repository: TaskRepository, session: Session
) -> None:
    work = create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    create_task(session, work, title="Report")
    create_task(session, work, title="Meeting")
    create_task(session, home, title="Laundry")

    page, total = repository.list_page(group_id=work.id, offset=0, limit=20)

    assert sorted(titles(page)) == ["Meeting", "Report"]
    assert total == 2


def test_list_page_without_a_group_returns_every_task(
    repository: TaskRepository, session: Session
) -> None:
    create_task(session)
    create_task(session)
    create_task(session)

    _, total = repository.list_page(group_id=None, offset=0, limit=20)

    assert total == 3


def test_list_page_of_a_group_with_no_tasks(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    create_task(session)

    page, total = repository.list_page(group_id=group.id, offset=0, limit=20)

    assert (list(page), total) == ([], 0)


def test_list_page_puts_the_newest_tasks_first(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    for days, title in [(0, "oldest"), (2, "newest"), (1, "middle")]:
        create_task(
            session, group, title=title, created_at=START + timedelta(days=days)
        )

    page, _ = repository.list_page(group_id=group.id, offset=0, limit=20)

    assert titles(page) == ["newest", "middle", "oldest"]


def test_list_page_slices_and_reports_the_overall_total(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    for number in range(25):
        create_task(
            session,
            group,
            title=f"Task {number:02d}",
            created_at=START + timedelta(minutes=number),
        )

    first, total = repository.list_page(group_id=group.id, offset=0, limit=10)
    last, _ = repository.list_page(group_id=group.id, offset=20, limit=10)
    beyond, beyond_total = repository.list_page(group_id=group.id, offset=99, limit=10)

    assert (len(first), total) == (10, 25)
    assert titles(first)[0] == "Task 24"
    assert titles(last) == [f"Task {number:02d}" for number in (4, 3, 2, 1, 0)]
    assert (list(beyond), beyond_total) == ([], 25)


def test_pages_do_not_overlap_when_creation_times_tie(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    for number in range(12):
        create_task(session, group, title=f"T{number}", created_at=START)

    seen: list[str] = []
    for offset in (0, 4, 8):
        page, _ = repository.list_page(group_id=group.id, offset=offset, limit=4)
        seen += titles(page)

    assert len(seen) == 12
    assert len(set(seen)) == 12


# --- count_for_group ------------------------------------------------------------------


def test_count_for_group(repository: TaskRepository, session: Session) -> None:
    work = create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    empty = create_task_group(session, name="Empty")
    create_task(session, work)
    create_task(session, work)
    create_task(session, home)

    assert repository.count_for_group(work.id) == 2
    assert repository.count_for_group(home.id) == 1
    assert repository.count_for_group(empty.id) == 0


def test_count_for_an_unknown_group_is_zero(repository: TaskRepository) -> None:
    assert repository.count_for_group(uuid4()) == 0


def test_count_drops_when_a_task_is_deleted(
    repository: TaskRepository, session: Session
) -> None:
    group = create_task_group(session)
    task = create_task(session, group)

    repository.delete(task)
    session.commit()

    assert repository.count_for_group(group.id) == 0
