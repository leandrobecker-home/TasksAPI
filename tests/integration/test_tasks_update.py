"""Integration tests for PATCH /api/v1/tasks/{id} (RF12, RN04 to RN08)."""

from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import TaskPriority, TaskStatus
from tests.factories import create_task, create_task_group

URL = "/api/v1/tasks"
GROUPS = "/api/v1/task-groups"
STATUSES = [member.value for member in TaskStatus]


def patch(client: TestClient, task_id: Any, payload: Any) -> Any:
    return client.patch(f"{URL}/{task_id}", json=payload)


def moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


# --- partial updates ---------------------------------------------------------


def test_patch_changes_only_the_fields_sent(
    client: TestClient, session: Session
) -> None:
    task = create_task(
        session, title="Draft", description="original", priority=TaskPriority.LOW
    )

    response = patch(client, task.id, {"title": "Final"})

    body = response.json()
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert body["title"] == "Final"
    assert body["description"] == "original"
    assert body["priority"] == "low"
    assert body["status"] == "pending"
    assert body["id"] == str(task.id)


def test_patch_can_change_every_field_at_once(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(
        client,
        task.id,
        {
            "title": "New",
            "description": "text",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2027-01-31",
        },
    ).json()

    assert (body["title"], body["description"]) == ("New", "text")
    assert (body["status"], body["priority"]) == ("in_progress", "high")
    assert body["due_date"] == "2027-01-31"


def test_patch_can_change_only_the_status(client: TestClient, session: Session) -> None:
    task = create_task(session, title="Keep me")

    body = patch(client, task.id, {"status": "in_progress"}).json()

    assert (body["title"], body["status"]) == ("Keep me", "in_progress")


def test_patch_strips_surrounding_spaces_from_the_title(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    assert patch(client, task.id, {"title": "  Trimmed  "}).json()["title"] == "Trimmed"


def test_patch_is_persisted(client: TestClient, session: Session) -> None:
    task = create_task(session)

    patch(client, task.id, {"title": "Changed", "priority": "high"})

    stored = client.get(f"{URL}/{task.id}").json()
    assert (stored["title"], stored["priority"]) == ("Changed", "high")


def test_patch_with_null_clears_the_optional_fields(
    client: TestClient, session: Session
) -> None:
    task = create_task(session, description="text")
    patch(client, task.id, {"due_date": "2026-12-31"})

    body = patch(client, task.id, {"description": None, "due_date": None}).json()

    assert body["description"] is None
    assert body["due_date"] is None


def test_patch_with_an_empty_body_changes_nothing(
    client: TestClient, session: Session
) -> None:
    task = create_task(session, description="text")
    before = client.get(f"{URL}/{task.id}").json()

    response = patch(client, task.id, {})

    assert response.status_code == 200
    assert response.json() == before


def test_patch_moves_updated_at_forward_and_keeps_created_at(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)
    before = client.get(f"{URL}/{task.id}").json()

    after = patch(client, task.id, {"title": "Changed"}).json()

    assert after["created_at"] == before["created_at"]
    assert moment(after["updated_at"]) > moment(before["updated_at"])


# --- status transitions (RN06) and completed_at (RN07) ----------------------


@pytest.mark.parametrize("target", STATUSES)
@pytest.mark.parametrize("origin", STATUSES)
def test_every_status_transition_is_accepted(
    client: TestClient, session: Session, origin: str, target: str
) -> None:
    group = create_task_group(session)
    task_id = client.post(
        f"{GROUPS}/{group.id}/tasks", json={"title": "x", "status": origin}
    ).json()["id"]

    response = patch(client, task_id, {"status": target})

    assert response.status_code == 200
    assert response.json()["status"] == target


def test_completing_a_task_fills_completed_at(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(client, task.id, {"status": "completed"}).json()

    assert body["completed_at"] is not None
    assert body["completed_at"].endswith("Z")
    assert moment(body["completed_at"]) >= moment(body["created_at"])


@pytest.mark.parametrize("reopened", ["pending", "in_progress"])
def test_leaving_completed_clears_completed_at(
    client: TestClient, session: Session, reopened: str
) -> None:
    task = create_task(session)
    patch(client, task.id, {"status": "completed"})

    body = patch(client, task.id, {"status": reopened}).json()

    assert body["status"] == reopened
    assert body["completed_at"] is None


def test_sending_completed_again_keeps_the_original_time(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)
    first = patch(client, task.id, {"status": "completed"}).json()["completed_at"]

    second = patch(client, task.id, {"status": "completed", "title": "x"}).json()

    assert second["completed_at"] == first


def test_changing_other_fields_keeps_completed_at(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)
    first = patch(client, task.id, {"status": "completed"}).json()["completed_at"]

    body = patch(client, task.id, {"priority": "high"}).json()

    assert body["completed_at"] == first


def test_an_open_status_change_leaves_completed_at_empty(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(client, task.id, {"status": "in_progress"}).json()

    assert body["completed_at"] is None


def test_completed_at_sent_by_the_client_is_ignored(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(
        client, task.id, {"title": "x", "completed_at": "2000-01-01T00:00:00Z"}
    ).json()

    assert body["completed_at"] is None


def test_completed_at_sent_with_a_completion_is_ignored(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(
        client,
        task.id,
        {"status": "completed", "completed_at": "2000-01-01T00:00:00Z"},
    ).json()

    assert body["completed_at"] != "2000-01-01T00:00:00Z"
    assert moment(body["completed_at"]).year >= 2026


def test_other_generated_fields_sent_by_the_client_are_ignored(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = patch(
        client,
        task.id,
        {
            "title": "x",
            "id": str(uuid4()),
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
    ).json()

    assert body["id"] == str(task.id)
    assert body["created_at"] != "2000-01-01T00:00:00Z"
    assert body["updated_at"] != "2000-01-01T00:00:00Z"


# --- moving to another group (RN04) -------------------------------------------


def test_a_task_can_be_moved_to_another_group(
    client: TestClient, session: Session
) -> None:
    origin = create_task_group(session, name="Origin")
    destination = create_task_group(session, name="Destination")
    task = create_task(session, origin, title="Movable", priority=TaskPriority.HIGH)

    response = patch(client, task.id, {"task_group_id": str(destination.id)})

    body = response.json()
    assert response.status_code == 200
    assert body["task_group_id"] == str(destination.id)
    assert (body["title"], body["priority"]) == ("Movable", "high")


def test_a_moved_task_changes_which_group_lists_it(
    client: TestClient, session: Session
) -> None:
    origin = create_task_group(session, name="Origin")
    destination = create_task_group(session, name="Destination")
    task = create_task(session, origin)

    patch(client, task.id, {"task_group_id": str(destination.id)})

    assert client.get(f"{GROUPS}/{origin.id}/tasks").json()["total"] == 0
    listed = client.get(f"{GROUPS}/{destination.id}/tasks").json()
    assert [item["id"] for item in listed["items"]] == [str(task.id)]


def test_a_task_can_be_moved_and_edited_in_the_same_request(
    client: TestClient, session: Session
) -> None:
    destination = create_task_group(session, name="Destination")
    task = create_task(session)

    body = patch(
        client,
        task.id,
        {"task_group_id": str(destination.id), "status": "completed"},
    ).json()

    assert body["task_group_id"] == str(destination.id)
    assert body["status"] == "completed"
    assert body["completed_at"] is not None


def test_moving_a_task_to_its_own_group_is_accepted(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"task_group_id": str(task.task_group_id)})

    assert response.status_code == 200


def test_moving_a_task_to_an_unknown_group_is_422(
    client: TestClient, session: Session
) -> None:
    task = create_task(session, title="Stays")
    original_group = str(task.task_group_id)

    response = patch(
        client, task.id, {"task_group_id": str(uuid4()), "title": "Changed"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == "task_group_id: the task group does not exist."
    stored = client.get(f"{URL}/{task.id}").json()
    assert stored["task_group_id"] == original_group
    assert stored["title"] == "Stays"


def test_task_group_id_that_is_not_a_uuid_is_422(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"task_group_id": "not-a-uuid"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("task_group_id: ")


def test_the_origin_group_can_be_deleted_after_its_last_task_moves_out(
    client: TestClient, session: Session
) -> None:
    origin = create_task_group(session, name="Origin")
    destination = create_task_group(session, name="Destination")
    task = create_task(session, origin)
    assert client.delete(f"{GROUPS}/{origin.id}").status_code == 409

    patch(client, task.id, {"task_group_id": str(destination.id)})

    assert client.delete(f"{GROUPS}/{origin.id}").status_code == 204


# --- validation (422): same rules as RF06 -------------------------------------


@pytest.mark.parametrize("title", ["", "   ", None, 123, ["x"], "t" * 201])
def test_invalid_title_is_422(client: TestClient, session: Session, title: Any) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"title": title})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("title: ")


def test_description_over_2000_characters_is_422(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"description": "d" * 2001})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("description: ")


@pytest.mark.parametrize("field", ["status", "priority"])
@pytest.mark.parametrize("value", ["bogus", "HIGH", "", 1, None])
def test_enum_fields_reject_values_outside_the_enum(
    client: TestClient, session: Session, field: str, value: Any
) -> None:
    task = create_task(session)

    response = patch(client, task.id, {field: value})

    assert response.status_code == 422
    assert response.json()["detail"].startswith(f"{field}: ")


@pytest.mark.parametrize(
    "due_date", ["31/12/2026", "2026-13-01", "2026-02-30", "2026-12-31T00:00:00", 0]
)
def test_due_date_that_is_not_yyyy_mm_dd_is_422(
    client: TestClient, session: Session, due_date: Any
) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"due_date": due_date})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("due_date: ")


def test_a_rejected_patch_changes_nothing(client: TestClient, session: Session) -> None:
    task = create_task(session, title="Stays")

    patch(client, task.id, {"title": "Changed", "status": "bogus"})

    assert client.get(f"{URL}/{task.id}").json()["title"] == "Stays"


def test_unknown_field_is_422(client: TestClient, session: Session) -> None:
    task = create_task(session)

    response = patch(client, task.id, {"color": "red"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("color: ")


def test_body_that_is_not_an_object_is_422(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    assert patch(client, task.id, ["title"]).status_code == 422


def test_malformed_json_is_400(client: TestClient, session: Session) -> None:
    task = create_task(session)

    response = client.patch(
        f"{URL}/{task.id}",
        content='{"title": ',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400


# --- not found and bad ids ---------------------------------------------------


def test_unknown_task_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = patch(client, missing, {"title": "Anything"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"] == f"Task {missing} not found."


def test_id_that_is_not_a_uuid_is_422(client: TestClient) -> None:
    response = patch(client, "not-a-uuid", {"title": "Anything"})

    assert response.status_code == 422
    assert response.json()["detail"].startswith("task_id: ")


def test_an_invalid_body_wins_over_an_unknown_id(client: TestClient) -> None:
    assert patch(client, uuid4(), {"title": ""}).status_code == 422


def test_put_is_not_available_on_a_task(client: TestClient, session: Session) -> None:
    task = create_task(session, title="Stays")

    response = client.put(f"{URL}/{task.id}", json={"title": "Replaced"})

    assert response.status_code == 405
    assert "PATCH" in response.headers["allow"]
    assert "PUT" not in response.headers["allow"]
    assert client.get(f"{URL}/{task.id}").json()["title"] == "Stays"


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{URL}/{{task_id}}"]["patch"]

    assert operation["summary"] == "Update a task"
    assert operation["tags"] == ["tasks"]
