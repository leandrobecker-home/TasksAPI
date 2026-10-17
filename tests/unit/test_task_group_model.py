"""Unit tests for the TaskGroup table model (RT03, RN01)."""

from datetime import UTC, timedelta
from uuid import UUID

import pytest
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import TaskGroup
from app.models.task_group import normalize_name
from tests.factories import build_task_group, create_task_group


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Trabalho", "trabalho"),
        ("  Trabalho  ", "trabalho"),
        ("TRABALHO", "trabalho"),
        ("Ação", "ação"),
        ("AÇÃO", "ação"),
        ("Straße", "strasse"),
        ("STRASSE", "strasse"),
        ("Work  Items", "work  items"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_normalize_name_treats_composed_and_decomposed_accents_alike() -> None:
    composed = "Ação"
    decomposed = "Ação"

    assert composed != decomposed
    assert normalize_name(composed) == normalize_name(decomposed)


def test_table_and_columns(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("task_groups")}

    assert columns == {
        "id",
        "name",
        "normalized_name",
        "description",
        "created_at",
        "updated_at",
    }


def test_normalized_name_has_a_unique_index(engine: Engine) -> None:
    indexes = inspect(engine).get_indexes("task_groups")

    unique_on_normalized_name = [
        index
        for index in indexes
        if index["column_names"] == ["normalized_name"] and index["unique"]
    ]
    assert len(unique_on_normalized_name) == 1


def test_a_new_group_gets_generated_fields(session: Session) -> None:
    group = create_task_group(session, name="Work")

    assert isinstance(group.id, UUID)
    assert group.description is None
    assert group.created_at == group.updated_at


def test_normalized_name_is_derived_on_insert(session: Session) -> None:
    group = create_task_group(session, name="  Ação Rápida ")

    assert group.name == "  Ação Rápida "
    assert group.normalized_name == "ação rápida"


def test_normalized_name_follows_a_rename(session: Session) -> None:
    group = create_task_group(session, name="Home")

    group.name = "Office"
    session.commit()
    session.refresh(group)

    assert group.normalized_name == "office"


def test_names_that_differ_only_in_case_collide(session: Session) -> None:
    create_task_group(session, name="Trabalho")

    with pytest.raises(IntegrityError):
        create_task_group(session, name="TRABALHO")


def test_names_that_differ_only_in_accented_case_collide(session: Session) -> None:
    create_task_group(session, name="Ação")

    with pytest.raises(IntegrityError):
        create_task_group(session, name="AÇÃO")


def test_names_that_differ_only_in_surrounding_spaces_collide(
    session: Session,
) -> None:
    create_task_group(session, name="Work")

    with pytest.raises(IntegrityError):
        create_task_group(session, name="  Work  ")


def test_different_names_do_not_collide(session: Session) -> None:
    create_task_group(session, name="Work")
    other = create_task_group(session, name="Home")

    assert other.normalized_name == "home"


def test_datetimes_round_trip_as_utc(engine: Engine, session: Session) -> None:
    group = create_task_group(session)
    group_id = group.id

    with Session(engine) as other_session:
        reloaded = other_session.get(TaskGroup, group_id)

    assert reloaded is not None
    assert reloaded.created_at.tzinfo is not None
    assert reloaded.created_at.utcoffset() == timedelta(0)
    assert reloaded.created_at == group.created_at
    assert reloaded.created_at.tzinfo == UTC


def test_updated_at_changes_on_update_and_created_at_does_not(
    session: Session,
) -> None:
    group = create_task_group(session)
    created_at = group.created_at
    first_updated_at = group.updated_at

    group.description = "now with a description"
    session.commit()
    session.refresh(group)

    assert group.created_at == created_at
    assert group.updated_at > first_updated_at


def test_updated_at_is_untouched_when_nothing_changes(session: Session) -> None:
    group = create_task_group(session)
    before = group.updated_at

    session.commit()
    session.refresh(group)

    assert group.updated_at == before


def test_factories_produce_unique_names() -> None:
    assert build_task_group().name != build_task_group().name


def test_factory_overrides_win() -> None:
    group = build_task_group(name="Fixed", description="text")

    assert (group.name, group.description) == ("Fixed", "text")
