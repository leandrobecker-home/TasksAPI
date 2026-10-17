"""Integration tests for GET /api/v1/tasks/{id} (RF11)."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import TaskPriority, TaskStatus
from tests.factories import create_task, create_task_group

URL = "/api/v1/tasks"


def test_get_returns_the_task_with_all_its_fields(
    client: TestClient, session: Session
) -> None:
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

    response = client.get(f"{URL}/{task.id}")

    body = response.json()
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert body["id"] == str(task.id)
    assert body["task_group_id"] == str(group.id)
    assert body["title"] == "Write report"
    assert body["description"] == "quarterly numbers"
    assert body["status"] == "in_progress"
    assert body["priority"] == "high"
    assert body["due_date"] == "2026-12-31"
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    assert body["completed_at"] is None


def test_get_has_exactly_the_documented_fields(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = client.get(f"{URL}/{task.id}").json()

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


def test_get_returns_nulls_for_the_optional_fields(
    client: TestClient, session: Session
) -> None:
    task = create_task(session)

    body = client.get(f"{URL}/{task.id}").json()

    assert body["description"] is None
    assert body["due_date"] is None
    assert body["completed_at"] is None
    assert (body["status"], body["priority"]) == ("pending", "medium")


def test_get_returns_completed_at_for_a_completed_task(
    client: TestClient, session: Session
) -> None:
    moment = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    task = create_task(session, status=TaskStatus.COMPLETED, completed_at=moment)

    body = client.get(f"{URL}/{task.id}").json()

    assert body["completed_at"] == "2026-03-01T12:00:00Z"


def test_get_returns_only_the_requested_task(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    create_task(session, group, title="Other")
    wanted = create_task(session, group, title="Wanted")

    assert client.get(f"{URL}/{wanted.id}").json()["title"] == "Wanted"


def test_get_finds_a_task_whatever_its_group(
    client: TestClient, session: Session
) -> None:
    task = create_task(session, create_task_group(session, name="Elsewhere"))

    assert client.get(f"{URL}/{task.id}").status_code == 200


def test_get_accepts_an_uppercase_uuid(client: TestClient, session: Session) -> None:
    task = create_task(session)

    response = client.get(f"{URL}/{str(task.id).upper()}")

    assert response.status_code == 200
    assert response.json()["id"] == str(task.id)


def test_the_location_returned_by_post_leads_to_the_task(
    client: TestClient, session: Session
) -> None:
    group = create_task_group(session)
    created = client.post(f"/api/v1/task-groups/{group.id}/tasks", json={"title": "x"})

    response = client.get(created.headers["location"])

    assert response.status_code == 200
    assert response.json() == created.json()


def test_unknown_id_is_404(client: TestClient) -> None:
    missing = uuid4()

    response = client.get(f"{URL}/{missing}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"Task {missing} not found.",
        "instance": f"{URL}/{missing}",
    }


def test_a_group_id_is_not_a_task_id(client: TestClient, session: Session) -> None:
    group = create_task_group(session)

    assert client.get(f"{URL}/{group.id}").status_code == 404


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "123", "xyz-xyz", "1234-5678"])
def test_id_that_is_not_a_uuid_is_422(client: TestClient, bad_id: str) -> None:
    response = client.get(f"{URL}/{bad_id}")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["detail"].startswith("task_id: ")


def test_post_is_not_allowed_on_a_single_task(client: TestClient) -> None:
    response = client.post(f"{URL}/{uuid4()}", json={"title": "x"})

    assert response.status_code == 405
    assert "GET" in response.headers["allow"]


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][f"{URL}/{{task_id}}"]["get"]

    assert operation["summary"] == "Get a task"
    assert operation["tags"] == ["tasks"]
    assert operation["parameters"][0]["schema"]["format"] == "uuid"
