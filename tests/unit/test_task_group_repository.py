"""Unit tests for the TaskGroup repository (RT03, RN01)."""

import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel

from app.db import create_db_engine
from app.errors import ConflictError
from app.repositories.task_group import DUPLICATE_NAME_DETAIL, TaskGroupRepository
from tests.factories import build_task_group, create_task_group


@pytest.fixture
def repository(session: Session) -> TaskGroupRepository:
    return TaskGroupRepository(session)


@pytest.fixture
def file_engine(tmp_path: Path) -> Iterator[Engine]:
    """A file database, whose connections are independent (unlike in-memory)."""
    engine = create_db_engine(f"sqlite:///{tmp_path / 'race.db'}")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


# --- add, get and get_by_name -------------------------------------------------


def test_add_persists_the_group(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = repository.add(build_task_group(name="Work"))
    session.commit()

    assert repository.get(group.id) is group
    assert group.normalized_name == "work"


def test_get_returns_none_for_an_unknown_id(repository: TaskGroupRepository) -> None:
    assert repository.get(uuid4()) is None


@pytest.mark.parametrize("lookup", ["Trabalho", "trabalho", "TRABALHO", "  Trabalho "])
def test_get_by_name_ignores_case_and_surrounding_spaces(
    repository: TaskGroupRepository, session: Session, lookup: str
) -> None:
    group = create_task_group(session, name="Trabalho")

    assert repository.get_by_name(lookup) is group


def test_get_by_name_ignores_the_case_of_accented_letters(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = create_task_group(session, name="Ação")

    assert repository.get_by_name("AÇÃO") is group


def test_get_by_name_returns_none_when_no_group_matches(
    repository: TaskGroupRepository, session: Session
) -> None:
    create_task_group(session, name="Work")

    assert repository.get_by_name("Home") is None
    assert repository.get_by_name("Wor") is None


# --- unique name (RN01) --------------------------------------------------------


@pytest.mark.parametrize("duplicate", ["Work", "WORK", "work", "  Work  "])
def test_add_rejects_a_duplicate_name(
    repository: TaskGroupRepository, session: Session, duplicate: str
) -> None:
    create_task_group(session, name="Work")

    with pytest.raises(ConflictError) as error:
        repository.add(build_task_group(name=duplicate))

    assert error.value.detail == DUPLICATE_NAME_DETAIL
    assert error.value.status_code == 409


def test_add_rejects_a_duplicate_with_accents(
    repository: TaskGroupRepository, session: Session
) -> None:
    create_task_group(session, name="Ação")

    with pytest.raises(ConflictError):
        repository.add(build_task_group(name="AÇÃO"))


def test_session_stays_usable_after_a_conflict(
    repository: TaskGroupRepository, session: Session
) -> None:
    create_task_group(session, name="Work")
    with pytest.raises(ConflictError):
        repository.add(build_task_group(name="work"))

    repository.add(build_task_group(name="Home"))
    session.commit()

    assert repository.get_by_name("Home") is not None


def test_save_rejects_renaming_to_another_groups_name(
    repository: TaskGroupRepository, session: Session
) -> None:
    create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")

    home.name = "WORK"
    with pytest.raises(ConflictError):
        repository.save(home)


def test_save_allows_a_group_to_keep_or_recase_its_own_name(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    group.name = "WORK"
    repository.save(group)
    session.commit()
    session.refresh(group)

    assert (group.name, group.normalized_name) == ("WORK", "work")


def test_save_applies_the_changes(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = create_task_group(session, name="Work")

    group.description = "everything for the job"
    repository.save(group)
    session.commit()
    session.refresh(group)

    assert group.description == "everything for the job"


def test_duplicate_name_is_caught_even_when_the_check_came_first(
    file_engine: Engine,
) -> None:
    """Two requests both see the name as free; the database stops the second."""
    with Session(file_engine) as first, Session(file_engine) as second:
        first_repository = TaskGroupRepository(first)
        second_repository = TaskGroupRepository(second)

        assert first_repository.get_by_name("Race") is None
        assert second_repository.get_by_name("Race") is None

        first_repository.add(build_task_group(name="Race"))
        first.commit()

        with pytest.raises(ConflictError):
            second_repository.add(build_task_group(name="race"))


def test_concurrent_creations_of_the_same_name_create_exactly_one(
    file_engine: Engine,
) -> None:
    attempts = 8
    barrier = threading.Barrier(attempts)

    def create(_: int) -> str:
        with Session(file_engine) as session:
            barrier.wait(timeout=10)
            try:
                TaskGroupRepository(session).add(build_task_group(name="Same Name"))
                session.commit()
            except ConflictError:
                return "conflict"
            return "created"

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        outcomes = list(pool.map(create, range(attempts)))

    assert outcomes.count("created") == 1
    assert outcomes.count("conflict") == attempts - 1


# --- delete ----------------------------------------------------------------------


def test_delete_removes_the_group(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = create_task_group(session)
    group_id = group.id

    repository.delete(group)
    session.commit()

    assert repository.get(group_id) is None


def test_a_deleted_name_can_be_used_again(
    repository: TaskGroupRepository, session: Session
) -> None:
    group = create_task_group(session, name="Temporary")
    repository.delete(group)
    session.commit()

    again = repository.add(build_task_group(name="Temporary"))

    assert again.normalized_name == "temporary"


# --- list_page ---------------------------------------------------------------------


def names(groups: object) -> list[str]:
    return [group.name for group in groups]  # type: ignore[attr-defined]


def test_list_page_of_an_empty_table(repository: TaskGroupRepository) -> None:
    page, total = repository.list_page(search=None, offset=0, limit=20)

    assert (list(page), total) == ([], 0)


def test_list_page_orders_by_name_ignoring_case(
    repository: TaskGroupRepository, session: Session
) -> None:
    for name in ["banana", "Cherry", "apple", "Banana split"]:
        create_task_group(session, name=name)

    page, total = repository.list_page(search=None, offset=0, limit=20)

    assert names(page) == ["apple", "banana", "Banana split", "Cherry"]
    assert total == 4


def test_list_page_slices_and_reports_the_overall_total(
    repository: TaskGroupRepository, session: Session
) -> None:
    for number in range(1, 26):
        create_task_group(session, name=f"Group {number:02d}")

    first, total = repository.list_page(search=None, offset=0, limit=10)
    last, _ = repository.list_page(search=None, offset=20, limit=10)
    beyond, beyond_total = repository.list_page(search=None, offset=100, limit=10)

    assert (len(first), total) == (10, 25)
    assert names(first)[0] == "Group 01"
    assert names(last) == [f"Group {number}" for number in range(21, 26)]
    assert (list(beyond), beyond_total) == ([], 25)


@pytest.mark.parametrize("search", ["work", "WORK", "  Work ", "ork"])
def test_search_ignores_case_and_surrounding_spaces(
    repository: TaskGroupRepository, session: Session, search: str
) -> None:
    create_task_group(session, name="Homework")
    create_task_group(session, name="Leisure")

    page, total = repository.list_page(search=search, offset=0, limit=20)

    assert (names(page), total) == (["Homework"], 1)


def test_search_ignores_the_case_of_accented_letters(
    repository: TaskGroupRepository, session: Session
) -> None:
    create_task_group(session, name="Ação rápida")
    create_task_group(session, name="Other")

    page, _ = repository.list_page(search="AÇÃO", offset=0, limit=20)

    assert names(page) == ["Ação rápida"]


def test_search_total_counts_only_the_matches(
    repository: TaskGroupRepository, session: Session
) -> None:
    for number in range(1, 6):
        create_task_group(session, name=f"Match {number}")
    create_task_group(session, name="Unrelated")

    page, total = repository.list_page(search="match", offset=0, limit=2)

    assert (len(page), total) == (2, 5)


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_search_is_treated_as_absent(
    repository: TaskGroupRepository, session: Session, blank: str
) -> None:
    create_task_group(session, name="One")
    create_task_group(session, name="Two")

    _, total = repository.list_page(search=blank, offset=0, limit=20)

    assert total == 2


@pytest.mark.parametrize("wildcard", ["%", "_", "100%"])
def test_search_treats_wildcards_literally(
    repository: TaskGroupRepository, session: Session, wildcard: str
) -> None:
    create_task_group(session, name="Plain")
    create_task_group(session, name="100% done")
    create_task_group(session, name="snake_case")

    page, _ = repository.list_page(search=wildcard, offset=0, limit=20)

    assert "Plain" not in names(page)
    expected = {"%": ["100% done"], "_": ["snake_case"], "100%": ["100% done"]}
    assert names(page) == expected[wildcard]


# --- other integrity errors are not disguised as name conflicts -------------------


def test_other_integrity_errors_are_not_reported_as_conflicts(
    engine: Engine, session: Session
) -> None:
    existing = create_task_group(session, name="Work")

    with Session(engine) as other_session:
        clash = build_task_group(name="Another", id=existing.id)
        with pytest.raises(IntegrityError):
            TaskGroupRepository(other_session).add(clash)
