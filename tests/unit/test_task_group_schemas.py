"""Unit tests for the task group schemas (RF01, RF04, RN08)."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.base import GENERATED_FIELDS
from app.schemas.task_group import TaskGroupCreate, TaskGroupRead, TaskGroupUpdate
from tests.factories import build_task_group


def invalid(model: type[Any], payload: dict[str, Any], field: str) -> None:
    """Assert that ``payload`` is rejected and the error points at ``field``."""
    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)
    assert field in {
        str(location) for e in error.value.errors() for location in e["loc"]
    }


# --- TaskGroupCreate -----------------------------------------------------------


def test_create_accepts_only_a_name() -> None:
    data = TaskGroupCreate.model_validate({"name": "Work"})

    assert (data.name, data.description) == ("Work", None)


def test_create_accepts_a_name_and_a_description() -> None:
    data = TaskGroupCreate.model_validate({"name": "Work", "description": "Job stuff"})

    assert data.description == "Job stuff"


def test_create_strips_surrounding_spaces() -> None:
    data = TaskGroupCreate.model_validate({"name": "  Work  ", "description": " x "})

    assert (data.name, data.description) == ("Work", "x")


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_create_rejects_a_blank_name(name: str) -> None:
    invalid(TaskGroupCreate, {"name": name}, "name")


def test_create_requires_a_name() -> None:
    invalid(TaskGroupCreate, {}, "name")
    invalid(TaskGroupCreate, {"description": "only this"}, "name")


@pytest.mark.parametrize("name", [None, 5, ["Work"], {"a": 1}])
def test_create_rejects_a_name_that_is_not_text(name: object) -> None:
    invalid(TaskGroupCreate, {"name": name}, "name")


def test_create_name_length_limit_is_100() -> None:
    assert TaskGroupCreate.model_validate({"name": "x" * 100}).name == "x" * 100
    invalid(TaskGroupCreate, {"name": "x" * 101}, "name")


def test_create_description_length_limit_is_500() -> None:
    ok = TaskGroupCreate.model_validate({"name": "a", "description": "d" * 500})

    assert ok.description == "d" * 500
    invalid(TaskGroupCreate, {"name": "a", "description": "d" * 501}, "description")


def test_create_rejects_unknown_fields() -> None:
    invalid(TaskGroupCreate, {"name": "Work", "color": "red"}, "color")


def test_create_rejects_the_internal_normalized_name() -> None:
    invalid(
        TaskGroupCreate, {"name": "Work", "normalized_name": "work"}, "normalized_name"
    )


@pytest.mark.parametrize("field", sorted(GENERATED_FIELDS))
def test_create_ignores_generated_fields_even_when_invalid(field: str) -> None:
    data = TaskGroupCreate.model_validate({"name": "Work", field: "not-valid-at-all"})

    assert data.model_dump() == {"name": "Work", "description": None}


def test_create_rejects_a_body_that_is_not_an_object() -> None:
    with pytest.raises(ValidationError):
        TaskGroupCreate.model_validate(["Work"])


# --- TaskGroupUpdate -----------------------------------------------------------


def test_update_accepts_an_empty_body() -> None:
    data = TaskGroupUpdate.model_validate({})

    assert data.model_fields_set == set()


def test_update_tracks_which_fields_were_sent() -> None:
    only_name = TaskGroupUpdate.model_validate({"name": "New"})
    only_description = TaskGroupUpdate.model_validate({"description": "text"})

    assert only_name.model_fields_set == {"name"}
    assert only_description.model_fields_set == {"description"}


def test_update_can_clear_the_description_with_null() -> None:
    data = TaskGroupUpdate.model_validate({"description": None})

    assert data.model_fields_set == {"description"}
    assert data.description is None


def test_update_cannot_set_the_name_to_null() -> None:
    invalid(TaskGroupUpdate, {"name": None}, "name")


@pytest.mark.parametrize("name", ["", "   "])
def test_update_rejects_a_blank_name(name: str) -> None:
    invalid(TaskGroupUpdate, {"name": name}, "name")


def test_update_applies_the_same_limits_as_create() -> None:
    invalid(TaskGroupUpdate, {"name": "x" * 101}, "name")
    invalid(TaskGroupUpdate, {"description": "d" * 501}, "description")
    assert TaskGroupUpdate.model_validate({"name": "x" * 100}).name == "x" * 100


def test_update_strips_surrounding_spaces() -> None:
    assert TaskGroupUpdate.model_validate({"name": "  New "}).name == "New"


def test_update_rejects_unknown_fields_but_ignores_generated_ones() -> None:
    invalid(TaskGroupUpdate, {"color": "red"}, "color")

    data = TaskGroupUpdate.model_validate({"name": "New", "id": "ignored"})
    assert data.model_dump(exclude_unset=True) == {"name": "New"}


# --- TaskGroupRead -------------------------------------------------------------


def test_read_is_built_from_a_table_row() -> None:
    group = build_task_group(name="Work", description="Job")

    data = TaskGroupRead.model_validate(group)

    assert (data.id, data.name, data.description) == (group.id, "Work", "Job")


def test_read_exposes_exactly_the_public_fields() -> None:
    data = TaskGroupRead.model_validate(build_task_group())

    assert set(data.model_dump()) == {
        "id",
        "name",
        "description",
        "created_at",
        "updated_at",
    }


def test_read_never_exposes_the_normalized_name() -> None:
    payload = json.loads(
        TaskGroupRead.model_validate(build_task_group()).model_dump_json()
    )

    assert "normalized_name" not in payload


def test_read_serializes_datetimes_as_iso_8601_utc() -> None:
    payload = json.loads(
        TaskGroupRead.model_validate(build_task_group()).model_dump_json()
    )

    assert payload["created_at"].endswith("Z")
    assert payload["updated_at"].endswith("Z")
    assert isinstance(payload["id"], str)
