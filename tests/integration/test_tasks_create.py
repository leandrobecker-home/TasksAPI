"""Integration tests for POST /api/v1/task-groups/{group_id}/tasks (RF06)."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Task
from tests.factories import create_task_group

GROUPS = "/api/v1/task-groups"


def url(group_id: Any) -> str:
    return f"{GROUPS}/{group_id}/tasks"


def post(client: TestClient, group_id: Any, payload: Any) -> Any:
    return client.post(url(group_id), json=payload)


def task_count(session: Session) -> int:
    return len(session.exec(select(Task)).all())


# --- success -------------------------------------------------------------------------


def test_create_returns_201_with_the_new_task(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "Write report"})

    body = response.json()
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    assert set(body) == {
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
    assert UUID(body["id"])
    assert body["title"] == "Write report"


def test_the_task_belongs_to_the_group_in_the_path(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    body = post(client, group.id, {"title": "x"}).json()

    assert body["task_group_id"] == str(group.id)


def test_create_sets_the_location_header_to_the_new_task(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x"})

    assert response.headers["location"] == f"/api/v1/tasks/{response.json()['id']}"


def test_a_new_task_gets_the_defaults(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    body = post(client, group.id, {"title": "x"}).json()

    assert body["status"] == "pending"
    assert body["priority"] == "medium"
    assert body["description"] is None
    assert body["due_date"] is None
    assert body["completed_at"] is None


def test_generated_fields_are_set_by_the_server(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    body = post(client, group.id, {"title": "x"}).json()

    assert body["created_at"] == body["updated_at"]
    assert body["created_at"].endswith("Z")


def test_every_field_can_be_given(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    body = post(
        client,
        group.id,
        {
            "title": "Write report",
            "description": "quarterly numbers",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2026-12-31",
        },
    ).json()

    assert body["description"] == "quarterly numbers"
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-12-31"
    assert body["completed_at"] is None


def test_create_persists_the_task(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    task_id = UUID(post(client, group.id, {"title": "  Write report  "}).json()["id"])

    saved = session.get(Task, task_id)
    assert saved is not None
    assert (saved.title, saved.task_group_id) == ("Write report", group.id)


def test_create_strips_surrounding_spaces_from_the_title(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    assert post(client, group.id, {"title": "   Report   "}).json()["title"] == "Report"


def test_create_accepts_the_maximum_lengths(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "t" * 200, "description": "d" * 2000})

    assert response.status_code == 201


def test_create_handles_non_ascii_text(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    body = post(client, group.id, {"title": "Ação rápida 日本語"}).json()

    assert body["title"] == "Ação rápida 日本語"


def test_titles_do_not_have_to_be_unique(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    first = post(client, group.id, {"title": "Same"})
    second = post(client, group.id, {"title": "Same"})

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["id"] != second.json()["id"]


def test_the_same_title_is_fine_in_another_group(
    client: TestClient, session: Session
) -> None:
    work = create_task_group(session, name="Work")
    home = create_task_group(session, name="Home")

    assert post(client, work.id, {"title": "Same"}).status_code == 201
    assert post(client, home.id, {"title": "Same"}).status_code == 201


def test_a_task_created_as_completed_gets_completed_at(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    body = post(client, group.id, {"title": "Done", "status": "completed"}).json()

    assert body["status"] == "completed"
    assert body["completed_at"] == body["created_at"]


# --- the group must exist (RN02) ------------------------------------------------------


def test_unknown_group_is_404_and_creates_nothing(
    client: TestClient, session: Session
) -> None:
    missing = uuid4()

    response = post(client, missing, {"title": "Orphan"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Task group {missing} not found.",
        "instance": url(missing),
    }
    assert task_count(session) == 0


def test_group_id_that_is_not_a_uuid_is_422(client: TestClient) -> None:
    response = post(client, "not-a-uuid", {"title": "x"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("group_id: ")


def test_a_deleted_group_no_longer_accepts_tasks(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    client.delete(f"{GROUPS}/{group.id}")

    assert post(client, group.id, {"title": "Late"}).status_code == 404


def test_invalid_body_wins_over_an_unknown_group(client: TestClient) -> None:
    assert post(client, uuid4(), {"title": ""}).status_code == 422


# --- validation (422) -----------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": "no title"},
        {"title": ""},
        {"title": "   "},
        {"title": None},
        {"title": 123},
        {"title": ["x"]},
        {"title": "t" * 201},
    ],
)
def test_invalid_title_is_422(
    client: TestClient, session: Session, payload: Any
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, payload)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("title: ")
    assert task_count(session) == 0


def test_description_over_2000_characters_is_422(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x", "description": "d" * 2001})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("description: ")


@pytest.mark.parametrize("status", ["bogus", "PENDING", "done", "", 1, None])
def test_status_outside_the_enum_is_422(
    client: TestClient, session: Session, status: Any
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x", "status": status})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("status: ")


@pytest.mark.parametrize("priority", ["urgent", "HIGH", "", 2, None])
def test_priority_outside_the_enum_is_422(
    client: TestClient, session: Session, priority: Any
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x", "priority": priority})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("priority: ")


@pytest.mark.parametrize(
    "due_date",
    ["31/12/2026", "2026-13-01", "2026-02-30", "2026-12-31T00:00:00", 20261231, 0],
)
def test_due_date_that_is_not_yyyy_mm_dd_is_422(
    client: TestClient, session: Session, due_date: Any
) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x", "due_date": due_date})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("due_date: ")
    assert task_count(session) == 0


@pytest.mark.parametrize("field", ["color", "task_group_id", "normalized_name"])
def test_unknown_field_is_422(client: TestClient, session: Session, field: str) -> None:
    group = create_task_group(session)

    response = post(client, group.id, {"title": "x", field: "anything"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith(f"{field}: ")


def test_generated_fields_sent_by_the_client_are_ignored(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    sent_id = "00000000-0000-0000-0000-000000000001"

    body = post(
        client,
        group.id,
        {
            "title": "x",
            "id": sent_id,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
            "completed_at": "2000-01-01T00:00:00Z",
        },
    ).json()

    assert body["id"] != sent_id
    assert body["created_at"] != "2000-01-01T00:00:00Z"
    assert body["updated_at"] != "2000-01-01T00:00:00Z"
    assert body["completed_at"] is None


def test_body_that_is_not_an_object_is_422(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)

    assert client.post(url(group.id), json=["x"]).status_code == 422


def test_missing_body_is_422(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    assert client.post(url(group.id)).status_code == 422


def test_malformed_json_is_400(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    response = client.post(
        url(group.id),
        content='{"title": ',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


# --- documentation --------------------------------------------------------------------


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{GROUPS}/{{group_id}}/tasks"]["post"]

    assert operation["summary"] == "Create a task in a group"
    assert operation["tags"] == ["tasks"]
    assert "201" in operation["responses"]
