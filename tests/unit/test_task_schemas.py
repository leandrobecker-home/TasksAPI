"""Unit tests for the task schemas (RF06, RF12, RT05, RN05, RN08)."""

import json
from datetime import date, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import TaskPriority, TaskStatus
from app.schemas.base import GENERATED_FIELDS
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from tests.factories import build_task, build_task_group


def invalid(model: type[Any], payload: dict[str, Any], field: str) -> None:
    """Assert that ``payload`` is rejected and the error points at ``field``."""
    with pytest.raises(ValidationError) as error:
        model.model_validate(payload)
    assert field in {str(part) for e in error.value.errors() for part in e["loc"]}


# --- TaskCreate: defaults (RN05) ------------------------------------------------------


def test_create_needs_only_a_title() -> None:
    data = TaskCreate.model_validate({"title": "Write report"})

    assert data.title == "Write report"
    assert data.description is None
    assert data.due_date is None


def test_create_defaults_to_pending_and_medium() -> None:
    data = TaskCreate.model_validate({"title": "x"})

    assert data.status is TaskStatus.PENDING
    assert data.priority is TaskPriority.MEDIUM


def test_create_accepts_every_field() -> None:
    data = TaskCreate.model_validate(
        {
            "title": "Write report",
            "description": "quarterly",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-12-31",
        }
    )

    assert data.status is TaskStatus.IN_PROGRESS
    assert data.priority is TaskPriority.HIGH
    assert data.due_date == date(2026, 12, 31)


# --- TaskCreate: title and description ------------------------------------------------


def test_create_strips_surrounding_spaces() -> None:
    data = TaskCreate.model_validate({"title": "  Report  ", "description": " d "})

    assert (data.title, data.description) == ("Report", "d")


@pytest.mark.parametrize("title", ["", "   ", "\t\n"])
def test_create_rejects_a_blank_title(title: str) -> None:
    invalid(TaskCreate, {"title": title}, "title")


@pytest.mark.parametrize("title", [None, 5, ["x"]])
def test_create_rejects_a_title_that_is_not_text(title: object) -> None:
    invalid(TaskCreate, {"title": title}, "title")


def test_create_requires_a_title() -> None:
    invalid(TaskCreate, {}, "title")
    invalid(TaskCreate, {"description": "only this"}, "title")


def test_create_title_limit_is_200_characters() -> None:
    assert len(TaskCreate.model_validate({"title": "t" * 200}).title) == 200
    invalid(TaskCreate, {"title": "t" * 201}, "title")


def test_create_description_limit_is_2000_characters() -> None:
    ok = TaskCreate.model_validate({"title": "x", "description": "d" * 2000})

    assert ok.description == "d" * 2000
    invalid(TaskCreate, {"title": "x", "description": "d" * 2001}, "description")


# --- TaskCreate: enums ----------------------------------------------------------------


@pytest.mark.parametrize("status", ["bogus", "PENDING", "done", "", 1, None])
def test_create_rejects_a_status_outside_the_enum(status: object) -> None:
    invalid(TaskCreate, {"title": "x", "status": status}, "status")


@pytest.mark.parametrize("priority", ["urgent", "HIGH", "", 2, None])
def test_create_rejects_a_priority_outside_the_enum(priority: object) -> None:
    invalid(TaskCreate, {"title": "x", "priority": priority}, "priority")


@pytest.mark.parametrize("status", [member.value for member in TaskStatus])
def test_create_accepts_every_status(status: str) -> None:
    assert TaskCreate.model_validate({"title": "x", "status": status}).status == status


@pytest.mark.parametrize("priority", [member.value for member in TaskPriority])
def test_create_accepts_every_priority(priority: str) -> None:
    data = TaskCreate.model_validate({"title": "x", "priority": priority})

    assert data.priority == priority


# --- TaskCreate: due date (RT05) ------------------------------------------------------


@pytest.mark.parametrize(
    "due_date",
    [
        "31/12/2026",
        "2026-13-01",
        "2026-02-30",
        "2026-1-1",
        "tomorrow",
        "",
        "2026-12-31T00:00:00",
        "2026-12-31T10:30:00Z",
        20261231,
        0,
        1_767_225_600,
        True,
        ["2026-12-31"],
    ],
)
def test_create_rejects_a_due_date_that_is_not_yyyy_mm_dd(due_date: object) -> None:
    invalid(TaskCreate, {"title": "x", "due_date": due_date}, "due_date")


def test_create_accepts_a_leap_day_and_rejects_a_missing_one() -> None:
    ok = TaskCreate.model_validate({"title": "x", "due_date": "2028-02-29"})

    assert ok.due_date == date(2028, 2, 29)
    invalid(TaskCreate, {"title": "x", "due_date": "2027-02-29"}, "due_date")


def test_create_accepts_a_null_due_date() -> None:
    assert TaskCreate.model_validate({"title": "x", "due_date": None}).due_date is None


# --- TaskCreate: unknown and generated fields (RN08) ----------------------------------


def test_create_rejects_unknown_fields() -> None:
    invalid(TaskCreate, {"title": "x", "color": "red"}, "color")


def test_create_has_no_task_group_id_because_the_group_comes_from_the_path() -> None:
    invalid(TaskCreate, {"title": "x", "task_group_id": str(uuid4())}, "task_group_id")


@pytest.mark.parametrize("field", sorted(GENERATED_FIELDS))
def test_create_ignores_generated_fields_even_when_invalid(field: str) -> None:
    data = TaskCreate.model_validate({"title": "x", field: "not-valid-at-all"})

    assert data.model_dump()["title"] == "x"
    assert field not in data.model_dump()


# --- TaskUpdate -----------------------------------------------------------------------


def test_update_accepts_an_empty_body() -> None:
    assert TaskUpdate.model_validate({}).model_fields_set == set()


def test_update_tracks_which_fields_were_sent() -> None:
    data = TaskUpdate.model_validate({"status": "completed", "priority": "low"})

    assert data.model_fields_set == {"status", "priority"}
    assert data.model_dump(exclude_unset=True) == {
        "status": TaskStatus.COMPLETED,
        "priority": TaskPriority.LOW,
    }


@pytest.mark.parametrize("field", ["description", "due_date"])
def test_update_can_clear_optional_fields_with_null(field: str) -> None:
    data = TaskUpdate.model_validate({field: None})

    assert data.model_fields_set == {field}
    assert getattr(data, field) is None


@pytest.mark.parametrize("field", ["title", "status", "priority", "task_group_id"])
def test_update_cannot_set_required_fields_to_null(field: str) -> None:
    invalid(TaskUpdate, {field: None}, field)


def test_update_applies_the_same_limits_as_create() -> None:
    invalid(TaskUpdate, {"title": ""}, "title")
    invalid(TaskUpdate, {"title": "t" * 201}, "title")
    invalid(TaskUpdate, {"description": "d" * 2001}, "description")
    invalid(TaskUpdate, {"status": "bogus"}, "status")
    invalid(TaskUpdate, {"priority": "bogus"}, "priority")
    invalid(TaskUpdate, {"due_date": "31/12/2026"}, "due_date")


def test_update_accepts_a_task_group_id() -> None:
    group_id = uuid4()

    data = TaskUpdate.model_validate({"task_group_id": str(group_id)})

    assert data.task_group_id == group_id


def test_update_rejects_a_task_group_id_that_is_not_a_uuid() -> None:
    invalid(TaskUpdate, {"task_group_id": "not-a-uuid"}, "task_group_id")


def test_update_rejects_unknown_fields_but_ignores_generated_ones() -> None:
    invalid(TaskUpdate, {"color": "red"}, "color")

    data = TaskUpdate.model_validate({"title": "New", "completed_at": "ignored"})
    assert data.model_dump(exclude_unset=True) == {"title": "New"}


# --- TaskRead -------------------------------------------------------------------------


def test_read_is_built_from_a_table_row() -> None:
    task = build_task(
        build_task_group(),
        title="Report",
        status=TaskStatus.COMPLETED,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 12, 31),
    )

    data = TaskRead.model_validate(task)

    assert (data.id, data.task_group_id, data.title) == (
        task.id,
        task.task_group_id,
        "Report",
    )
    assert (data.status, data.priority) == (TaskStatus.COMPLETED, TaskPriority.HIGH)


def test_read_exposes_exactly_the_public_fields() -> None:
    data = TaskRead.model_validate(build_task(build_task_group()))

    assert set(data.model_dump()) == {
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


def test_read_serializes_enums_dates_and_datetimes_in_the_documented_formats() -> None:
    task = build_task(build_task_group(), due_date=date(2026, 12, 31))
    payload = json.loads(TaskRead.model_validate(task).model_dump_json())

    assert payload["status"] == "pending"
    assert payload["priority"] == "medium"
    assert payload["due_date"] == "2026-12-31"
    assert payload["created_at"].endswith("Z")
    assert payload["completed_at"] is None


def test_create_accepts_a_plain_date_object() -> None:
    data = TaskCreate.model_validate({"title": "x", "due_date": date(2026, 12, 31)})

    assert data.due_date == date(2026, 12, 31)


def test_create_rejects_a_datetime_object_as_due_date() -> None:
    invalid(
        TaskCreate,
        {"title": "x", "due_date": datetime(2026, 12, 31, 10, 30)},
        "due_date",
    )
