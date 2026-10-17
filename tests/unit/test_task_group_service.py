"""Unit tests for the TaskGroup service: RN01 and the group life cycle."""

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from app.errors import ConflictError, NotFoundError
from app.models import TaskGroup
from app.repositories.task import TaskRepository
from app.repositories.task_group import GROUP_HAS_TASKS_DETAIL
from app.schemas.common import Pagination
from app.schemas.task_group import TaskGroupCreate, TaskGroupUpdate
from app.services.task_group import TaskGroupService
from tests.factories import create_task, create_task_group


@pytest.fixture
def service(session: Session) -> TaskGroupService:
    return TaskGroupService(session)


def update_data(**fields: Any) -> TaskGroupUpdate:
    """Build an update the way the API does, so only sent fields are tracked."""
    return TaskGroupUpdate.model_validate(fields)


def stored(engine: Engine, group_id: Any) -> TaskGroup | None:
    """Read a group through a brand-new session, proving it was committed."""
    with Session(engine) as other_session:
        return other_session.get(TaskGroup, group_id)


# --- create ------------------------------------------------------------------------


def test_create_saves_the_group_with_its_generated_fields(
    service: TaskGroupService, engine: Engine
) -> None:
    group = service.create(TaskGroupCreate(name="Work", description="Job"))

    saved = stored(engine, group.id)
    assert saved is not None
    assert (saved.name, saved.description) == ("Work", "Job")
    assert saved.created_at == saved.updated_at


def test_create_without_a_description(service: TaskGroupService) -> None:
    assert service.create(TaskGroupCreate(name="Work")).description is None


@pytest.mark.parametrize("duplicate", ["Work", "work", "WORK"])
def test_create_rejects_a_duplicate_name_ignoring_case(
    service: TaskGroupService, duplicate: str
) -> None:
    service.create(TaskGroupCreate(name="Work"))

    with pytest.raises(ConflictError):
        service.create(TaskGroupCreate(name=duplicate))


def test_create_rejects_a_duplicate_name_with_accents(
    service: TaskGroupService,
) -> None:
    service.create(TaskGroupCreate(name="Ação"))

    with pytest.raises(ConflictError):
        service.create(TaskGroupCreate(name="AÇÃO"))


def test_a_rejected_create_leaves_nothing_behind(
    service: TaskGroupService,
) -> None:
    service.create(TaskGroupCreate(name="Work"))
    with pytest.raises(ConflictError):
        service.create(TaskGroupCreate(name="work", description="second"))

    _, total = service.list(search=None, pagination=Pagination())

    assert total == 1


def test_service_stays_usable_after_a_conflict(service: TaskGroupService) -> None:
    service.create(TaskGroupCreate(name="Work"))
    with pytest.raises(ConflictError):
        service.create(TaskGroupCreate(name="WORK"))

    assert service.create(TaskGroupCreate(name="Home")).name == "Home"


# --- get ---------------------------------------------------------------------------


def test_get_returns_the_group(service: TaskGroupService) -> None:
    created = service.create(TaskGroupCreate(name="Work"))

    assert service.get(created.id) is created


def test_get_of_an_unknown_id_is_not_found(service: TaskGroupService) -> None:
    missing = uuid4()

    with pytest.raises(NotFoundError) as error:
        service.get(missing)

    assert error.value.status_code == 404
    assert str(missing) in error.value.detail


# --- list --------------------------------------------------------------------------


def test_list_returns_a_page_and_the_total(
    service: TaskGroupService, session: Session
) -> None:
    for number in range(1, 8):
        create_task_group(session, name=f"Group {number}")

    groups, total = service.list(
        search=None, pagination=Pagination(page=2, page_size=3)
    )

    assert [group.name for group in groups] == ["Group 4", "Group 5", "Group 6"]
    assert total == 7


def test_list_filters_by_name(service: TaskGroupService, session: Session) -> None:
    create_task_group(session, name="Homework")
    create_task_group(session, name="Leisure")

    groups, total = service.list(search="HOME", pagination=Pagination())

    assert [group.name for group in groups] == ["Homework"]
    assert total == 1


# --- update ------------------------------------------------------------------------


def test_update_changes_only_the_fields_sent(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")

    service.update(group.id, update_data(name="Office"))

    assert (group.name, group.description) == ("Office", "original")


def test_update_can_change_only_the_description(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")

    service.update(group.id, update_data(description="changed"))

    assert (group.name, group.description) == ("Work", "changed")


def test_update_can_clear_the_description(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work", description="original")

    service.update(group.id, update_data(description=None))

    assert group.description is None


def test_update_is_committed(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    group = create_task_group(session, name="Work")

    service.update(group.id, update_data(name="Office"))

    saved = stored(engine, group.id)
    assert saved is not None
    assert saved.name == "Office"
    assert saved.normalized_name == "office"


def test_update_moves_updated_at_forward_and_keeps_created_at(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    created_at, first_updated_at = group.created_at, group.updated_at

    service.update(group.id, update_data(name="Office"))

    assert group.created_at == created_at
    assert group.updated_at > first_updated_at


def test_update_rejects_another_groups_name(
    service: TaskGroupService, session: Session
) -> None:
    create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")

    with pytest.raises(ConflictError):
        service.update(home.id, update_data(name="WORK"))


def test_a_rejected_update_keeps_the_old_name(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")
    home_id = home.id

    with pytest.raises(ConflictError):
        service.update(home_id, update_data(name="work"))

    saved = stored(engine, home_id)
    assert saved is not None
    assert saved.name == "Home"


@pytest.mark.parametrize("same", ["Work", "WORK", "work"])
def test_update_allows_a_group_to_keep_its_own_name(
    service: TaskGroupService, session: Session, same: str
) -> None:
    group = create_task_group(session, name="Work")

    result = service.update(group.id, update_data(name=same))

    assert result.name == same


def test_empty_update_changes_nothing(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    before = group.updated_at

    result = service.update(group.id, update_data())

    assert result is group
    assert group.updated_at == before


def test_update_of_an_unknown_id_is_not_found(service: TaskGroupService) -> None:
    with pytest.raises(NotFoundError):
        service.update(uuid4(), update_data(name="Anything"))


# --- delete ------------------------------------------------------------------------


def test_delete_removes_the_group(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    group = create_task_group(session)
    group_id = group.id

    service.delete(group_id)

    assert stored(engine, group_id) is None
    with pytest.raises(NotFoundError):
        service.get(group_id)


def test_delete_of_an_unknown_id_is_not_found(service: TaskGroupService) -> None:
    with pytest.raises(NotFoundError):
        service.delete(uuid4())


def test_a_deleted_name_can_be_used_again(service: TaskGroupService) -> None:
    group = service.create(TaskGroupCreate(name="Temporary"))
    service.delete(group.id)

    assert service.create(TaskGroupCreate(name="Temporary")).name == "Temporary"


# --- a group with tasks cannot be deleted (RN03) --------------------------------------


def test_delete_refuses_a_group_that_still_has_tasks(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    group = create_task_group(session, name="Work")
    create_task(session, group)
    group_id = group.id

    with pytest.raises(ConflictError) as error:
        service.delete(group_id)

    assert error.value.status_code == 409
    assert error.value.detail == GROUP_HAS_TASKS_DETAIL
    assert stored(engine, group_id) is not None


def test_a_refused_delete_keeps_every_task(
    service: TaskGroupService, session: Session
) -> None:
    group = create_task_group(session, name="Work")
    for _ in range(3):
        create_task(session, group)

    with pytest.raises(ConflictError):
        service.delete(group.id)

    assert TaskRepository(session).count_for_group(group.id) == 3


def test_delete_works_once_the_tasks_are_gone(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    group = create_task_group(session, name="Work")
    task = create_task(session, group)
    group_id = group.id
    with pytest.raises(ConflictError):
        service.delete(group_id)

    session.delete(task)
    session.commit()
    service.delete(group_id)

    assert stored(engine, group_id) is None


def test_tasks_of_another_group_do_not_block_the_delete(
    service: TaskGroupService, session: Session, engine: Engine
) -> None:
    empty = create_task_group(session, name="Empty")
    busy = create_task_group(session, name="Busy")
    create_task(session, busy)
    empty_id = empty.id

    service.delete(empty_id)

    assert stored(engine, empty_id) is None
    assert stored(engine, busy.id) is not None
